"""Strict configuration helpers for supervised SO-101 teleoperation."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from laundrybench.data.recording import RecordingConfigError

SUPPORTED_CAMERA_ROTATIONS = (0, 90, 180, 270)


@dataclass(frozen=True)
class TeleoperationCamera:
    """One OpenCV camera used for live operator observability."""

    index_or_path: int | str
    width: int
    height: int
    fps: int
    rotation: int


@dataclass(frozen=True)
class TeleoperationConfig:
    """Validated inputs for one bounded, supervised teleoperation session."""

    follower_port: str
    follower_id: str
    follower_calibration_file: Path
    leader_port: str
    leader_id: str
    leader_calibration_file: Path
    cameras: dict[str, TeleoperationCamera]
    control_fps: int
    duration_s: float
    display_data: bool
    display_mode: str
    lerobot_python: Path
    lerobot_home: Path
    lerobot_version: str


def load_teleoperation_config(path: Path) -> TeleoperationConfig:
    """Read the exact-key teleoperation YAML; relative paths resolve from its directory."""
    path = Path(path)
    if not path.is_file():
        raise RecordingConfigError(f"missing teleoperation config: {path}")
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RecordingConfigError(f"{path}: cannot read teleoperation YAML: {exc}") from exc
    if not isinstance(value, dict) or set(value) != {"teleoperation"}:
        raise RecordingConfigError(f"{path.name}: expected only top-level key 'teleoperation'")
    data = value["teleoperation"]
    if not isinstance(data, dict):
        raise RecordingConfigError(f"{path.name}: key 'teleoperation' must be a mapping")
    _keys(
        data,
        {
            "follower_port",
            "follower_id",
            "follower_calibration_file",
            "leader_port",
            "leader_id",
            "leader_calibration_file",
            "cameras",
            "fps",
            "duration_s",
            "display_data",
            "display_mode",
            "lerobot",
        },
        "teleoperation",
    )
    lerobot = _section(data["lerobot"], "teleoperation.lerobot", {"python", "home", "version"})
    cameras_value = data["cameras"]
    if not isinstance(cameras_value, dict) or not cameras_value:
        raise RecordingConfigError("teleoperation.cameras must be a nonempty mapping")
    cameras: dict[str, TeleoperationCamera] = {}
    for name, raw_camera in cameras_value.items():
        camera_name = _identity(name, "teleoperation camera name")
        camera = _section(
            raw_camera, camera_name, {"index_or_path", "width", "height", "fps", "rotation"}
        )
        cameras[camera_name] = TeleoperationCamera(
            index_or_path=_camera_index(
                camera["index_or_path"], f"cameras.{camera_name}.index_or_path"
            ),
            width=_positive_int(camera["width"], f"cameras.{camera_name}.width"),
            height=_positive_int(camera["height"], f"cameras.{camera_name}.height"),
            fps=_positive_int(camera["fps"], f"cameras.{camera_name}.fps"),
            rotation=_rotation(camera["rotation"], f"cameras.{camera_name}.rotation"),
        )
    config = TeleoperationConfig(
        follower_port=_nonempty(data["follower_port"], "follower_port"),
        follower_id=_identity(data["follower_id"], "follower_id"),
        follower_calibration_file=_path(
            data["follower_calibration_file"], path.parent, "follower_calibration_file"
        ),
        leader_port=_nonempty(data["leader_port"], "leader_port"),
        leader_id=_identity(data["leader_id"], "leader_id"),
        leader_calibration_file=_path(
            data["leader_calibration_file"], path.parent, "leader_calibration_file"
        ),
        cameras=cameras,
        control_fps=_positive_int(data["fps"], "fps"),
        duration_s=_positive_float(data["duration_s"], "duration_s"),
        display_data=_bool(data["display_data"], "display_data"),
        display_mode=_display_mode(data["display_mode"]),
        lerobot_python=_executable_path(lerobot["python"], path.parent, "lerobot.python"),
        lerobot_home=_path(lerobot["home"], path.parent, "lerobot.home"),
        lerobot_version=_nonempty(lerobot["version"], "lerobot.version"),
    )
    if config.follower_port == config.leader_port:
        raise RecordingConfigError("follower_port and leader_port must be distinct")
    if config.follower_id == config.leader_id:
        raise RecordingConfigError("follower_id and leader_id must be distinct")
    for name, camera in config.cameras.items():
        if camera.fps < config.control_fps:
            raise RecordingConfigError(f"cameras.{name}.fps must be at least teleoperation.fps")
    return config


def validate_teleoperation_calibration_files(config: TeleoperationConfig) -> None:
    """Require readable ID-matched calibration files at LeRobot's selected paths."""
    configured_home = os.environ.get("HF_LEROBOT_HOME")
    active_home = (
        Path(configured_home).expanduser().resolve() if configured_home else config.lerobot_home
    )
    if active_home != config.lerobot_home:
        raise RecordingConfigError(
            "configured LeRobot home "
            f"{config.lerobot_home} differs from HF_LEROBOT_HOME {active_home}"
        )
    expected_paths = (
        (
            "follower",
            config.follower_id,
            config.follower_calibration_file,
            config.lerobot_home / "calibration/robots/so_follower" / f"{config.follower_id}.json",
        ),
        (
            "leader",
            config.leader_id,
            config.leader_calibration_file,
            config.lerobot_home
            / "calibration/teleoperators/so_leader"
            / f"{config.leader_id}.json",
        ),
    )
    for role, device_id, calibration, expected_path in expected_paths:
        if calibration != expected_path.resolve():
            raise RecordingConfigError(
                f"{role} calibration path must be LeRobot's ID lookup path: {expected_path}"
            )
        if calibration.stem != device_id:
            raise RecordingConfigError(
                f"{role} calibration filename {calibration.name!r} does not match ID {device_id!r}"
            )
        try:
            parsed = json.loads(calibration.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RecordingConfigError(
                f"{role} calibration is not readable JSON: {calibration}"
            ) from exc
        if not isinstance(parsed, dict) or not parsed:
            raise RecordingConfigError(
                f"{role} calibration must contain a nonempty JSON object: {calibration}"
            )


def _keys(data: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = set(data) - allowed
    missing = allowed - set(data)
    if unknown:
        raise RecordingConfigError(f"{where}: unknown key {min(unknown)!r}")
    if missing:
        raise RecordingConfigError(f"{where}: missing key {min(missing)!r}")


def _section(value: object, name: str, allowed: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RecordingConfigError(f"{name} must be a mapping")
    _keys(value, allowed, name)
    return value


def _path(value: object, base: Path, name: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise RecordingConfigError(f"{name} must be a nonempty path string")
    candidate = Path(value).expanduser()
    return (candidate if candidate.is_absolute() else base / candidate).resolve()


def _executable_path(value: object, base: Path, name: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise RecordingConfigError(f"{name} must be a nonempty executable path")
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate.absolute()


def _nonempty(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "<" in value or ">" in value:
        raise RecordingConfigError(f"{name} must be a concrete nonempty string")
    return value.strip()


def _identity(value: object, name: str) -> str:
    result = _nonempty(value, name)
    if any(char.isspace() for char in result):
        raise RecordingConfigError(f"{name} cannot contain whitespace")
    return result


def _camera_index(value: object, name: str) -> int | str:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise RecordingConfigError(f"{name} must be an integer or nonempty path")
    if isinstance(value, str) and not value.strip():
        raise RecordingConfigError(f"{name} must be an integer or nonempty path")
    return value


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise RecordingConfigError(f"{name} must be a positive integer")
    return value


def _positive_float(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise RecordingConfigError(f"{name} must be a positive number")
    return float(value)


def _rotation(value: object, name: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value not in SUPPORTED_CAMERA_ROTATIONS
    ):
        allowed = ", ".join(str(item) for item in SUPPORTED_CAMERA_ROTATIONS)
        raise RecordingConfigError(f"{name} must be one of: {allowed}")
    return value


def _bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise RecordingConfigError(f"{name} must be a boolean")
    return value


def _display_mode(value: object) -> str:
    result = _identity(value, "display_mode")
    if result != "rerun":
        raise RecordingConfigError("display_mode must be 'rerun'")
    return result
