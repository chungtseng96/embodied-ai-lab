#!/usr/bin/env python3
"""Launch the pinned LeLab operator UI beside an existing LeRobot environment.

LeLab is installed in its own environment because its web dependencies and
frontend are separate from LaundryBench.  On the current Intel macOS host,
the LeLab compatibility build uses the already validated LeRobot 0.6.1
environment through ``PYTHONPATH``; it does not replace that environment's
LeRobot or Torch packages.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PINNED_LEROBOT_VERSION = "0.6.1"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LELAB_PYTHON = PROJECT_ROOT / ".venv-lelab" / "bin" / "python"
DEFAULT_LEROBOT_PYTHON = PROJECT_ROOT / ".venv-lerobot" / "bin" / "python"
DEFAULT_LEROBOT_HOME = Path.home() / ".cache" / "huggingface" / "lerobot"


def build_command(
    lelab_executable: Path, *, no_open: bool = False, stop: bool = False
) -> list[str]:
    """Build the shell-free LeLab launcher command."""
    command = [str(lelab_executable)]
    if stop:
        command.append("--stop")
    elif no_open:
        command.append("--no-open")
    return command


def probe_lerobot(python: Path) -> tuple[str | None, Path | None]:
    """Return the selected LeRobot version and its import directory."""
    script = (
        "import importlib.metadata, sysconfig; "
        "print(importlib.metadata.version('lerobot')); "
        "print(sysconfig.get_paths()['purelib'])"
    )
    try:
        result = subprocess.run(
            [str(python), "-c", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None, None
    if result.returncode:
        return None, None
    lines = result.stdout.strip().splitlines()
    if len(lines) != 2:
        return None, None
    return lines[0].strip(), Path(lines[1].strip())


def build_environment(
    base: dict[str, str], *, lerobot_site: Path, lerobot_home: Path
) -> dict[str, str]:
    """Make LeRobot importable to LeLab without copying or modifying it."""
    environment = dict(base)
    pythonpath = [str(lerobot_site)]
    if existing := environment.get("PYTHONPATH"):
        pythonpath.append(existing)
    environment["PYTHONPATH"] = os.pathsep.join(pythonpath)
    environment["HF_LEROBOT_HOME"] = str(lerobot_home)
    return environment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lelab-python",
        type=Path,
        default=Path(os.environ.get("LAUNDRYBENCH_LELAB_PYTHON", DEFAULT_LELAB_PYTHON)),
        help="Python executable in the LeLab environment",
    )
    parser.add_argument(
        "--lerobot-python",
        type=Path,
        default=Path(os.environ.get("LAUNDRYBENCH_LEROBOT_PYTHON", DEFAULT_LEROBOT_PYTHON)),
        help="Python executable in the validated LeRobot environment",
    )
    parser.add_argument(
        "--lerobot-home",
        type=Path,
        default=Path(
            os.environ.get("HF_LEROBOT_HOME", DEFAULT_LEROBOT_HOME)
        ).expanduser(),
        help="LeRobot cache/calibration root",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="start the server without opening a browser",
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="stop LeLab processes on its localhost ports and exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the launch environment and command without starting LeLab",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    lelab_python_path = args.lelab_python.expanduser()
    lelab_executable = lelab_python_path.parent / "lelab"
    lelab_python = lelab_python_path
    lerobot_python = args.lerobot_python.expanduser()
    lerobot_home = args.lerobot_home.expanduser().resolve()

    if not lelab_python_path.is_file() or not os.access(lelab_python_path, os.X_OK):
        print(f"LeLab Python is not executable: {lelab_python_path}", file=sys.stderr)
        return 2
    if not lelab_executable.is_file() or not os.access(lelab_executable, os.X_OK):
        print(f"LeLab launcher is not executable: {lelab_executable}", file=sys.stderr)
        return 2

    version, lerobot_site = probe_lerobot(lerobot_python)
    if version != PINNED_LEROBOT_VERSION or lerobot_site is None:
        print(
            f"selected LeRobot environment reports {version!r}; "
            f"expected {PINNED_LEROBOT_VERSION!r}: {lerobot_python}",
            file=sys.stderr,
        )
        return 2

    environment = build_environment(
        dict(os.environ), lerobot_site=lerobot_site, lerobot_home=lerobot_home
    )
    command = build_command(lelab_executable, no_open=args.no_open, stop=args.stop)
    print("LeLab UI: http://127.0.0.1:8000")
    print(f"LeLab Python: {lelab_python}")
    print(f"LeRobot Python: {lerobot_python} ({version})")
    print(f"LeRobot home: {lerobot_home}")
    print(f"Command: {' '.join(command)}")
    if args.dry_run:
        print(f"PYTHONPATH: {environment['PYTHONPATH']}")
        return 0

    return subprocess.run(command, env=environment, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
