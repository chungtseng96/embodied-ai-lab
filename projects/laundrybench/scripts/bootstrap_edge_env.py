"""Create the pinned native SO-101 edge environment with uv."""

from __future__ import annotations

import argparse
import shlex
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REQUIREMENTS = (
    ROOT / "projects" / "laundrybench" / "requirements" / "edge-macos-x86_64.lock.txt"
)
DEFAULT_VENV = ROOT / ".venv-lerobot-edge"
LEROBOT_VERSION = "0.6.1"


def _run(command: list[str]) -> None:
    print(f"$ {shlex.join(command)}", flush=True)
    subprocess.run(command, check=True, cwd=ROOT)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build the pinned Intel-macOS edge environment used for SO-101 "
            "serial, camera, recording, and rollout checks."
        )
    )
    parser.add_argument(
        "--venv",
        type=Path,
        default=DEFAULT_VENV,
        help="target virtual environment (default: %(default)s)",
    )
    parser.add_argument(
        "--requirements",
        type=Path,
        default=DEFAULT_REQUIREMENTS,
        help="exact uv requirements file (default: %(default)s)",
    )
    parser.add_argument(
        "--python",
        default="3.12",
        dest="python_version",
        help="Python version passed to uv venv (default: %(default)s)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("uv is required; install it before bootstrapping the edge environment")

    requirements = args.requirements.expanduser().resolve()
    venv = args.venv.expanduser().resolve()
    if not requirements.is_file():
        raise SystemExit(f"requirements file does not exist: {requirements}")

    python = venv / "bin" / "python"
    if python.is_file():
        print(f"Reusing existing virtual environment: {venv}", flush=True)
    else:
        if venv.exists():
            raise SystemExit(
                f"target exists but is not a complete virtual environment: {venv}; "
                "choose another path or repair it explicitly"
            )
        _run([uv, "venv", "--python", args.python_version, str(venv)])
        if not python.is_file():
            raise SystemExit(f"uv did not create the expected Python executable: {python}")

    _run([uv, "pip", "install", "--python", str(python), "--requirement", str(requirements)])
    _run(
        [
            uv,
            "pip",
            "install",
            "--python",
            str(python),
            "--no-deps",
            f"lerobot=={LEROBOT_VERSION}",
        ]
    )
    _run(
        [
            uv,
            "pip",
            "install",
            "--python",
            str(python),
            "--no-deps",
            "--editable",
            str(ROOT / "projects" / "laundrybench"),
        ]
    )
    print(f"Edge environment ready: {python}", flush=True)
    print("Run: make host-check PYTHON=... and make lerobot-check PYTHON=...", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
