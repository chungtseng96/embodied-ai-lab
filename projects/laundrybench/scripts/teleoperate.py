"""Dry-run-first adapter to LeRobot's native SO-101 teleoperation loop."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from laundrybench.data.recording import RecordingConfigError
from laundrybench.data.teleoperation import (
    TeleoperationConfig,
    load_teleoperation_config,
    validate_teleoperation_calibration_files,
)

PINNED_LEROBOT_VERSION = "0.6.1"
LEROBOT_MODULE = "lerobot.scripts.lerobot_teleoperate"


def build_command(config: TeleoperationConfig) -> list[str]:
    """Build a shell-free argv using LeRobot's v0.6.1 module entry point."""
    cameras = {
        name: {
            "type": "opencv",
            "index_or_path": camera.index_or_path,
            "width": camera.width,
            "height": camera.height,
            "fps": camera.fps,
            "color_mode": "rgb",
            "rotation": camera.rotation,
        }
        for name, camera in config.cameras.items()
    }
    return [
        str(config.lerobot_python),
        "-m",
        LEROBOT_MODULE,
        "--robot.type=so101_follower",
        f"--robot.port={config.follower_port}",
        f"--robot.id={config.follower_id}",
        "--robot.use_degrees=false",
        f"--robot.cameras={json.dumps(cameras, separators=(',', ':'))}",
        "--teleop.type=so101_leader",
        f"--teleop.port={config.leader_port}",
        f"--teleop.id={config.leader_id}",
        "--teleop.use_degrees=false",
        f"--fps={config.control_fps}",
        f"--display_data={str(config.display_data).lower()}",
        f"--display_mode={config.display_mode}",
        f"--teleop_time_s={config.duration_s:g}",
    ]


def probe_lerobot(python: Path) -> tuple[str | None, bool]:
    """Inspect the selected Python environment without importing robot drivers."""
    script = (
        "import importlib.metadata, importlib.util, json; "
        "print(json.dumps({'version': importlib.metadata.version('lerobot'), "
        f"'module': importlib.util.find_spec('{LEROBOT_MODULE}') is not None}}))"
    )
    result = subprocess.run(
        [str(python), "-c", script], check=False, capture_output=True, text=True, timeout=20
    )
    if result.returncode:
        return None, False
    try:
        answer = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return None, False
    return answer.get("version"), answer.get("module") is True


def execute_teleoperation(
    config: TeleoperationConfig,
    command: list[str],
    *,
    version_probe: Callable[[Path], tuple[str | None, bool]] = probe_lerobot,
    popen_factory: Callable[..., Any] = subprocess.Popen,
) -> int:
    """Run one explicitly supervised, bounded teleoperation session."""
    try:
        validate_teleoperation_calibration_files(config)
        if not config.lerobot_python.is_file() or not os.access(config.lerobot_python, os.X_OK):
            raise RecordingConfigError(
                f"selected LeRobot Python is not executable: {config.lerobot_python}"
            )
        version, module_available = version_probe(config.lerobot_python)
        if version != config.lerobot_version or version != PINNED_LEROBOT_VERSION:
            raise RecordingConfigError(
                f"LeRobot version {version!r} does not match pinned {PINNED_LEROBOT_VERSION}"
            )
        if not module_available:
            raise RecordingConfigError(f"selected environment has no {LEROBOT_MODULE} module")
        environment = {
            **os.environ,
            "HF_LEROBOT_HOME": str(config.lerobot_home),
            "PATH": f"{config.lerobot_python.parent}:{os.environ.get('PATH', '')}",
        }
        process_options: dict[str, Any] = {"shell": False, "env": environment}
        if os.name == "posix":
            process_options["start_new_session"] = True
        process = popen_factory(command, **process_options)
        try:
            return process.wait()
        except KeyboardInterrupt:
            _stop_process_group(process)
            return 130
    except (OSError, subprocess.SubprocessError, RecordingConfigError) as exc:
        print(f"teleoperation refused: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/teleoperation.example.yaml"),
        help="strict teleoperation YAML (default: configs/teleoperation.example.yaml)",
    )
    parser.add_argument("--execute", action="store_true", help="launch LeRobot teleoperation")
    parser.add_argument(
        "--supervised",
        action="store_true",
        help="confirm an operator is present with stop access",
    )
    args = parser.parse_args(argv)
    if args.execute and not args.supervised:
        parser.error("--execute requires --supervised")
    if args.execute and not sys.stdin.isatty():
        parser.error("--execute requires an interactive terminal")
    if args.execute and os.name == "posix":
        try:
            if os.tcgetpgrp(sys.stdin.fileno()) != os.getpgrp():
                parser.error("--execute requires the foreground terminal process group")
        except OSError as exc:
            parser.error(f"cannot verify foreground terminal: {exc}")
    try:
        config = load_teleoperation_config(args.config)
        command = build_command(config)
    except RecordingConfigError as exc:
        parser.error(str(exc))
    if args.execute:
        print("SUPERVISED PHYSICAL TELEOPERATION TARGET:")
        print(
            json.dumps(
                {
                    "follower_port": config.follower_port,
                    "follower_id": config.follower_id,
                    "leader_port": config.leader_port,
                    "leader_id": config.leader_id,
                    "cameras": {
                        name: {
                            "index_or_path": camera.index_or_path,
                            "width": camera.width,
                            "height": camera.height,
                            "fps": camera.fps,
                            "rotation": camera.rotation,
                        }
                        for name, camera in config.cameras.items()
                    },
                    "duration_s": config.duration_s,
                    "display_mode": config.display_mode,
                },
                indent=2,
                sort_keys=True,
            )
        )
        print("Exact argv:")
        print(json.dumps(command, indent=2))
        return execute_teleoperation(config, command)
    print(json.dumps({"mode": "dry-run", "command": command, "shell": False}, indent=2))
    return 0


def _stop_process_group(process: Any) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGINT)
        else:
            process.send_signal(signal.SIGINT)
        process.wait(timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGTERM)
            else:
                process.terminate()
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            try:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
            except OSError:
                pass
            process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
