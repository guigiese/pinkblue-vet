"""
Seed de escalas de teste — maio 2026.

Regras:
  Sextas-feiras : 13:30-18:00  status=rascunho
  Sábados       : 09:00-12:00 e 14:00-18:00  status=publicado
  Domingos      : 14:00-18:00  status=publicado
  Feriado 01/05 : 09:00-18:00  status=publicado
  Vagas         : 1 veterinário + 1 auxiliar em todas
  Local         : primeiro local ativo do banco
  Criado por    : primeiro usuário ativo (master)

Idempotente: pula inserção se já existe escala para mesmo
local + data + hora_inicio.
"""

import sys
import os
from datetime import date, timedelta

# Garantir que o worktree está no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from pb_platform.storage import store

engine = store._engine

MAIO_INICIO = date(2026, 5, 1)
MAIO_FIM    = date(2026, 5, 31)
FERIADOS    = {"2026-05-01"}  # Dia do Trabalho

def get_local_id(conn):
    row = conn.execute(text(
        "SELECT id FROM plantao_locais WHERE ativo != 0 ORDER BY id LIMIT 1"
    )).fetchone()
    if not row:
        raise RuntimeError("Nenhum local ativo cadastrado. Cadastre ao menos um local antes de executar o seed.")
    return row[0]

def get_criado_por(conn):
    row = conn.execute(text(
        "SELECT id FROM users ORDER BY id LIMIT 1"
    )).fetchone()
    if not row:
        raise RuntimeError("Nenhum usuário encontrado no banco.")
    return row[0]

def ja_existe(conn, local_id, data_str, hora_inicio):
    row = conn.execute(text(
        "SELECT id FROM plantao_datas WHERE local_id=:l AND data=:d AND hora_inicio=:h LIMIT 1"
    ), {"l": local_id, "d": data_str, "h": hora_inicio}).fetchone()
    return row is not None

def inserir_escala(conn, local_id, criado_por, data_str, hora_inicio, hora_fim, status, subtipo="regular"):
    from datetime import datetime
    agora = datetime.now().isoformat(sep="T", timespec="seconds")

    if ja_existe(conn, local_id, data_str, hora_inicio):
        print(f"  SKIP  {data_str} {hora_inicio}-{hora_fim} (já existe)")
        return

    result = conn.execute(text("""
        INSERT INTO plantao_datas
            (local_id, tipo, subtipo, data, hora_inicio, hora_fim, observacoes,
             status, criado_em, alterado_em, criado_por)
        VALUES
            (:local_id, 'presencial', :subtipo, :data, :hora_inicio, :hora_fim, '',
             :status, :agora, :agora, :criado_por)
        RETURNING id
    """), {
        "local_id": local_id,
        "subtipo": subtipo,
        "data": data_str,
        "hora_inicio": hora_inicio,
        "hora_fim": hora_fim,
        "status": status,
        "agora": agora,
        "criado_por": criado_por,
    })
    data_id = result.fetchone()[0]

    for tipo_pos in ("veterinario", "auxiliar"):
        conn.execute(text(
            "INSERT INTO plantao_posicoes (data_id, tipo, vagas) VALUES (:d, :t, 1)"
        ), {"d": data_id, "t": tipo_pos})

    label = "RASCUNHO" if status == "rascunho" else "PUBLICADO"
    print(f"  {label}  {data_str} {hora_inicio}-{hora_fim}  [{subtipo}]")

    # Registrar publicado_em se publicado
    if status == "publicado":
        conn.execute(text(
            "UPDATE plantao_datas SET publicado_em=:agora, publicado_por=:por WHERE id=:id"
        ), {"agora": agora, "por": criado_por, "id": data_id})


def main():
    with engine.begin() as conn:
        local_id   = get_local_id(conn)
        criado_por = get_criado_por(conn)
        print(f"Local ID: {local_id} | Criado por user ID: {criado_por}\n")

        d = MAIO_INICIO
        inseridos = 0

        while d <= MAIO_FIM:
            ds = d.strftime("%Y-%m-%d")
            wd = d.weekday()  # 0=seg … 4=sex 5=sab 6=dom

            if ds in FERIADOS:
                print(f"[{ds}] Feriado")
                inserir_escala(conn, local_id, criado_por, ds, "09:00", "18:00", "publicado", subtipo="feriado")
                inseridos += 1

            elif wd == 4:  # sexta
                print(f"[{ds}] Sexta")
                inserir_escala(conn, local_id, criado_por, ds, "13:30", "18:00", "rascunho")
                inseridos += 1

            elif wd == 5:  # sábado
                print(f"[{ds}] Sábado")
                inserir_escala(conn, local_id, criado_por, ds, "09:00", "12:00", "publicado")
                inserir_escala(conn, local_id, criado_por, ds, "14:00", "18:00", "publicado")
                inseridos += 2

            elif wd == 6:  # domingo
                print(f"[{ds}] Domingo")
                inserir_escala(conn, local_id, criado_por, ds, "14:00", "18:00", "publicado")
                inseridos += 1

            d += timedelta(days=1)

        print(f"\nSeed concluído: {inseridos} escalas processadas.")


if __name__ == "__main__":
    main()
