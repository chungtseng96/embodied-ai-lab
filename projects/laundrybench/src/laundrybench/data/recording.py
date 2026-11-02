"""Strict configuration and metadata helpers for native LeRobot recording."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from laundrybench.robot.so101_spec import SO101_JOINT_NAMES

DATASET_IDENTITY_CONTRACT = "dataset-tree-sha256-v1"


class RecordingConfigError(ValueError):
    """A recording config is missing, malformed, or unsafe to execute."""


@dataclass(frozen=True)
class RecordingConfig:
    follower_port: str
    follower_id: str
    follower_calibration_file: Path
    leader_port: str
    leader_id: str
    leader_calibration_file: Path
    camera_name: str
    camera_index_or_path: int | str
    camera_width: int
    camera_height: int
    camera_fps: int
    dataset_repo_id: str
    dataset_fps: int
    dataset_root: Path
    manifest_path: Path
    episodes: int
    episode_time_s: float
    reset_time_s: float
    task: str
    lerobot_python: Path
    lerobot_home: Path
    lerobot_version: str


def load_recording_config(path: Path) -> RecordingConfig:
    """Read the dedicated, exact-key recording config; paths resolve from its directory."""
    path = Path(path)
    if not path.is_file():
        raise RecordingConfigError(f"missing recording config: {path}")
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RecordingConfigError(f"{path}: cannot read recording YAML: {exc}") from exc
    if not isinstance(value, dict) or set(value) != {"recording"}:
        raise RecordingConfigError(f"{path.name}: expected only top-level key 'recording'")
    data = value["recording"]
    if not isinstance(data, dict):
        raise RecordingConfigError(f"{path.name}: key 'recording' must be a mapping")
    fields = {
        "follower_port",
        "follower_id",
        "follower_calibration_file",
        "leader_port",
        "leader_id",
        "leader_calibration_file",
        "camera",
        "dataset",
        "episodes",
        "episode_time_s",
        "reset_time_s",
        "task",
        "lerobot",
    }
    _keys(data, fields, "recording")
    camera = _section(data, "camera", {"name", "index_or_path", "width", "height", "fps"})
    dataset = _section(data, "dataset", {"repo_id", "fps", "root", "manifest_path"})
    lerobot = _section(data, "lerobot", {"python", "home", "version"})
    config = RecordingConfig(
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
        camera_name=_identity(camera["name"], "camera.name"),
        camera_index_or_path=_camera_index(camera["index_or_path"]),
        camera_width=_positive_int(camera["width"], "camera.width"),
        camera_height=_positive_int(camera["height"], "camera.height"),
        camera_fps=_positive_int(camera["fps"], "camera.fps"),
        dataset_repo_id=_repo_id(dataset["repo_id"]),
        dataset_fps=_positive_int(dataset["fps"], "dataset.fps"),
        dataset_root=_path(dataset["root"], path.parent, "dataset.root"),
        manifest_path=_path(dataset["manifest_path"], path.parent, "dataset.manifest_path"),
        episodes=_positive_int(data["episodes"], "episodes"),
        episode_time_s=_positive_float(data["episode_time_s"], "episode_time_s"),
        reset_time_s=_positive_float(data["reset_time_s"], "reset_time_s"),
        task=_nonempty(data["task"], "task"),
        lerobot_python=_executable_path(lerobot["python"], path.parent, "lerobot.python"),
        lerobot_home=_path(lerobot["home"], path.parent, "lerobot.home"),
        lerobot_version=_nonempty(lerobot["version"], "lerobot.version"),
    )
    if config.follower_port == config.leader_port:
        raise RecordingConfigError("follower_port and leader_port must be distinct")
    if config.follower_id == config.leader_id:
        raise RecordingConfigError("follower_id and leader_id must be distinct")
    if config.dataset_root == config.manifest_path:
        raise RecordingConfigError("dataset.root and dataset.manifest_path must be distinct")
    if config.camera_fps < config.dataset_fps:
        raise RecordingConfigError("camera.fps must be at least dataset.fps")
    return config


def validate_calibration_files(config: RecordingConfig) -> None:
    """Require readable ID-matched files at LeRobot's selected calibration paths."""
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


def dataset_content_identity(root: Path) -> str:
    """Hash LeRobot metadata/data/videos by relative path and bytes for portable identity."""
    root = Path(root).resolve()
    digest = hashlib.sha256()
    digest.update((DATASET_IDENTITY_CONTRACT + "\0").encode("ascii"))
    for directory in ("meta", "data", "videos"):
        tree = root / directory
        if not tree.is_dir() or tree.is_symlink():
            raise RecordingConfigError(
                f"dataset identity requires a real {directory}/ directory: {tree}"
            )
        digest.update(b"D\0" + directory.encode("utf-8") + b"\0")
        files = sorted(tree.rglob("*"), key=lambda item: item.relative_to(root).as_posix())
        for path in files:
            if path.is_symlink():
                raise RecordingConfigError(f"dataset identity does not allow symlinks: {path}")
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix().encode("utf-8")
            digest.update(b"F\0" + len(relative).to_bytes(8, "big") + relative)
            size = path.stat().st_size
            digest.update(size.to_bytes(8, "big"))
            bytes_read = 0
            with path.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
                    bytes_read += len(chunk)
            if bytes_read != size:
                raise RecordingConfigError(f"dataset file changed while hashing: {path}")
    return f"local-sha256:{digest.hexdigest()}"


