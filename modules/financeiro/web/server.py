"""
Folha Web — servidor local para fechamento de folha
Rodar: python modules/financeiro/web/server.py [periodo]
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from threading import Timer
from typing import Any

import anthropic
import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

# ── resolve directories ────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent.parent
HERE = Path(__file__).parent

period_arg = sys.argv[1] if len(sys.argv) > 1 else "2026-04"
if re.match(r"^\d{4}-\d{2}$", period_arg):
    PERIOD_DIR = ROOT / "runtime-data" / "financeiro" / "competencias" / period_arg
else:
    PERIOD_DIR = Path(period_arg) if Path(period_arg).is_absolute() else ROOT / period_arg

# ── app ────────────────────────────────────────────────────────────────────

app = FastAPI(title="Folha Web", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── helpers ────────────────────────────────────────────────────────────────

INBOX_BUCKETS = ["contabilidade", "simplesvet", "ponto", "whatsapp", "imagens", "manual", "outros"]
EARNING_CATS = [
    "valor_importado", "horas_trabalhadas", "producao_vet",
    "comissao_tosa", "bonus_manual", "credito_manual", "reembolso",
]
DISCOUNT_CATS = ["adiantamento", "consumo_em_aberto", "falha_veterinaria", "desconto_manual"]

PROFILE_RULES: dict[str, dict[str, str]] = {
    "folha_contabilidade_pdf": {
        "target_schema": "folha_importada",
        "prompt_objective": "Extrair bruto, descontos, liquido, periodo e observacoes da folha calculada.",
    },
    "comissao_itemizada": {
        "target_schema": "eventos_comissao_item",
        "prompt_objective": "Extrair eventos itemizados de comissao preservando colaborador, base e valor final.",
    },
    "simplesvet_export": {
        "target_schema": "eventos_operacionais",
        "prompt_objective": "Mapear linhas operacionais em eventos de comissao, producao ou desconto.",
    },
    "ponto_bruto": {
        "target_schema": "eventos_jornada",
        "prompt_objective": "Converter batidas em eventos de jornada por colaborador e data.",
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
        "prompt_objective": "Extrair linhas relevantes de planilha manual e classificar.",
    },
    "generico": {
        "target_schema": "evidencia_generica",
        "prompt_objective": "Classificar a evidencia, resumir o conteudo e apontar se exige revisao humana.",
    },
}


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def infer_profile(bucket: str, filename: str, suffix: str) -> str:
    name = filename.lower()
    if bucket == "contabilidade" and suffix == ".pdf":
        return "folha_contabilidade_pdf"
    if bucket == "simplesvet":
        return "comissao_itemizada" if "comiss" in name else "simplesvet_export"
    if bucket == "ponto":
        return "ponto_bruto"
    if bucket == "whatsapp":
        return "whatsapp_texto" if suffix in {".txt", ".json", ".md"} else "imagem_ocr"
    if bucket == "imagens":
        return "imagem_ocr"
    if bucket == "manual" and suffix in {".xlsx", ".xls", ".csv"}:
        return "planilha_manual"
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".heic"}:
        return "imagem_ocr"
    if suffix in {".xlsx", ".xls", ".csv"}:
        return "planilha_manual"
    return "generico"


# ── routes: meta ──────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = HERE / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/status")
async def get_status():
    meta = read_json(PERIOD_DIR / "periodo.json", {})
    colaboradores = read_json(PERIOD_DIR / "colaboradores.json", [])
    lancamentos = read_json(PERIOD_DIR / "lancamentos.json", [])
    pool = read_json(PERIOD_DIR / "pool" / "evidencias_indexadas.json", [])
    resultado = read_json(PERIOD_DIR / "saida" / "resultado.json")
    pending = [e for e in pool if e.get("review_status") == "pendente"]
    return {
        "periodo": meta.get("periodo", "—"),
        "empresa": meta.get("empresa", "—"),
        "period_dir": str(PERIOD_DIR),
        "colaboradores_count": len(colaboradores),
        "lancamentos_count": len(lancamentos),
        "pool_total": len(pool),
        "pool_pending": len(pending),
        "has_resultado": resultado is not None,
        "resultado_liquido": resultado["resumo"]["liquido_total"] if resultado else None,
        "resultado_avisos": len(resultado.get("avisos", [])) if resultado else 0,
    }


# ── routes: colaboradores ─────────────────────────────────────────────────

@app.get("/api/colaboradores")
async def get_colaboradores():
    return read_json(PERIOD_DIR / "colaboradores.json", [])


@app.put("/api/colaboradores")
async def update_colaboradores(data: list):
    write_json(PERIOD_DIR / "colaboradores.json", data)
    return {"ok": True}


# ── routes: lancamentos ───────────────────────────────────────────────────

@app.get("/api/lancamentos")
async def get_lancamentos():
    return read_json(PERIOD_DIR / "lancamentos.json", [])


@app.put("/api/lancamentos")
async def update_lancamentos(data: list):
    write_json(PERIOD_DIR / "lancamentos.json", data)
    return {"ok": True}


@app.post("/api/lancamentos/append")
async def append_lancamentos(data: list):
    existing = read_json(PERIOD_DIR / "lancamentos.json", [])
    write_json(PERIOD_DIR / "lancamentos.json", existing + data)
    return {"ok": True, "total": len(existing) + len(data)}


# ── routes: pool ──────────────────────────────────────────────────────────

@app.get("/api/pool")
async def get_pool():
    return read_json(PERIOD_DIR / "pool" / "evidencias_indexadas.json", [])


@app.post("/api/pool/indexar")
async def indexar_pool():
    result = subprocess.run(
        [sys.executable, "-m", "modules.financeiro", "indexar-pool", str(PERIOD_DIR)],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    pool = read_json(PERIOD_DIR / "pool" / "evidencias_indexadas.json", [])
    return {
        "ok": result.returncode == 0,
        "output": result.stdout + result.stderr,
        "items": pool,
    }


@app.post("/api/pool/upload/{bucket}")
async def upload_to_pool(bucket: str, file: UploadFile = File(...)):
    if bucket not in INBOX_BUCKETS:
        raise HTTPException(400, f"Bucket inválido: {bucket}")
    bucket_dir = PERIOD_DIR / "pool" / "inbox" / bucket
    bucket_dir.mkdir(parents=True, exist_ok=True)
    dest = bucket_dir / (file.filename or "arquivo")
    content = await file.read()
    dest.write_bytes(content)
    return {"ok": True, "path": str(dest), "size": len(content)}


@app.post("/api/pool/processar/{sha256}")
async def processar_evidencia(sha256: str):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(400, "ANTHROPIC_API_KEY não configurada. Configure a variável de ambiente e reinicie.")

    pool = read_json(PERIOD_DIR / "pool" / "evidencias_indexadas.json", [])
    item = next((e for e in pool if e["sha256"] == sha256), None)
    if not item:
        raise HTTPException(404, "Evidência não encontrada no índice.")

    abs_path = PERIOD_DIR / item["relative_path"]
    suffix = Path(abs_path).suffix.lower()
    text_exts = {".txt", ".csv", ".json", ".md", ".tsv"}

    content = ""
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(abs_path))
            content = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            raise HTTPException(422, f"Não foi possível ler o PDF: {e}")
    elif suffix in text_exts:
        try:
            content = abs_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            raise HTTPException(422, f"Não foi possível ler o arquivo: {e}")
    else:
        raise HTTPException(
            422,
            f"Arquivo binário ({suffix}) — adicione os lançamentos manualmente ou aguarde integração OCR.",
        )

    colaboradores = read_json(PERIOD_DIR / "colaboradores.json", [])
    cols_list = "\n".join(
        f'  - id: "{c["id"]}", nome: "{c["nome"]}", modo: "{c["modo"]}"'
        for c in colaboradores
    )

    client = anthropic.Anthropic(api_key=api_key)
    profile = item.get("profile", "generico")
    objective = PROFILE_RULES.get(profile, PROFILE_RULES["generico"])["prompt_objective"]

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=3000,
        system="Você é um extrator especializado em dados de folha de pagamento para clínicas veterinárias brasileiras. Responda APENAS com JSON válido, sem markdown nem texto extra.",
        messages=[
            {
                "role": "user",
                "content": f"""Perfil: {profile}
