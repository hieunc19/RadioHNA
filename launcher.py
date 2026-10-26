"""Double-click entry point used by the Windows one-folder build."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _restart_in_project_venv() -> int | None:
    """Use the project environment when the source launcher is double-clicked."""
    if getattr(sys, "frozen", False):
        return None
    venv_python = Path(__file__).resolve().parent / ".venv" / "Scripts" / "python.exe"
    if not venv_python.is_file() or Path(sys.executable).resolve() == venv_python.resolve():
        return None
    return subprocess.call([str(venv_python), str(Path(__file__).resolve())])


if __name__ == "__main__":
    exit_code = _restart_in_project_venv()
    if exit_code is not None:
        raise SystemExit(exit_code)
    from app.main import run_app

    run_app(open_browser=True)
