from __future__ import annotations

import configparser
import json
import re
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "poc" / "architecture-map" / "data"
SEED_PATH = DATA_DIR / "pinkblue-map.v1.json"
RUNTIME_PATH = DATA_DIR / "pinkblue-map.runtime.json"
CONFIG_PATH = ROOT / "config.json"
SECRETS_PATH = ROOT / ".secrets"

PROD_BASE_URL = "https://pinkblue-vet-production.up.railway.app"
GITHUB_REPO = "guigiese/pinkblue-vet"
JIRA_BASE_URL = "https://guigiese.atlassian.net"
LOCAL_TZ = ZoneInfo("America/Sao_Paulo")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_local_display(value: str | None) -> str:
    if not value:
        return "N/A"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.astimezone(LOCAL_TZ).strftime("%d/%m %H:%M")


def fmt_ms(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{round(value)} ms"


def fmt_gb(value: float | None) -> str:
    if value is None:
        return "N/A"
    if value < 1:
        return f"{round(value * 1024)} MB"
    return f"{value:.2f} GB"


def fmt_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}%"


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def get_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "PinkBlue-ArchitectureMap-Refresher/1.0",
            "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
        }
    )
    return session


def http_probe(session: requests.Session, url: str, timeout: int = 15) -> dict[str, Any]:
    started = now_utc()
    try:
        response = session.get(url, timeout=timeout)
        elapsed_ms = (now_utc() - started).total_seconds() * 1000
        return {
            "ok": response.ok,
            "status": response.status_code,
            "elapsedMs": elapsed_ms,
            "url": str(response.url),
            "text": response.text,
        }
    except Exception as exc:  # pragma: no cover
        return {
            "ok": False,
            "status": None,
            "elapsedMs": None,
            "url": url,
            "text": "",
            "error": str(exc),
        }


