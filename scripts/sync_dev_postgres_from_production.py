from __future__ import annotations

import base64
import configparser
import json
import os
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
RAILWAY_CMD = str(Path.home() / "AppData" / "Roaming" / "npm" / "railway.cmd")

from modules.plantao.actions import (  # noqa: E402
    aderir_sobreaviso,
    candidatar,
    confirmar_candidatura,
    criar_data_plantao,
    publicar_data_plantao,
)
from modules.plantao.schema import init_schema  # noqa: E402
from pb_platform.settings import settings  # noqa: E402
from pb_platform.storage import store  # noqa: E402

EXPORT_TABLES = [
    "users",
    "app_kv",
    "telegram_subscriptions",
    "lab_snapshots",
    "notification_event_log",
    "exam_thresholds",
]


def _load_secret(name: str) -> str:
    parser = configparser.ConfigParser()
    parser.read(ROOT / ".secrets", encoding="utf-8")
    return parser["railway"][name].strip()


def _run(*args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        list(args),
        cwd=str(ROOT),
        env={**os.environ, **(env or {})},
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def export_production_snapshot() -> dict[str, list[dict]]:
    remote_code = """
import base64, json, sqlite3
conn = sqlite3.connect('/data/pinkbluevet.sqlite3')
conn.row_factory = sqlite3.Row
tables = %s
payload = {}
for table in tables:
    try:
        rows = [dict(row) for row in conn.execute(f'SELECT * FROM {table}').fetchall()]
    except Exception:
        rows = []
    payload[table] = rows
print(base64.b64encode(json.dumps(payload, ensure_ascii=False).encode('utf-8')).decode('ascii'))
""" % json.dumps(EXPORT_TABLES)
    command = (
        'python -c "import base64; exec(base64.b64decode(\'%s\').decode(\'utf-8\'))"'
        % base64.b64encode(remote_code.encode("utf-8")).decode("ascii")
    )
    env = {"RAILWAY_API_TOKEN": _load_secret("token")}
    output = _run(
        RAILWAY_CMD,
        "ssh",
        "-p",
        _load_secret("project_id"),
        "-s",
        _load_secret("service_id"),
        "-e",
        _load_secret("env_id"),
        command,
        env=env,
    )
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    encoded = "".join(lines)
    return json.loads(base64.b64decode(encoded).decode("utf-8"))


def export_local_postgres(engine) -> dict[str, list[dict]]:
    snapshot: dict[str, list[dict]] = {}
    with engine.connect() as conn:
        for table in EXPORT_TABLES:
            try:
                rows = conn.execute(text(f"SELECT * FROM {table}")).mappings().all()
            except Exception:
                rows = []
            snapshot[table] = [dict(row) for row in rows]
    return snapshot


def load_local_sqlite_extras() -> tuple[dict[str, dict], dict[str, dict]]:
    sqlite_path = settings.legacy_db_path
    if not sqlite_path.exists():
        return {}, {}
    import sqlite3

    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    app_kv = {
        row["key"]: dict(row)
        for row in conn.execute("SELECT key, value, updated_at FROM app_kv").fetchall()
    }
    lab_snapshots = {
        row["lab_id"]: dict(row)
        for row in conn.execute(
            "SELECT lab_id, snapshot_json, last_check, last_error, updated_at FROM lab_snapshots"
        ).fetchall()
    }
    conn.close()
    return app_kv, lab_snapshots


def ensure_dev_database(engine) -> None:
    url = settings.database_url
    if "localhost" not in url and "127.0.0.1" not in url:
        raise RuntimeError(f"Refusando resetar banco não local: {url}")
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


def import_snapshot(engine, snapshot: dict[str, list[dict]], app_kv_extras: dict[str, dict], lab_extras: dict[str, dict]) -> None:
    with engine.begin() as conn:
        for row in snapshot.get("app_kv", []):
            conn.execute(
                text(
                    "INSERT INTO app_kv(key, value, updated_at) VALUES (:key, :value, :updated_at) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at"
                ),
                row,
            )
        for row in app_kv_extras.values():
            conn.execute(
                text(
                    "INSERT INTO app_kv(key, value, updated_at) VALUES (:key, :value, :updated_at) "
                    "ON CONFLICT(key) DO NOTHING"
                ),
                row,
            )
        for row in snapshot.get("users", []):
            mapped = {
                "id": row["id"],
                "email": row["email"].strip().lower(),
                "password_hash": row["password_hash"],
                "role": row.get("role", "viewer"),
                "is_active": row.get("is_active", 1),
                "force_password_change": row.get("force_password_change", 0),
                "created_at": row.get("created_at") or "",
                "updated_at": row.get("updated_at") or "",
                "nome": row.get("nome", "") or "",
                "telefone": row.get("telefone", "") or "",
                "crmv": row.get("crmv", "") or "",
                "status": row.get("status") or ("ativo" if row.get("is_active", 1) else "inativo"),
                "tentativas_login": row.get("tentativas_login", 0) or 0,
                "bloqueado_ate": row.get("bloqueado_ate"),
            }
            conn.execute(
                text(
                    "INSERT INTO users("
                    "id, email, password_hash, role, is_active, force_password_change, created_at, updated_at, "
                    "nome, telefone, crmv, status, tentativas_login, bloqueado_ate"
                    ") VALUES ("
                    ":id, :email, :password_hash, :role, :is_active, :force_password_change, :created_at, :updated_at, "
                    ":nome, :telefone, :crmv, :status, :tentativas_login, :bloqueado_ate)"
                ),
                mapped,
            )
        conn.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('users', 'id'), COALESCE((SELECT MAX(id) FROM users), 1), true)"
            )
        )
        for table in ("telegram_subscriptions", "lab_snapshots", "notification_event_log", "exam_thresholds"):
            for row in snapshot.get(table, []):
                cols = ", ".join(row.keys())
                vals = ", ".join(f":{key}" for key in row.keys())
                updates = ", ".join(f"{key}=excluded.{key}" for key in row.keys() if key not in {"chat_id", "lab_id", "signature", "exam_slug"})
                pk = {
                    "telegram_subscriptions": "chat_id",
                    "lab_snapshots": "lab_id",
                    "notification_event_log": "signature",
                    "exam_thresholds": "exam_slug",
                }[table]
                conn.execute(
                    text(
                        f"INSERT INTO {table}({cols}) VALUES ({vals}) "
                        f"ON CONFLICT({pk}) DO UPDATE SET {updates}"
                    ),
                    row,
                )
        for row in lab_extras.values():
            conn.execute(
                text(
                    "INSERT INTO lab_snapshots(lab_id, snapshot_json, last_check, last_error, updated_at) "
                    "VALUES (:lab_id, :snapshot_json, :last_check, :last_error, :updated_at) "
                    "ON CONFLICT(lab_id) DO NOTHING"
                ),
                row,
            )


