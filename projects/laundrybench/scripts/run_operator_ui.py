#!/usr/bin/env python3
"""Launch the local Phosphobot operator dashboard with LaundryBench defaults."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

DEFAULT_PORT = 8020
DEFAULT_MAX_OPENCV_INDEX = 2


def build_command(
    executable: str,
    *,
    port: int = DEFAULT_PORT,
    max_opencv_index: int = DEFAULT_MAX_OPENCV_INDEX,
) -> list[str]:
    """Build the local-only, camera-bounded Phosphobot command."""

    return [
        executable,
        "run",
        "--host=127.0.0.1",
        f"--port={port}",
        f"--max-opencv-index={max_opencv_index}",
        "--no-can",
        "--no-realsense",
        "--no-telemetry",
    ]


def _dashboard_is_ready(url: str) -> bool:
    try:
        with urlopen(url, timeout=1) as response:
            return response.status == 200
    except (OSError, URLError):
        return False


def _wait_for_dashboard(url: str, timeout_s: float = 180.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if _dashboard_is_ready(url):
            return True
        time.sleep(0.5)
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Start the Phosphobot browser dashboard for the two SO-101 arms "
            "and the two USB cameras."
        )
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("LAUNDRYBENCH_OPERATOR_PORT", DEFAULT_PORT)),
        help=f"localhost port (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--max-opencv-index",
        type=int,
        default=int(
            os.environ.get(
                "LAUNDRYBENCH_OPERATOR_MAX_OPENCV_INDEX",
                DEFAULT_MAX_OPENCV_INDEX,
            )
        ),
        help=(
            "exclusive upper bound for OpenCV camera indexes; 2 searches only "
            "indexes 0 and 1 (default)"
        ),
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="open the dashboard in the default macOS browser after startup",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the command without starting the service",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    executable = shutil.which("phosphobot")
    if executable is None:
        print(
            "phosphobot is not installed. Install it with: "
            "brew install phospho-app/phosphobot/phosphobot",
            file=sys.stderr,
        )
        return 2
    if args.port < 1 or args.port > 65535:
        print("--port must be between 1 and 65535", file=sys.stderr)
        return 2
    if args.max_opencv_index < 1:
        print("--max-opencv-index must be at least 1", file=sys.stderr)
        return 2

    command = build_command(
        executable,
        port=args.port,
        max_opencv_index=args.max_opencv_index,
    )
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Starting operator dashboard at {url}")
    print(f"Command: {shlex.join(command)}")
    print(
        "The dashboard connects to hardware only after the arms are attached; "
        "do not start leader control until the operator safety check is complete."
    )
    if args.dry_run:
        return 0

    process = subprocess.Popen(command)
    try:
        if args.open_browser:
            if _wait_for_dashboard(url):
                subprocess.run(["open", url], check=False)
            else:
                print(
                    f"Dashboard did not respond within 180 seconds; open {url} manually.",
                    file=sys.stderr,
                )
        return process.wait()
    except KeyboardInterrupt:
        process.send_signal(signal.SIGINT)
        return process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
