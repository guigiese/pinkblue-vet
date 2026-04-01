import json
import time
from pathlib import Path

OPS_MAP_DIR = Path(__file__).resolve().parents[1] / "poc" / "architecture-map"
OPS_MAP_RUNTIME_PATH = OPS_MAP_DIR / "data" / "pinkblue-map.runtime.json"
OPS_MAP_SEED_PATH = OPS_MAP_DIR / "data" / "pinkblue-map.v1.json"
OPS_MAP_CACHE_TTL_SECONDS = 120

_ops_map_cache: dict[str, object] = {
    "generated_at": 0.0,
    "payload": None,
}


def get_ops_map_runtime(force_refresh: bool = False) -> dict:
    now = time.time()
    cached_payload = _ops_map_cache.get("payload")
    cached_at = float(_ops_map_cache.get("generated_at", 0.0) or 0.0)

    if not force_refresh and cached_payload and (now - cached_at) < OPS_MAP_CACHE_TTL_SECONDS:
        return cached_payload  # type: ignore[return-value]

    source_path = OPS_MAP_RUNTIME_PATH if OPS_MAP_RUNTIME_PATH.exists() else OPS_MAP_SEED_PATH
    runtime_map = json.loads(source_path.read_text(encoding="utf-8"))

    runtime_map["mode"] = "cloud-packaged-snapshot"
    runtime_map.setdefault("meta", {})
    runtime_map["meta"]["cloudServedAt"] = now
    runtime_map["meta"].setdefault("notes", [])
    runtime_map["meta"]["notes"] = list(runtime_map["meta"]["notes"]) + [
        "Cloud module serves the packaged operations-map snapshot to avoid self-probing recursion inside the app runtime.",
    ]

    for node in runtime_map.get("nodes", []):
        node["iconPath"] = f"/ops-map-static/assets/rendered/{node['id']}.png"

    _ops_map_cache["generated_at"] = now
    _ops_map_cache["payload"] = runtime_map
    return runtime_map