def seed_dev_fixtures(engine) -> None:
    fixtures = [
        {
            "email": "gestor.plantao.dev@pinkbluevet.local",
            "password": "PlantaoDev@123",
            "role": "operator",
            "nome": "Gestor Plantão DEV",
            "status": "ativo",
        },
        {
            "email": "veterinaria.dev@pinkbluevet.local",
            "password": "PlantaoDev@123",
            "role": "veterinario",
            "nome": "Marina Veterinaria DEV",
            "telefone": "51999990001",
            "crmv": "SC-12345",
            "status": "ativo",
        },
        {
            "email": "veterinaria.espera.dev@pinkbluevet.local",
            "password": "PlantaoDev@123",
            "role": "veterinario",
            "nome": "Julia Espera DEV",
            "telefone": "51999990002",
            "crmv": "SC-54321",
            "status": "ativo",
        },
        {
            "email": "auxiliar.dev@pinkbluevet.local",
            "password": "PlantaoDev@123",
            "role": "auxiliar",
            "nome": "Carlos Auxiliar DEV",
            "telefone": "51999990003",
            "status": "ativo",
        },
    ]
    for fixture in fixtures:
        if not store.get_user_by_email(fixture["email"]):
            store.create_user(**fixture)
    if not store.get_user_by_email("cadastro.pendente.dev@pinkbluevet.local"):
        store.create_user_request(
            email="cadastro.pendente.dev@pinkbluevet.local",
            password="PlantaoDev@123",
            role="veterinario",
            nome="Cadastro Pendente DEV",
            telefone="51999990004",
            crmv="SC-11111",
        )

    with engine.connect() as conn:
        existing = conn.execute(text("SELECT COUNT(*) FROM plantao_datas")).scalar_one()
    if existing:
        return

    gestor = store.get_user_by_email("gestor.plantao.dev@pinkbluevet.local") or store.get_user_by_email("guigiese@gmail.com")
    vet = store.get_user_by_email("veterinaria.dev@pinkbluevet.local")
    vet_lista = store.get_user_by_email("veterinaria.espera.dev@pinkbluevet.local")
    aux = store.get_user_by_email("auxiliar.dev@pinkbluevet.local")
    if not gestor or not vet or not vet_lista or not aux:
        raise RuntimeError("Fixtures básicas de usuários não foram criadas corretamente.")

    with engine.connect() as conn:
        local_id = conn.execute(text("SELECT id FROM plantao_locais ORDER BY id LIMIT 1")).scalar_one()

    turno_data = (date.today() + timedelta(days=3)).isoformat()
    sobreaviso_data = (date.today() + timedelta(days=4)).isoformat()
    escala_id = criar_data_plantao(
        engine,
        local_id=local_id,
        tipo="presencial",
        subtipo="regular",
        data=turno_data,
        hora_inicio="08:00",
        hora_fim="20:00",
        posicoes=[{"tipo": "veterinario", "vagas": 1}, {"tipo": "auxiliar", "vagas": 1}],
        gestor_id=gestor["id"],
        observacoes="Fixture DEV para validação do MVP1 de Plantão.",
    )
    publicar_data_plantao(engine, escala_id, gestor["id"])

    sobreaviso_id = criar_data_plantao(
        engine,
        local_id=local_id,
        tipo="sobreaviso",
        subtipo="sobreaviso_emergencia",
        data=sobreaviso_data,
        hora_inicio="20:00",
        hora_fim="08:00",
        posicoes=[],
        gestor_id=gestor["id"],
        observacoes="Fixture DEV para fila de sobreaviso.",
    )
    publicar_data_plantao(engine, sobreaviso_id, gestor["id"])

    with engine.connect() as conn:
        vet_posicao = conn.execute(
            text("SELECT id FROM plantao_posicoes WHERE data_id=:data_id AND tipo='veterinario' ORDER BY id LIMIT 1"),
            {"data_id": escala_id},
        ).scalar_one()
        aux_posicao = conn.execute(
            text("SELECT id FROM plantao_posicoes WHERE data_id=:data_id AND tipo='auxiliar' ORDER BY id LIMIT 1"),
            {"data_id": escala_id},
        ).scalar_one()

    cand_vet = candidatar(engine, vet_posicao, vet["id"])
    confirmar_candidatura(engine, cand_vet, gestor["id"])
    candidatar(engine, vet_posicao, vet_lista["id"])
    cand_aux = candidatar(engine, aux_posicao, aux["id"])
    confirmar_candidatura(engine, cand_aux, gestor["id"])
    aderir_sobreaviso(engine, sobreaviso_id, vet["id"])


def main() -> None:
    timestamp = date.today().isoformat()
    backup_dir = ROOT / "runtime-data" / "legacy-backups" / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)

    prod_snapshot = export_production_snapshot()
    (backup_dir / "production_snapshot.json").write_text(
        json.dumps(prod_snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if settings.legacy_db_path.exists():
        shutil.copy2(settings.legacy_db_path, backup_dir / settings.legacy_db_path.name)

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    local_pg_snapshot = export_local_postgres(engine)
    (backup_dir / "dev_postgres_before_sync.json").write_text(
        json.dumps(local_pg_snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    app_kv_extras, lab_extras = load_local_sqlite_extras()
    ensure_dev_database(engine)
    store.init_db()
    init_schema(store.engine)
    import_snapshot(store.engine, prod_snapshot, app_kv_extras, lab_extras)
    init_schema(store.engine)
    seed_dev_fixtures(store.engine)
    print("DEV PostgreSQL sincronizado com o estado real de produção e fixtures do Plantão.")


if __name__ == "__main__":
    main()
