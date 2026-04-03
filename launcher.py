"""Launcher script for KSPDeltaVForMods API server.

Checks dependencies, installs if missing, then starts uvicorn.
Writes errors to launcher.log in the same directory.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

LOG_FILE = Path(__file__).parent / "launcher.log"
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


def check_and_install_deps() -> None:
    """Check if fastapi is importable; if not, pip install from requirements.txt."""
    try:
        import fastapi  # noqa: F401

        log.info("fastapi found, skipping install")
    except ImportError:
        log.info("fastapi not found, installing dependencies...")
        req_file = Path(__file__).parent / "requirements.txt"
        if req_file.exists():
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
                capture_output=True,
                text=True,
            )
            log.info("pip stdout: %s", result.stdout)
            if result.returncode != 0:
                log.error("pip install failed: %s", result.stderr)
                sys.exit(1)
            log.info("Dependencies installed successfully")
        else:
            log.error("requirements.txt not found at %s", req_file)
            # Try direct install as fallback
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "fastapi", "uvicorn[standard]", "python-multipart"],
                capture_output=True,
                text=True,
            )


def main() -> None:
    """Start the API server."""
    log.info("Launcher starting...")
    log.info("Python: %s", sys.executable)
    log.info("Working dir: %s", Path.cwd())
    log.info("Script dir: %s", Path(__file__).parent)

    check_and_install_deps()

    try:
        import uvicorn

        from api import app

        log.info("Starting uvicorn on 127.0.0.1:8000")
        uvicorn.run(app, host="127.0.0.1", port=8000)
    except Exception:
        log.exception("Failed to start API server")
        sys.exit(1)


if __name__ == "__main__":
    main()
