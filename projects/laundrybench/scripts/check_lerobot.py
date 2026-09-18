"""Check whether this environment is ready for a LeRobot POC."""

from __future__ import annotations

import importlib
import json
import platform
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path

MIN_PYTHON = (3, 12)


def _command_version(command: str) -> str | None:
    executable = shutil.which(command)
    if executable is None:
        sibling = Path(sys.executable).with_name(command)
        executable = str(sibling) if sibling.exists() else None

    if executable is None:
        return None

    try:
        result = subprocess.run(
            [executable, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "present, but version check failed"

    output = (result.stdout or result.stderr).strip()
    return output or "present"


def main() -> None:
    lerobot_available = importlib.util.find_spec("lerobot") is not None
    status = {
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
            "meets_lerobot_docs_minimum": sys.version_info >= MIN_PYTHON,
        },
        "lerobot": {
            "importable": lerobot_available,
            "version": metadata.version("lerobot") if lerobot_available else None,
        },
        "tools": {
            "ffmpeg": _command_version("ffmpeg"),
            "lerobot-info": _command_version("lerobot-info"),
        },
    }

    print(json.dumps(status, indent=2), flush=True)

    if not status["python"]["meets_lerobot_docs_minimum"]:
        raise SystemExit(
            "LeRobot POC check failed: create a Python 3.12 environment before installing LeRobot."
        )

    if not lerobot_available:
        raise SystemExit("LeRobot POC check failed: install LeRobot with `python -m pip install lerobot`.")


if __name__ == "__main__":
    main()
