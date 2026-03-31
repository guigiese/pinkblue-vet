"""
Monitor de exames - thin local runner.

Calls run_monitor_loop from core.py with state=None (no web-server persistence).
Useful for running the monitor locally without the FastAPI web server.
State is not persisted between restarts when run this way.
"""

from core import run_monitor_loop

if __name__ == "__main__":
    run_monitor_loop(state=None)