def validate_dataset_metadata(
    path: Path, expected_camera: str, expected_fps: int, width: int, height: int
) -> dict[str, Any]:
    """Return a minimal ACT I/O contract only when LeRobot metadata is structurally sound."""
    info_path = Path(path) / "meta" / "info.json"
    try:
        info = json.loads(info_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecordingConfigError(
            f"dataset metadata is unavailable or invalid: {info_path}"
        ) from exc
    if not isinstance(info, dict) or info.get("fps") != expected_fps:
        raise RecordingConfigError("dataset metadata has no valid info mapping or its FPS differs")
    features = info.get("features")
    if not isinstance(features, dict):
        raise RecordingConfigError("dataset metadata has no feature mapping")
    state = _feature_contract(features, "observation.state")
    action = _feature_contract(features, "action")
    state_names = canonicalize_so101_joint_names(state["names"], "observation.state")
    action_names = canonicalize_so101_joint_names(action["names"], "action")
    if state_names != list(SO101_JOINT_NAMES) or action_names != list(SO101_JOINT_NAMES):
        raise RecordingConfigError(
            "state and action names/order do not match the six SO-101 joints"
        )
    state["canonical_joint_names"] = state_names
    action["canonical_joint_names"] = action_names
    if state["dtype"] != "float32" or action["dtype"] != "float32":
        raise RecordingConfigError("state and action dataset features must be float32")
    if state["shape"] != [6] or action["shape"] != [6]:
        raise RecordingConfigError("state and action dataset features must have shape [6]")
    camera_key = f"observation.images.{expected_camera}"
    camera = features.get(camera_key)
    if not isinstance(camera, dict) or camera.get("dtype") not in {"video", "image"}:
        raise RecordingConfigError(
            f"dataset metadata is missing named camera feature {camera_key!r}"
        )
    if camera.get("shape") != [height, width, 3]:
        raise RecordingConfigError(
            f"dataset camera shape {camera.get('shape')!r} differs from [{height}, {width}, 3]"
        )
    actual_camera_keys = sorted(
        key.removeprefix("observation.images.")
        for key in features
        if key.startswith("observation.images.")
    )
    return {
        "status": "validated",
        "source": str(info_path),
        "codebase_version": info.get("codebase_version"),
        "robot_type": info.get("robot_type"),
        "fps": info["fps"],
        "state": state,
        "action": action,
        "camera_names": actual_camera_keys,
        "camera_feature": camera_key,
        "camera_shape": camera.get("shape"),
    }


def canonicalize_so101_joint_names(names: list[str], feature: str) -> list[str]:
    """Normalize only exact known bare and LeRobot ``.pos`` SO-101 aliases."""
    aliases = {alias: joint for joint in SO101_JOINT_NAMES for alias in (joint, f"{joint}.pos")}
    try:
        canonical = [aliases[name] for name in names]
    except KeyError as exc:
        raise RecordingConfigError(
            f"dataset metadata feature {feature!r} has unknown SO-101 joint name {exc.args[0]!r}"
        ) from exc
    if len(canonical) != len(SO101_JOINT_NAMES) or len(set(canonical)) != len(canonical):
        raise RecordingConfigError(
            f"dataset metadata feature {feature!r} has duplicate or incomplete SO-101 joints"
        )
    return canonical


def _feature_contract(features: dict[str, Any], key: str) -> dict[str, Any]:
    feature = features.get(key)
    if not isinstance(feature, dict):
        raise RecordingConfigError(f"dataset metadata is missing feature {key!r}")
    names = feature.get("names")
    if not isinstance(names, list) or not names or not all(isinstance(n, str) and n for n in names):
        raise RecordingConfigError(f"dataset metadata feature {key!r} has no validated names list")
    units = feature.get("units")
    if units is not None and not (
        isinstance(units, list)
        and len(units) == len(names)
        and all(isinstance(x, str) for x in units)
    ):
        raise RecordingConfigError(f"dataset metadata feature {key!r} has invalid units")
    return {
        "feature": key,
        "dtype": feature.get("dtype"),
        "shape": feature.get("shape"),
        "names": names,
        "units": units,
    }


def _section(data: dict[str, Any], name: str, allowed: set[str]) -> dict[str, Any]:
    value = data[name]
    if not isinstance(value, dict):
        raise RecordingConfigError(f"recording.{name} must be a mapping")
    _keys(value, allowed, f"recording.{name}")
    return value


def _keys(data: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = set(data) - allowed
    missing = allowed - set(data)
    if unknown:
        raise RecordingConfigError(f"{where}: unknown key {min(unknown)!r}")
    if missing:
        raise RecordingConfigError(f"{where}: missing key {min(missing)!r}")


def _path(value: object, base: Path, name: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise RecordingConfigError(f"{name} must be a nonempty path string")
    candidate = Path(value).expanduser()
    return (candidate if candidate.is_absolute() else base / candidate).resolve()


def _executable_path(value: object, base: Path, name: str) -> Path:
    """Make an executable path absolute without dereferencing virtualenv symlinks."""
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


def _repo_id(value: object) -> str:
    result = _identity(value, "dataset.repo_id")
    if result.startswith("/") or result.endswith("/") or result.count("/") > 1:
        raise RecordingConfigError("dataset.repo_id must be an exact name or namespace/name")
    return result


def _camera_index(value: object) -> int | str:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise RecordingConfigError("camera.index_or_path must be an integer or nonempty path")
    if isinstance(value, str) and not value.strip():
        raise RecordingConfigError("camera.index_or_path must be an integer or nonempty path")
    return value


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise RecordingConfigError(f"{name} must be a positive integer")
    return value


def _positive_float(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise RecordingConfigError(f"{name} must be a positive number")
    return float(value)
