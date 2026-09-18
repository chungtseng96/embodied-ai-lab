"""Report local tools relevant to LaundryBench and SO-101 preparation."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

MIN_PYTHON = (3, 12)


def _executable(command: str) -> str | None:
    candidates = [
        shutil.which(command),
        str(Path(sys.executable).with_name(command)),
        str(Path.home() / ".local" / "bin" / command),
    ]
    return next((candidate for candidate in candidates if candidate and Path(candidate).exists()), None)


def _run(command: list[str], timeout: int = 8) -> dict[str, object]:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return {"available": False, "detail": str(error)}

    output = (result.stdout or result.stderr).strip()
    return {
        "available": result.returncode == 0,
        "returncode": result.returncode,
        "detail": output.splitlines()[0] if output else "",
    }


def _tool(command: str, *args: str) -> dict[str, object]:
    executable = _executable(command)
    if executable is None:
        return {"available": False, "detail": "not found"}

    status = _run([executable, *(args or ("--version",))])
    status["path"] = executable
    return status


def main() -> None:
    docker = _tool("docker")
    docker_daemon = {"available": False, "detail": "Docker client missing"}
    if docker.get("available") and docker.get("path"):
        docker_daemon = _run([docker["path"], "info"])
        if not docker_daemon.get("available"):
            desktop_status = _run([docker["path"], "--context", "desktop-linux", "info"])
            if desktop_status.get("available"):
                desktop_status["context"] = "desktop-linux"
                docker_daemon = desktop_status

    status = {
        "host": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "python_executable": sys.executable,
            "python_3_12_or_newer": sys.version_info >= MIN_PYTHON,
        },
        "tools": {
            "docker": docker,
            "docker_daemon": docker_daemon,
            "docker-compose": _tool("docker-compose"),
            "uv": _tool("uv"),
            "ffmpeg": _tool("ffmpeg"),
            "git-lfs": _tool("git-lfs"),
            "hf": _tool("hf"),
            "lelab": _tool("lelab"),
            "lerobot-info": _tool("lerobot-info"),
        },
        "notes": [
            "Docker daemon access is required for local image smoke tests.",
            "LeLab is optional; the repository CLI workflow remains canonical.",
            "Intel macOS is not the target for CUDA training.",
        ],
    }

    print(json.dumps(status, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
