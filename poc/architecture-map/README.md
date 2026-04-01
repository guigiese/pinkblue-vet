# PinkBlue Architecture Map PoC

Local-only proof of concept for a topology / dependency map around Lab Monitor.

This PoC is intentionally isolated from the production app and deploy flow.
It runs from static files plus a locally refreshed runtime snapshot.

## Run

Option 1:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_architecture_map_poc.ps1
```

This option refreshes the runtime snapshot first, including live probes for:
- production site and `/labmonitor`
- GitHub repo visibility and last push
- Railway deploy + memory/network signals
- public Lab Monitor pages for labs and channels

Option 2:

```powershell
python .\scripts\refresh_architecture_map_data.py
python .\scripts\build_architecture_map_icons.py
python -m http.server 8765 -d .\poc\architecture-map
```

Then open:

```text
http://127.0.0.1:8765
```

## Current Scope

- interactive graph of the main PinkBlue artifacts
- base JSON enriched by a local runtime refresh
- side panel for node and edge inspection
- live health, connection, deploy, and quota-watch signals when available
- includes WhatsApp / Callmebot even though it is disabled by default

## Icon Pipeline Guardrails

- The final node icon consumed by the graph is the rendered PNG in `poc/architecture-map/assets/rendered/`.
- Health status and secondary category badges are baked into that PNG by `scripts/build_architecture_map_icons.py`.
- `poc/architecture-map/app.js` must point Cytoscape directly to the rendered PNG path.
- Do not wrap the rendered PNG in a second SVG layer just to add badges. That caused washed-out square artifacts and broke the intended round icon look.
- If the graph visuals look stale after a rebuild, reload the page. `app.js` appends a version token to the icon URL to reduce browser cache issues.

## Safe Run Rule

- Prefer `powershell -ExecutionPolicy Bypass -File .\scripts\run_architecture_map_poc.ps1`.
- If serving manually, always refresh the runtime snapshot and rebuild rendered icons before starting `http.server`.
- A stale `pinkblue-map.runtime.json` or stale `assets/rendered/*.png` can make the graph fall back to an outdated visual state.

## Safety Guardrail

This PoC must stay parallel to the active Lab Monitor delivery line.
Do not mix it into the production app or deploy path until the scope is validated.
