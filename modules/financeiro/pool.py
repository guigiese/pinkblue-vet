from __future__ import annotations

import hashlib
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .folha import init_period_directory, read_json, write_json

INBOX_BUCKETS = [
    "contabilidade",
    "simplesvet",
    "ponto",
    "whatsapp",
    "imagens",
    "manual",
    "outros",
]

PROFILE_DEFINITIONS = {
    "folha_contabilidade_pdf": {
        "target_schema": "folha_importada",
        "prompt_objective": "Extrair bruto, descontos, liquido, periodo e observacoes da folha calculada.",
    },
    "simplesvet_export": {
        "target_schema": "eventos_operacionais",
        "prompt_objective": "Mapear linhas operacionais em eventos de comissao, producao ou desconto.",
    },
    "comissao_itemizada": {
        "target_schema": "eventos_comissao_item",
        "prompt_objective": "Extrair eventos itemizados de comissao preservando colaborador, base e valor final.",
    },
    "ponto_bruto": {
        "target_schema": "eventos_jornada",
        "prompt_objective": "Converter batidas, horarios ou ponto bruto em eventos de jornada por colaborador e data.",
    },
    "whatsapp_texto": {
        "target_schema": "eventos_jornada",
        "prompt_objective": "Extrair datas, horarios, colaborador e observacoes a partir de texto de WhatsApp.",
    },
    "imagem_ocr": {
        "target_schema": "eventos_nao_estruturados",
        "prompt_objective": "Ler imagem, identificar tipo de evidencia e estruturar o conteudo relevante.",
    },
    "planilha_manual": {
        "target_schema": "eventos_financeiros",
        "prompt_objective": "Extrair linhas relevantes de uma planilha manual e classificá-las.",
    },
    "generico": {
        "target_schema": "evidencia_generica",
        "prompt_objective": "Classificar a evidencia, resumir o conteudo e apontar se exige revisao humana.",
    },
}


def init_competency_workspace(
    directory: Path,
    period: str,
    company: str,
    force: bool = False,
) -> Path:
    period_dir = init_period_directory(directory, period=period, company=company, force=force)

    directories = [
        period_dir / "pool",
        period_dir / "pool" / "inbox",
        period_dir / "pool" / "normalized",
        period_dir / "pool" / "archive",
        period_dir / "pool" / "rejected",
    ]
    directories.extend((period_dir / "pool" / "inbox" / bucket) for bucket in INBOX_BUCKETS)
    for folder in directories:
        folder.mkdir(parents=True, exist_ok=True)

    templates = {
        period_dir / "pool" / "conectores.json": {
            "simplesvet": {
                "enabled": False,
                "mode": "export_folder",
                "notes": "Apontar para pasta de exportacao ou API quando existir.",
            },
            "contabilidade": {
                "enabled": False,
                "mode": "drop_folder",
                "notes": "Usar para PDFs ou planilhas enviados pela contabilidade.",
            },
            "whatsapp": {
                "enabled": False,
                "mode": "manual_export",
                "notes": "Exportar conversas ou screenshots para a pasta whatsapp.",
            },
        },
        period_dir / "pool" / "regras_normalizacao.json": {
            "provider": "openai_api",
            "primary_model": "gpt-5.4-mini",
            "fallback_model": "gpt-5.4",
            "reasoning_effort": "medium",
            "review_policy": {
                "always_review_profiles": [
                    "ponto_bruto",
                    "imagem_ocr",
                    "whatsapp_texto",
                ],
                "auto_accept_profiles": [
                    "folha_contabilidade_pdf",
                    "comissao_itemizada",
                ],
            },
            "notes": [
                "Usar Structured Outputs para cada perfil de extracao.",
                "Escalonar para o modelo maior apenas em casos ambiguos ou com erro de schema.",
            ],
        },
        period_dir / "pool" / "evidencias_indexadas.json": [],
        period_dir / "pool" / "fila_normalizacao.json": [],
        period_dir / "pool" / "revisao_humana.json": [],
    }
    for target, payload in templates.items():
        if target.exists() and not force:
            continue
        write_json(target, payload)

    return period_dir


