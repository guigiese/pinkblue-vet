import json
import time
from pathlib import Path

from scripts.refresh_architecture_map_data import SEED_PATH, apply_live_snapshot

OPS_MAP_DIR = Path(__file__).resolve().parents[1] / "poc" / "architecture-map"
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

    map_seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    runtime_map = apply_live_snapshot(map_seed)

    for node in runtime_map.get("nodes", []):
        node["iconPath"] = f"/ops-map-static/assets/rendered/{node['id']}.png"

    _ops_map_cache["generated_at"] = now
    _ops_map_cache["payload"] = runtime_map
    return runtime_map
