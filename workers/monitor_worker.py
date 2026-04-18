"""
Entrypoint standalone do monitor — sem dependência do servidor web.
Usado quando MONITOR_EMBEDDED=false no ambiente de produção.

Procfile: worker: python -m workers.monitor_worker
"""
import os
import time

from core import run_monitor_loop
from web.state import MonitorState, state


def main() -> None:
    print("[monitor_worker] iniciando loop standalone")
    run_monitor_loop(state)


if __name__ == "__main__":
    main()