def index_evidence_pool(period_dir: Path) -> dict[str, Any]:
    pool_dir = period_dir / "pool"
    inbox_dir = pool_dir / "inbox"
    index_path = pool_dir / "evidencias_indexadas.json"
    queue_path = pool_dir / "fila_normalizacao.json"

    existing_rows = {
        item["sha256"]: item for item in read_json(index_path, default=[])
        if isinstance(item, dict) and item.get("sha256")
    }

    indexed_rows: list[dict[str, Any]] = []
    queue: list[dict[str, Any]] = []

    for file_path in sorted(path for path in inbox_dir.rglob("*") if path.is_file()):
        row = _build_evidence_record(period_dir, file_path)
        previous = existing_rows.get(row["sha256"], {})
        row["status"] = previous.get("status", "pendente")
        row["normalizado_em"] = previous.get("normalizado_em")
        row["review_status"] = previous.get("review_status", "pendente")
        indexed_rows.append(row)

        queue.append(
            {
                "evidence_sha256": row["sha256"],
                "relative_path": row["relative_path"],
                "profile": row["profile"],
                "target_schema": row["target_schema"],
                "status": "pendente" if row["status"] == "pendente" else "ignorar",
                "prompt_objective": row["prompt_objective"],
                "requires_human_review": row["profile"] in {"ponto_bruto", "imagem_ocr", "whatsapp_texto"},
            }
        )

    write_json(index_path, indexed_rows)
    write_json(queue_path, queue)

    by_profile: dict[str, int] = {}
    for item in indexed_rows:
        profile = item["profile"]
        by_profile[profile] = by_profile.get(profile, 0) + 1

    summary = {
        "indexed": len(indexed_rows),
        "queue_items": len(queue),
        "profiles": by_profile,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return summary


def _build_evidence_record(period_dir: Path, file_path: Path) -> dict[str, Any]:
    relative_path = file_path.relative_to(period_dir).as_posix()
    sha256 = hashlib.sha256(file_path.read_bytes()).hexdigest()
    stat = file_path.stat()
    mime_type, _ = mimetypes.guess_type(file_path.name)
    bucket = _infer_bucket(period_dir, file_path)
    profile = _infer_profile(bucket, file_path)
    profile_definition = PROFILE_DEFINITIONS[profile]

    return {
        "sha256": sha256,
        "relative_path": relative_path,
        "bucket": bucket,
        "filename": file_path.name,
        "extension": file_path.suffix.lower(),
        "mime_type": mime_type or "application/octet-stream",
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "profile": profile,
        "target_schema": profile_definition["target_schema"],
        "prompt_objective": profile_definition["prompt_objective"],
    }


def _infer_bucket(period_dir: Path, file_path: Path) -> str:
    relative = file_path.relative_to(period_dir / "pool" / "inbox")
    return relative.parts[0] if relative.parts else "outros"


def _infer_profile(bucket: str, file_path: Path) -> str:
    name = file_path.name.lower()
    suffix = file_path.suffix.lower()

    if bucket == "contabilidade" and suffix == ".pdf":
        return "folha_contabilidade_pdf"
    if bucket == "simplesvet":
        if "comiss" in name:
            return "comissao_itemizada"
        return "simplesvet_export"
    if bucket == "ponto":
        return "ponto_bruto"
    if bucket == "whatsapp":
        if suffix in {".txt", ".json", ".md"}:
            return "whatsapp_texto"
        return "imagem_ocr"
    if bucket == "imagens":
        return "imagem_ocr"
    if bucket == "manual" and suffix in {".xlsx", ".xls", ".csv"}:
        return "planilha_manual"
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".heic"}:
        return "imagem_ocr"
    if suffix in {".xlsx", ".xls", ".csv"}:
        return "planilha_manual"
    return "generico"