Objetivo: {objective}
Arquivo: {item['filename']}

Colaboradores cadastrados:
{cols_list}

Categorias de proventos: {', '.join(EARNING_CATS)}
Categorias de descontos: {', '.join(DISCOUNT_CATS)}

Conteúdo do arquivo:
{content[:8000]}

Retorne SOMENTE este JSON:
{{
  "entries": [
    {{
      "colaborador_id": "id_aqui",
      "categoria": "categoria_aqui",
      "valor": 0.0,
      "quantidade": null,
      "data": "YYYY-MM-DD ou null",
      "descricao": "descricao_aqui",
      "fonte": "{item['filename']}",
      "confidence": "high|medium|low",
      "notes": "dúvida ou null"
    }}
  ],
  "warnings": [],
  "needs_human_review": false
}}""",
            }
        ],
    )

    raw = message.content[0].text.strip() if message.content else "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            raise HTTPException(500, f"IA retornou resposta inválida: {raw[:200]}")
        parsed = json.loads(m.group(0))

    return {
        "sha256": sha256,
        "filename": item["filename"],
        "profile": profile,
        "entries": parsed.get("entries", []),
        "warnings": parsed.get("warnings", []),
        "needs_human_review": parsed.get("needs_human_review", True),
    }


@app.post("/api/pool/aceitar/{sha256}")
async def aceitar_evidencia(sha256: str, data: list):
    # append cleaned entries
    clean = [
        {k: v for k, v in entry.items() if k not in ("confidence", "notes") and v is not None and v != ""}
        for entry in data
    ]
    existing = read_json(PERIOD_DIR / "lancamentos.json", [])
    write_json(PERIOD_DIR / "lancamentos.json", existing + clean)

    # update pool status
    pool = read_json(PERIOD_DIR / "pool" / "evidencias_indexadas.json", [])
    write_json(
        PERIOD_DIR / "pool" / "evidencias_indexadas.json",
        [
            {**e, "status": "processado", "review_status": "aceito",
             "normalizado_em": datetime.now(timezone.utc).isoformat()}
            if e["sha256"] == sha256 else e
            for e in pool
        ],
    )
    return {"ok": True, "entries_added": len(clean)}


@app.post("/api/pool/rejeitar/{sha256}")
async def rejeitar_evidencia(sha256: str):
    pool = read_json(PERIOD_DIR / "pool" / "evidencias_indexadas.json", [])
    write_json(
        PERIOD_DIR / "pool" / "evidencias_indexadas.json",
        [
            {**e, "status": "rejeitado", "review_status": "rejeitado"}
            if e["sha256"] == sha256 else e
            for e in pool
        ],
    )
    return {"ok": True}


# ── routes: fechamento ────────────────────────────────────────────────────

@app.post("/api/fechar")
async def fechar_folha():
    result = subprocess.run(
        [sys.executable, "-m", "modules.financeiro", "fechar", str(PERIOD_DIR)],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    resultado = read_json(PERIOD_DIR / "saida" / "resultado.json")
    return {
        "ok": result.returncode == 0,
        "output": result.stdout + result.stderr,
        "resultado": resultado,
    }


@app.get("/api/resultado")
async def get_resultado():
    resultado = read_json(PERIOD_DIR / "saida" / "resultado.json")
    if not resultado:
        raise HTTPException(404, "Nenhum resultado calculado ainda.")
    return resultado


# ── main ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = 7420
    url = f"http://localhost:{port}"
    print(f"\n  Folha Web — PinkBlue Vet")
    print(f"  Competência: {PERIOD_DIR.name}")
    print(f"  Abrindo em:  {url}\n")
    Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
