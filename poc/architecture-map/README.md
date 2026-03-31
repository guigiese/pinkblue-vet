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

## Safety Guardrail

This PoC must stay parallel to the active Lab Monitor delivery line.
Do not mix it into the production app or deploy path until the scope is validated.
