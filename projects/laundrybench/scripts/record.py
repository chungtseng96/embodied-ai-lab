"""Dry-run-first adapter to LeRobot's native SO-101 dataset recorder."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from laundrybench.data.recording import (
    DATASET_IDENTITY_CONTRACT,
    RecordingConfig,
    RecordingConfigError,
    dataset_content_identity,
    load_recording_config,
    validate_calibration_files,
    validate_dataset_metadata,
)

PINNED_LEROBOT_VERSION = "0.6.1"
LEROBOT_MODULE = "lerobot.scripts.lerobot_record"


def build_command(config: RecordingConfig) -> list[str]:
    """Build a shell-free argv using LeRobot's v0.6.1 module entry point."""
    camera = {
        config.camera_name: {
            "type": "opencv",
            "index_or_path": config.camera_index_or_path,
            "width": config.camera_width,
            "height": config.camera_height,
            "fps": config.camera_fps,
            "color_mode": "rgb",
        }
    }
    return [
        str(config.lerobot_python),
        "-m",
        LEROBOT_MODULE,
        "--robot.type=so101_follower",
        f"--robot.port={config.follower_port}",
        f"--robot.id={config.follower_id}",
        "--robot.use_degrees=false",
        f"--robot.cameras={json.dumps(camera, separators=(',', ':'))}",
        "--teleop.type=so101_leader",
        f"--teleop.port={config.leader_port}",
        f"--teleop.id={config.leader_id}",
        "--teleop.use_degrees=false",
        f"--dataset.repo_id={config.dataset_repo_id}",
        f"--dataset.root={config.dataset_root}",
        f"--dataset.fps={config.dataset_fps}",
        f"--dataset.num_episodes={config.episodes}",
        f"--dataset.episode_time_s={config.episode_time_s:g}",
        f"--dataset.reset_time_s={config.reset_time_s:g}",
        f"--dataset.single_task={config.task}",
        "--dataset.push_to_hub=false",
        "--resume=false",
        "--display_data=false",
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


def make_manifest(config: RecordingConfig, command: list[str]) -> dict[str, Any]:
    now = _now()
    return {
        "schema_version": 1,
        "status": "planned",
        "created_at": now,
        "updated_at": now,
        "command": command,
        "shell": False,
        "lerobot": {
            "pinned_version": config.lerobot_version,
            "observed_version": None,
            "module": LEROBOT_MODULE,
            "module_available": None,
        },
        "robot": {
            "type": "so101_follower",
            "port": config.follower_port,
            "id": config.follower_id,
            "use_degrees": False,
            "calibration_file": str(config.follower_calibration_file),
        },
        "teleoperator": {
            "type": "so101_leader",
            "port": config.leader_port,
            "id": config.leader_id,
            "use_degrees": False,
            "calibration_file": str(config.leader_calibration_file),
        },
        "camera": {
            "name": config.camera_name,
            "index_or_path": config.camera_index_or_path,
            "width": config.camera_width,
            "height": config.camera_height,
            "fps": config.camera_fps,
            "color_mode": "RGB",
        },
        "dataset": {
            "dataset_id": None,
            "dataset_id_contract": DATASET_IDENTITY_CONTRACT,
            "repo_id_requested": config.dataset_repo_id,
            "repo_id_effective": None,
            "root": str(config.dataset_root),
            "manifest_path": str(config.manifest_path),
            "upload_enabled": False,
            "episodes_requested": config.episodes,
            "fps": config.dataset_fps,
            "episode_time_s": config.episode_time_s,
            "reset_time_s": config.reset_time_s,
            "task": config.task,
            "act_io_contract": None,
            "meta_info_sha256": None,
            "metadata_validation_error": None,
            "content_identity_error": None,
        },
        "supervision": {"operator_confirmed": False},
        "return_code": None,
        "error": None,
    }


def execute_recording(
    config: RecordingConfig,
    command: list[str],
    manifest: dict[str, Any],
    *,
    version_probe: Callable[[Path], tuple[str | None, bool]] = probe_lerobot,
    popen_factory: Callable[..., Any] = subprocess.Popen,
) -> int:
    """Run one explicitly supervised recording and persist lifecycle state."""
    _write_manifest(config.manifest_path, manifest, permit_planned=True)
    try:
        validate_calibration_files(config)
        if not config.lerobot_python.is_file() or not os.access(config.lerobot_python, os.X_OK):
            raise RecordingConfigError(
                f"selected LeRobot Python is not executable: {config.lerobot_python}"
            )
        version, module_available = version_probe(config.lerobot_python)
        manifest["lerobot"]["observed_version"] = version
        manifest["lerobot"]["module_available"] = module_available
        if version != config.lerobot_version or version != PINNED_LEROBOT_VERSION:
            raise RecordingConfigError(
                f"LeRobot version {version!r} does not match pinned {PINNED_LEROBOT_VERSION}"
            )
        if not module_available:
            raise RecordingConfigError(f"selected environment has no {LEROBOT_MODULE} module")
        if config.dataset_root.exists():
            raise RecordingConfigError(
                f"dataset root already exists; refusing overwrite: {config.dataset_root}"
            )
        config.dataset_root.parent.mkdir(parents=True, exist_ok=True)
        manifest["supervision"]["operator_confirmed"] = True
        manifest["status"] = "running"
        manifest["started_at"] = _now()
        _write_manifest(config.manifest_path, manifest, permit_planned=True)
        old_sigterm = signal.getsignal(signal.SIGTERM)

        def stop_on_term(signum: int, frame: Any) -> None:
            raise _StopRequested(f"received signal {signum}")

        signal.signal(signal.SIGTERM, stop_on_term)
        process = None
        terminal_fd = None
        foreground_pgid = None
        try:
            process_options: dict[str, Any] = {"shell": False}
            if os.name == "posix":
                process_options["process_group"] = 0
            process = popen_factory(
                command,
                env={**os.environ, "HF_LEROBOT_HOME": str(config.lerobot_home)},
                **process_options,
            )
            if os.name == "posix" and sys.stdin.isatty():
                terminal_fd = sys.stdin.fileno()
                foreground_pgid = os.tcgetpgrp(terminal_fd)
                os.tcsetpgrp(terminal_fd, process.pid)
            return_code = process.wait()
        except (KeyboardInterrupt, _StopRequested) as exc:
            if process is not None:
                _stop_process_group(process)
            manifest["status"] = "failed"
            manifest["error"] = f"{exc or 'interrupted by operator'}; child process group stopped"
            manifest["return_code"] = 130
            return_code = 130
        finally:
            if terminal_fd is not None and foreground_pgid is not None:
                _restore_terminal_foreground(terminal_fd, foreground_pgid)
            signal.signal(signal.SIGTERM, old_sigterm)
        manifest["return_code"] = return_code
        if return_code == 0:
            manifest["status"] = "completed"
            manifest["completed_at"] = _now()
            try:
                manifest["dataset"]["dataset_id"] = dataset_content_identity(config.dataset_root)
            except RecordingConfigError as exc:
                manifest["dataset"]["content_identity_error"] = str(exc)
            try:
                info_path = config.dataset_root / "meta" / "info.json"
                info_bytes = info_path.read_bytes()
                manifest["dataset"]["meta_info_sha256"] = hashlib.sha256(info_bytes).hexdigest()
                info = json.loads(info_bytes)
                for key in ("repo_id", "dataset_repo_id", "id"):
                    if isinstance(info.get(key), str) and info[key]:
                        manifest["dataset"]["repo_id_effective"] = info[key]
                        break
            except (OSError, json.JSONDecodeError, RecordingConfigError) as exc:
                manifest["dataset"]["metadata_validation_error"] = str(exc)
            try:
                manifest["dataset"]["act_io_contract"] = validate_dataset_metadata(
                    config.dataset_root,
                    config.camera_name,
                    config.dataset_fps,
                    config.camera_width,
                    config.camera_height,
                )
            except RecordingConfigError as exc:
                manifest["dataset"]["metadata_validation_error"] = str(exc)
        elif manifest["status"] != "failed":
            manifest["status"] = "failed"
            manifest["error"] = f"LeRobot recorder exited with status {return_code}"
        return return_code
    except (OSError, subprocess.SubprocessError, RecordingConfigError) as exc:
        manifest["status"] = "failed"
        manifest["error"] = str(exc)
        manifest["failed_at"] = _now()
        return_code = 1
        return return_code
    finally:
        manifest["updated_at"] = _now()
        _write_manifest(config.manifest_path, manifest, permit_planned=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/recording.example.yaml"),
        help="strict recording YAML (default: configs/recording.example.yaml)",
    )
    parser.add_argument("--execute", action="store_true", help="launch LeRobot recording")
    parser.add_argument(
        "--supervised",
        action="store_true",
        help="confirm an operator is present at the follower with stop access",
    )
    args = parser.parse_args(argv)
    if args.execute and not args.supervised:
        parser.error("--execute requires --supervised")
    if args.execute and not sys.stdin.isatty():
        parser.error("--execute requires an interactive terminal for LeRobot recording controls")
    if args.execute and os.name == "posix":
        try:
            if os.tcgetpgrp(sys.stdin.fileno()) != os.getpgrp():
                parser.error("--execute requires the foreground terminal process group")
        except OSError as exc:
            parser.error(f"cannot verify foreground terminal: {exc}")
    try:
        config = load_recording_config(args.config)
        command = build_command(config)
        manifest = make_manifest(config, command)
        if args.execute:
            print("SUPERVISED PHYSICAL RECORDING TARGET:")
            print(
                json.dumps(
                    {
                        "follower_port": config.follower_port,
                        "follower_id": config.follower_id,
                        "leader_port": config.leader_port,
                        "leader_id": config.leader_id,
                        "camera": manifest["camera"],
                        "dataset_root": str(config.dataset_root),
                        "episodes": config.episodes,
                        "upload_enabled": False,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            print("Exact argv:")
            print(json.dumps(command, indent=2))
            return execute_recording(config, command, manifest)
        print(
            json.dumps(
                {
                    "mode": "dry-run",
                    "command": command,
                    "shell": False,
                    "manifest_path": str(config.manifest_path),
                    "manifest_status": "planned",
                },
                indent=2,
            )
        )
        _write_manifest(config.manifest_path, manifest, permit_planned=True)
        return 0
    except RecordingConfigError as exc:
        parser.error(str(exc))
    return 2


def _write_manifest(path: Path, manifest: dict[str, Any], *, permit_planned: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise RecordingConfigError(f"refusing to replace unreadable manifest: {path}")
        replaceable = {"planned", "running"} if permit_planned else set()
        if existing.get("status") not in replaceable:
            raise RecordingConfigError(f"manifest already exists and is not a planned run: {path}")
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


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


def _restore_terminal_foreground(fd: int, process_group: int) -> None:
    """Restore the parent foreground group without stopping it with SIGTTOU."""
    old_sigttou = signal.getsignal(signal.SIGTTOU)
    signal.signal(signal.SIGTTOU, signal.SIG_IGN)
    try:
        os.tcsetpgrp(fd, process_group)
    finally:
        signal.signal(signal.SIGTTOU, old_sigttou)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class _StopRequested(Exception):
    """Internal control-flow exception used to stop children on SIGTERM."""


if __name__ == "__main__":
    raise SystemExit(main())
