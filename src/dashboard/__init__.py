"""src/dashboard -- Gleipnir dashboard package.

The dashboard is a Streamlit app. Run it with:

    streamlit run src/dashboard/app.py

This __init__.py exposes a single helper, launch_dashboard(), used by
run_all.py and the MCP server to start the Streamlit server in a subprocess.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


_ROOT = Path(__file__).parent.parent.parent.resolve()
_APP  = Path(__file__).parent / "app.py"


def launch_dashboard(port: int = 8501, *, block: bool = False) -> subprocess.Popen | None:
    """Start the Streamlit dashboard server.

    Parameters
    ----------
    port:
        Port for the Streamlit server (default 8501).
    block:
        If True, wait for the process to exit (useful for tests).
        If False (default), return the Popen object immediately so the
        caller can decide when to wait/terminate.

    Returns
    -------
    The Popen object, or None when block=True.
    """
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(_APP),
        "--server.port", str(port),
        "--server.headless", "false",
    ]
    proc = subprocess.Popen(cmd, cwd=str(_ROOT))
    if block:
        proc.wait()
        return None
    return proc