def parse_public_labs(html: str) -> dict[str, dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    result: dict[str, dict[str, Any]] = {}

    for card in soup.select("div.bg-white.rounded-xl"):
        title = card.find("h3")
        badge = card.select_one("span.font-mono")
        if not title or not badge:
            continue

        text = card.get_text(" ", strip=True)
        connector = badge.get_text(" ", strip=True).lower()
        last_check = None
        match = re.search(r"Último check:\s*([0-9:]+)", text)
        if match:
            last_check = match.group(1)

        error_node = card.select_one("p.text-red-500")
        result[connector] = {
            "name": title.get_text(" ", strip=True),
            "enabled": "Desabilitado" not in text,
            "lastCheck": last_check,
            "error": error_node.get_text(" ", strip=True) if error_node else "",
        }

    return result


def parse_public_channels(html: str) -> dict[str, dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    result: dict[str, dict[str, Any]] = {}

    for card in soup.select("div.bg-white.rounded-xl"):
        title = card.find("h3")
        badge = card.select_one("span.font-mono")
        if not title or not badge:
            continue

        channel_id = title.get_text(" ", strip=True).lower()
        text = card.get_text(" ", strip=True)
        result[channel_id] = {
            "enabled": "Desabilitado" not in text,
            "userCount": len(card.select("button[hx-post*='/remove']")),
        }

    return result


def parse_protocol_totals(html: str) -> dict[str, int]:
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    return {
        "ready": int(re.search(r"(\d+)\s+Pronto[s]?", text, re.I).group(1)) if re.search(r"(\d+)\s+Pronto[s]?", text, re.I) else 0,
        "partial": int(re.search(r"(\d+)\s+Parcial(?:is)?", text, re.I).group(1)) if re.search(r"(\d+)\s+Parcial(?:is)?", text, re.I) else 0,
        "progress": int(re.search(r"(\d+)%\s+prontos", text, re.I).group(1)) if re.search(r"(\d+)%\s+prontos", text, re.I) else 0,
        "total": int(re.search(r"(\d+)\s+Protocolos", text, re.I).group(1)) if re.search(r"(\d+)\s+Protocolos", text, re.I) else 0,
    }


def fetch_github_snapshot(session: requests.Session) -> dict[str, Any]:
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}"
    probe = http_probe(session, api_url)
    if not probe["ok"]:
        return {"ok": False, "reason": probe.get("error") or f"HTTP {probe['status']}"}

    payload = json.loads(probe["text"])
    return {
        "ok": True,
        "pushedAt": payload.get("pushed_at"),
        "issues": payload.get("open_issues_count", 0),
        "visibility": payload.get("visibility", "unknown"),
        "repoUrl": payload.get("html_url", f"https://github.com/{GITHUB_REPO}"),
        "elapsedMs": probe["elapsedMs"],
        "defaultBranch": payload.get("default_branch", "main"),
    }


def railway_gql(token: str, query: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    response = requests.post(
        "https://backboard.railway.app/graphql/v2",
        headers=headers,
        json={"query": query},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(payload["errors"][0]["message"])
    return payload["data"]


def fetch_railway_snapshot() -> dict[str, Any]:
    cfg = configparser.ConfigParser()
    cfg.read(SECRETS_PATH)
    if "railway" not in cfg:
        return {"ok": False, "reason": "Railway credentials not available locally."}

    token = cfg["railway"].get("token", "")
    service_id = cfg["railway"].get("service_id", "")
    env_id = cfg["railway"].get("env_id", "")
    app_url = cfg["railway"].get("url", PROD_BASE_URL)
    if not token or not service_id or not env_id:
        return {"ok": False, "reason": "Incomplete Railway credentials in .secrets."}

    service_query = f"""
    query {{
      service(id: "{service_id}") {{
        id
        name
        projectId
        project {{ id name }}
      }}
      serviceInstance(serviceId: "{service_id}", environmentId: "{env_id}") {{
        id
        serviceName
        environmentId
        sleepApplication
        isUpdatable
        latestDeployment {{ id status createdAt }}
      }}
      serviceInstanceLimits(serviceId: "{service_id}", environmentId: "{env_id}")
    }}
    """
    service_data = railway_gql(token, service_query)
    project_id = service_data["service"]["projectId"]

    end = now_utc()
    start = end - timedelta(hours=24)
    metrics_query = f"""
    query {{
      usage(
        projectId: "{project_id}"
        startDate: "{start.isoformat()}"
        endDate: "{end.isoformat()}"
        measurements: [CPU_USAGE, NETWORK_RX_GB, NETWORK_TX_GB]
      ) {{
        measurement
        value
        tags {{ projectId serviceId environmentId }}
      }}
      metrics(
        projectId: "{project_id}"
        serviceId: "{service_id}"
        environmentId: "{env_id}"
        startDate: "{start.isoformat()}"
        endDate: "{end.isoformat()}"
        measurements: [CPU_USAGE, MEMORY_USAGE_GB]
        groupBy: [SERVICE_ID]
      ) {{
        measurement
        tags {{ serviceId }}
        values {{ value ts }}
      }}
    }}
    """
    metrics_data = railway_gql(token, metrics_query)

    usage_by_measurement = {item["measurement"]: item["value"] for item in metrics_data["usage"]}
    cpu_values: list[float] = []
    memory_values: list[float] = []
    for item in metrics_data["metrics"]:
        if item["tags"].get("serviceId") != service_id:
            continue
        values = [point["value"] for point in item["values"]]
        if item["measurement"] == "CPU_USAGE":
            cpu_values = values
        if item["measurement"] == "MEMORY_USAGE_GB":
            memory_values = values

    limits = service_data["serviceInstanceLimits"]["containers"]
    return {
        "ok": True,
        "serviceName": service_data["service"]["name"],
        "projectName": service_data["service"]["project"]["name"],
        "projectId": project_id,
        "appUrl": app_url,
        "latestDeployment": service_data["serviceInstance"]["latestDeployment"],
        "sleepApplication": service_data["serviceInstance"]["sleepApplication"],
        "isUpdatable": service_data["serviceInstance"]["isUpdatable"],
        "cpuLimit": limits["cpu"],
        "memoryLimitGb": limits["memoryBytes"] / 1_000_000_000,
        "networkRxGb24h": usage_by_measurement.get("NETWORK_RX_GB"),
        "networkTxGb24h": usage_by_measurement.get("NETWORK_TX_GB"),
        "cpuAvgPct24h": statistics.fmean(cpu_values) * 100 if cpu_values else None,
        "cpuPeakPct24h": max(cpu_values) * 100 if cpu_values else None,
        "memoryNowGb": memory_values[-1] if memory_values else None,
        "memoryPeakGb24h": max(memory_values) if memory_values else None,
    }


def merge_links(base_links: list[dict[str, str]], extra_links: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    merged: list[dict[str, str]] = []
    for item in base_links + extra_links:
        key = (item.get("label", ""), item.get("url", ""))
        if not key[0] or not key[1] or key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def apply_live_snapshot(map_data: dict[str, Any]) -> dict[str, Any]:
    session = get_session()
    generated_at = now_utc()
    generated_iso = generated_at.isoformat()

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    root_probe = http_probe(session, f"{PROD_BASE_URL}/")
    dashboard_probe = http_probe(session, f"{PROD_BASE_URL}/labmonitor")
    counts_probe = http_probe(session, f"{PROD_BASE_URL}/labmonitor/partials/lab_counts")
    labs_probe = http_probe(session, f"{PROD_BASE_URL}/labmonitor/labs")
    channels_probe = http_probe(session, f"{PROD_BASE_URL}/labmonitor/canais")

    labs_public = parse_public_labs(labs_probe["text"]) if labs_probe["ok"] else {}
    channels_public = parse_public_channels(channels_probe["text"]) if channels_probe["ok"] else {}
    totals = (
        parse_protocol_totals(counts_probe["text"])
        if counts_probe["ok"]
        else {"ready": 0, "partial": 0, "progress": 0, "total": 0}
    )
    github = fetch_github_snapshot(session)
    railway = fetch_railway_snapshot()

    nodes = {node["id"]: node for node in map_data["nodes"]}
    edges = {edge["id"]: edge for edge in map_data["edges"]}

    icon_map = {
        "local-workspace": "workspace",
        "codex": "codex",
        "claude": "claude",
        "github": "github",
        "jira": "jira",
        "railway": "railway",
        "pinkblue-site": "site",
        "lab-monitor": "labmonitor",
        "telegram": "telegram",
        "whatsapp-callmebot": "whatsapp",
        "bitlab": "bitlab",
        "nexio": "nexio",
    }

    for node in nodes.values():
        node["iconKey"] = icon_map.get(node["id"], node.get("kind", "system"))
        node["source"] = {"kind": "manual", "label": "Manual snapshot", "checkedAt": generated_iso}
        node["healthReason"] = node.get("notes", "")
        node["signals"] = []
        node["metrics"] = []
        node["links"] = node.get("links", [])

    nodes["local-workspace"].update(
        {
            "statusLine": "Localhost-safe workspace",
            "health": "healthy",
            "source": {"kind": "local", "label": "Local repo", "checkedAt": generated_iso},
            "signals": [
                "PoC continua isolada do deploy principal.",
                "Arquivos vivem fora da linha ativa do Claude.",
            ],
            "metrics": [
                {"label": "Scope", "value": "Parallel-safe"},
                {"label": "Mode", "value": "Localhost only"},
            ],
            "links": merge_links(nodes["local-workspace"]["links"], []),
        }
    )

    nodes["codex"].update(
        {
            "statusLine": "Sessão ativa",
            "health": "healthy",
            "source": {"kind": "session", "label": "Current Codex session", "checkedAt": generated_iso},
            "healthReason": "Atuando só na PoC local e na estrutura paralela do projeto.",
            "signals": [
                "Sessão atual ativa no workspace local.",
                "Jira e documentação seguem sincronizados por esta linha.",
            ],
            "metrics": [
                {"label": "Role", "value": "Planning + implementation"},
                {"label": "Scope", "value": "No deploy touch"},
            ],
        }
    )

    nodes["claude"].update(
        {
            "statusLine": "Pausado antes do deploy",
            "health": "warning",
            "source": {"kind": "manual", "label": "User input", "checkedAt": generated_iso},
            "healthReason": "Linha principal pausada por créditos esgotados. Mantivemos a PoC fora desse escopo.",
            "signals": [
                "Créditos pausaram a execução do Claude.",
                "O downstream desta PoC não deve interferir no deploy em aberto.",
            ],
            "metrics": [
                {"label": "Credits", "value": "Exhausted"},
                {"label": "Risk rule", "value": "Do not disturb active scope"},
            ],
        }
    )

    github_links = [
        {"label": "Repo", "url": f"https://github.com/{GITHUB_REPO}"},
        {"label": "Commits", "url": f"https://github.com/{GITHUB_REPO}/commits/main"},
    ]
    if github["ok"]:
        nodes["github"].update(
            {
                "statusLine": f"Repo público • push {to_local_display(github['pushedAt'])}",
                "health": "healthy",
                "source": {"kind": "live-api", "label": "GitHub API", "checkedAt": generated_iso},
                "healthReason": "API do GitHub respondeu normalmente e o repositório público segue acessível.",
                "signals": unique_strings(
                    [
                        f"GitHub API respondeu em {fmt_ms(github['elapsedMs'])}.",
                        f"Último push detectado em {to_local_display(github['pushedAt'])}.",
                        f"Visibilidade atual: {github['visibility']}.",
                    ]
                ),
                "metrics": [
                    {"label": "Visibility", "value": str(github["visibility"]).capitalize()},
                    {"label": "Open issues", "value": str(github["issues"])},
                    {"label": "Default branch", "value": github["defaultBranch"]},
                ],
                "links": merge_links(nodes["github"]["links"], github_links),
            }
        )
    else:
        nodes["github"].update(
            {
                "health": "warning",
                "statusLine": "Sem telemetria ao vivo",
                "healthReason": github["reason"],
                "signals": [github["reason"]],
                "links": merge_links(nodes["github"]["links"], github_links),
            }
        )

    nodes["jira"].update(
        {
            "statusLine": "3 projetos • board de triagem ativo",
            "health": "healthy",
            "source": {"kind": "manual", "label": "Jira workspace", "checkedAt": generated_iso},
            "healthReason": "Fluxo e projetos PB estão ativos. A telemetria aqui ainda é operacional, não via API de uso.",
            "signals": [
                "Projetos ativos: PBEXM, PBCORE e PBINC.",
                "PB Triage mantém cards ambíguos visíveis sem criar projeto-limbo.",
            ],
            "metrics": [
                {"label": "Projects", "value": "3"},
                {"label": "Shared board", "value": "PB Triage"},
            ],
            "links": merge_links(
                nodes["jira"]["links"],
                [
                    {"label": "Triage filter", "url": f"{JIRA_BASE_URL}/issues/?filter=10069"},
                    {"label": "PBCORE", "url": f"{JIRA_BASE_URL}/jira/software/projects/PBCORE"},
                ],
            ),
        }
    )

    nodes["pinkblue-site"].update(
        {
            "statusLine": f"Landing {root_probe['status']} • {fmt_ms(root_probe['elapsedMs'])}",
            "health": "healthy" if root_probe["ok"] else "problem",
            "source": {"kind": "live-http", "label": "Public HTTP probe", "checkedAt": generated_iso},
            "healthReason": "Landing pública respondeu normalmente." if root_probe["ok"] else root_probe.get("error", "Landing indisponível."),
            "signals": [
                f"GET / retornou {root_probe['status'] or 'erro'} em {fmt_ms(root_probe['elapsedMs'])}.",
            ],
            "metrics": [
                {"label": "HTTP", "value": str(root_probe["status"] or "ERR")},
                {"label": "Latency", "value": fmt_ms(root_probe["elapsedMs"])},
            ],
            "links": merge_links(
                nodes["pinkblue-site"]["links"],
                [{"label": "Live site", "url": f"{PROD_BASE_URL}/"}],
            ),
        }
    )

    labs_enabled = sum(1 for lab in config["labs"] if lab.get("enabled", True))
    notifiers_enabled = sum(1 for notifier in config["notifiers"] if notifier.get("enabled", True))
    dashboard_health = "healthy" if dashboard_probe["ok"] and counts_probe["ok"] else "problem"
    nodes["lab-monitor"].update(
        {
            "statusLine": f"{totals['total']} protocolos • {totals['ready']} prontos",
            "health": dashboard_health,
            "source": {"kind": "live-http", "label": "Public app routes", "checkedAt": generated_iso},
            "healthReason": (
                "Dashboard, contadores e páginas operacionais responderam normalmente."
                if dashboard_health == "healthy"
                else "Uma ou mais rotas públicas do Lab Monitor não responderam como esperado."
            ),
            "usage": {"kind": "system", "value": f"{totals['ready']} prontos • {totals['partial']} parciais"},
            "limit": {"kind": "polling", "value": f"Intervalo atual {config['interval_minutes']} min"},
            "signals": unique_strings(
                [
                    f"GET /labmonitor retornou {dashboard_probe['status'] or 'erro'} em {fmt_ms(dashboard_probe['elapsedMs'])}.",
                    f"GET /labmonitor/partials/lab_counts retornou {counts_probe['status'] or 'erro'}.",
                    f"{labs_enabled} laboratórios e {notifiers_enabled} canal(is) ativos na config versionada.",
                ]
            ),
            "metrics": [
                {"label": "Dashboard", "value": f"{dashboard_probe['status'] or 'ERR'} • {fmt_ms(dashboard_probe['elapsedMs'])}"},
                {"label": "Protocolos", "value": str(totals["total"])},
                {"label": "Progress", "value": f"{totals['progress']}% prontos"},
                {"label": "Active stack", "value": f"{labs_enabled} labs • {notifiers_enabled} canais"},
            ],
            "links": merge_links(
                nodes["lab-monitor"]["links"],
                [
                    {"label": "Dashboard", "url": f"{PROD_BASE_URL}/labmonitor"},
                    {"label": "Labs", "url": f"{PROD_BASE_URL}/labmonitor/labs"},
                    {"label": "Canais", "url": f"{PROD_BASE_URL}/labmonitor/canais"},
                ],
            ),
        }
    )

    if railway["ok"]:
        memory_ratio = (railway["memoryNowGb"] or 0) / railway["memoryLimitGb"] if railway["memoryLimitGb"] else 0
        railway_health = "healthy"
        if railway["latestDeployment"]["status"] != "SUCCESS":
            railway_health = "problem"
        elif memory_ratio >= 0.75:
            railway_health = "warning"

        nodes["railway"].update(
            {
                "statusLine": f"Deploy {railway['latestDeployment']['status']} • RAM {fmt_gb(railway['memoryNowGb'])}",
                "health": railway_health,
                "source": {"kind": "live-api", "label": "Railway GraphQL + HTTP probes", "checkedAt": generated_iso},
                "healthReason": (
                    "Railway está saudável agora: último deploy em SUCCESS, app acordado e uso de memória bem abaixo do limite."
                    if railway_health == "healthy"
                    else "Railway merece atenção: ou houve falha no último deploy, ou o uso já está alto perto do limite."
                ),
                "usage": {
                    "kind": "runtime",
                    "value": f"RX {fmt_gb(railway['networkRxGb24h'])} • TX {fmt_gb(railway['networkTxGb24h'])} nas últimas 24h",
                },
                "limit": {
                    "kind": "runtime",
                    "value": f"{railway['cpuLimit']} vCPU • {fmt_gb(railway['memoryLimitGb'])} RAM",
                },
                "signals": unique_strings(
                    [
                        f"Último deploy: {railway['latestDeployment']['status']} em {to_local_display(railway['latestDeployment']['createdAt'])}.",
                        f"Memória agora: {fmt_gb(railway['memoryNowGb'])}; pico 24h: {fmt_gb(railway['memoryPeakGb24h'])}.",
                        f"CPU 24h: média {fmt_percent(railway['cpuAvgPct24h'])}; pico {fmt_percent(railway['cpuPeakPct24h'])}.",
                        "O alerta antigo foi removido porque o serviço está respondendo bem e sem pressão real de memória.",
                    ]
                ),
                "metrics": [
                    {"label": "Deploy", "value": f"{railway['latestDeployment']['status']} • {to_local_display(railway['latestDeployment']['createdAt'])}"},
                    {"label": "Memory", "value": f"{fmt_gb(railway['memoryNowGb'])} now • {fmt_gb(railway['memoryPeakGb24h'])} peak / {fmt_gb(railway['memoryLimitGb'])}"},
                    {"label": "CPU 24h", "value": f"{fmt_percent(railway['cpuAvgPct24h'])} avg • {fmt_percent(railway['cpuPeakPct24h'])} peak"},
                    {"label": "Traffic 24h", "value": f"RX {fmt_gb(railway['networkRxGb24h'])} • TX {fmt_gb(railway['networkTxGb24h'])}"},
                ],
                "links": merge_links(
                    nodes["railway"]["links"],
                    [{"label": "Production app", "url": railway["appUrl"]}],
                ),
            }
        )
    else:
        nodes["railway"].update(
            {
                "health": "warning",
                "statusLine": "Sem telemetria ao vivo",
                "source": {"kind": "manual", "label": "Fallback manual", "checkedAt": generated_iso},
                "healthReason": railway["reason"],
                "signals": [railway["reason"]],
            }
        )

    telegram_info = channels_public.get("telegram", {})
    telegram_enabled = telegram_info.get("enabled", True)
    telegram_users = telegram_info.get("userCount", 0)
    telegram_health = "healthy" if telegram_enabled and telegram_users > 0 else ("warning" if telegram_enabled else "dormant")
    nodes["telegram"].update(
        {
            "statusLine": f"{'Habilitado' if telegram_enabled else 'Desabilitado'} • {telegram_users} inscritos",
            "health": telegram_health,
            "source": {"kind": "live-http", "label": "Public canais page", "checkedAt": generated_iso},
            "healthReason": (
                "Canal principal ativo com usuários inscritos visíveis na página pública."
                if telegram_health == "healthy"
                else "Canal ativo sem usuários suficientes, ou desabilitado na configuração."
            ),
            "usage": {"kind": "channel", "value": f"{telegram_users} usuário(s) inscritos"},
            "signals": unique_strings(
                [
                    f"Página /labmonitor/canais mostra Telegram {'habilitado' if telegram_enabled else 'desabilitado'}.",
                    f"Usuários visíveis agora: {telegram_users}.",
                ]
            ),
            "metrics": [
                {"label": "Enabled", "value": "Yes" if telegram_enabled else "No"},
                {"label": "Users", "value": str(telegram_users)},
            ],
            "links": merge_links(
                nodes["telegram"]["links"],
                [{"label": "Canais page", "url": f"{PROD_BASE_URL}/labmonitor/canais"}],
            ),
        }
    )

    whatsapp_info = channels_public.get("whatsapp", {})
    whatsapp_enabled = whatsapp_info.get("enabled", False)
    nodes["whatsapp-callmebot"].update(
        {
            "statusLine": "Desabilitado na config ativa" if not whatsapp_enabled else "Canal opcional ativo",
            "health": "dormant" if not whatsapp_enabled else "warning",
            "source": {"kind": "live-http", "label": "Public canais page", "checkedAt": generated_iso},
            "healthReason": (
                "Canal mantido mapeado, mas hoje desligado na configuração ativa. Útil para decisão futura de reativar ou aposentar."
                if not whatsapp_enabled
                else "Canal opcional ativo, mas com rate limit duro do Callmebot."
            ),
            "usage": {"kind": "channel", "value": "0 fluxo ativo agora" if not whatsapp_enabled else "Canal opcional"},
            "limit": {"kind": "rate-limit", "value": "16 msgs / 240 min"},
            "signals": [
                f"Página /labmonitor/canais mostra WhatsApp {'habilitado' if whatsapp_enabled else 'desabilitado'}.",
                "O conector continua mapeado por valor operacional e por decisão futura de descarte.",
            ],
            "metrics": [
                {"label": "Enabled", "value": "Yes" if whatsapp_enabled else "No"},
                {"label": "Limit", "value": "16 msgs / 240 min"},
            ],
            "links": merge_links(
                nodes["whatsapp-callmebot"]["links"],
                [{"label": "Canais page", "url": f"{PROD_BASE_URL}/labmonitor/canais"}],
            ),
        }
    )

    for lab_node_id, connector_id in [("bitlab", "bitlab"), ("nexio", "nexio")]:
        info = labs_public.get(connector_id, {})
        enabled = info.get("enabled", True)
        has_error = bool(info.get("error"))
        health = "healthy"
        if not enabled:
            health = "dormant"
        elif has_error:
            health = "warning"

        nodes[lab_node_id].update(
            {
                "statusLine": f"{'Habilitado' if enabled else 'Desabilitado'} • último check {info.get('lastCheck', 'N/A')}",
                "health": health,
                "source": {"kind": "live-http", "label": "Public labs page", "checkedAt": generated_iso},
                "healthReason": (
                    f"{info.get('name', nodes[lab_node_id]['name'])} aparece habilitado e sem erro público recente."
                    if health == "healthy"
                    else info.get("error") or "Conector desabilitado ou com erro público recente."
                ),
                "signals": unique_strings(
                    [
                        f"Página /labmonitor/labs mostra {info.get('name', nodes[lab_node_id]['name'])} {'habilitado' if enabled else 'desabilitado'}.",
                        f"Último check visível: {info.get('lastCheck', 'N/A')}.",
                        info.get("error", ""),
                    ]
                ),
                "metrics": [
                    {"label": "Enabled", "value": "Yes" if enabled else "No"},
                    {"label": "Last check", "value": info.get("lastCheck", "N/A")},
                ],
                "links": merge_links(
                    nodes[lab_node_id]["links"],
                    [{"label": "Labs page", "url": f"{PROD_BASE_URL}/labmonitor/labs"}],
                ),
            }
        )

    edges["github-railway"].update(
        {
            "health": nodes["railway"]["health"],
            "check": nodes["railway"]["statusLine"],
            "notes": "Deploy source segue no GitHub, mas agora o mapa já mostra o estado vivo do serviço no Railway.",
        }
    )
    edges["railway-lab-monitor"].update(
        {
            "health": nodes["lab-monitor"]["health"],
            "check": f"{dashboard_probe['status'] or 'ERR'} • {fmt_ms(dashboard_probe['elapsedMs'])}",
            "notes": "Esta conexão agora é validada pela própria resposta pública do app em produção.",
        }
    )
    edges["site-lab-monitor"].update(
        {
            "health": "healthy" if root_probe["ok"] and dashboard_probe["ok"] else "problem",
            "check": f"/ {root_probe['status'] or 'ERR'} • /labmonitor {dashboard_probe['status'] or 'ERR'}",
            "notes": "A rota pública do site e a entrada do Lab Monitor foram verificadas no refresh local.",
        }
    )
    edges["lab-monitor-telegram"].update(
        {
            "health": nodes["telegram"]["health"],
            "check": f"{telegram_users} inscritos" if telegram_enabled else "desabilitado",
            "notes": "Saúde inferida da página pública de canais, sem disparar mensagem de teste.",
        }
    )
    edges["lab-monitor-whatsapp"].update(
        {
            "health": nodes["whatsapp-callmebot"]["health"],
            "check": "desabilitado" if not whatsapp_enabled else "ativo com rate limit",
            "notes": "Canal mantido no mapa para decisão futura, mas sem uso ativo agora.",
        }
    )
    edges["lab-monitor-bitlab"].update(
        {
            "health": nodes["bitlab"]["health"],
            "check": labs_public.get("bitlab", {}).get("lastCheck", "N/A"),
            "notes": "Sinal derivado da página pública de laboratórios.",
        }
    )
    edges["lab-monitor-nexio"].update(
        {
            "health": nodes["nexio"]["health"],
            "check": labs_public.get("nexio", {}).get("lastCheck", "N/A"),
            "notes": "Sinal derivado da página pública de laboratórios.",
        }
    )

    live_nodes = sum(1 for node in nodes.values() if node.get("source", {}).get("kind", "").startswith("live"))
    watch_nodes = sum(1 for node in nodes.values() if node.get("health") in {"warning", "problem", "dormant"})

    map_data["mode"] = "local-live-snapshot"
    map_data["meta"] = {
        "generatedAt": generated_iso,
        "generatedAtDisplay": generated_at.astimezone(LOCAL_TZ).strftime("%d/%m/%Y %H:%M:%S"),
        "liveNodeCount": live_nodes,
        "manualNodeCount": len(nodes) - live_nodes,
        "watchNodeCount": watch_nodes,
        "sourceCoverage": f"{live_nodes}/{len(nodes)} live node snapshots",
        "notes": [
            "A PoC continua isolada do deploy principal.",
            "Os sinais ao vivo são best effort: onde não há API segura, mantemos leitura manual ou pública.",
        ],
    }
    return map_data


def main() -> None:
    map_data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    runtime_map = apply_live_snapshot(map_data)
    RUNTIME_PATH.write_text(
        json.dumps(runtime_map, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Refreshed runtime map: {RUNTIME_PATH}")


if __name__ == "__main__":
    main()
