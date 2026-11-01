"""Load and validate the checked-in LaundryBench YAML configs."""

from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, get_origin

import yaml


class ConfigError(ValueError):
    """A config file is missing, malformed, or has unknown or missing keys."""


@dataclass(frozen=True)
class RobotConfig:
    implementation: str
    hardware_target: str
    follower_port: str | None
    leader_port: str | None
    max_episode_seconds: float
    require_manual_supervision: bool


@dataclass(frozen=True)
class CameraConfig:
    implementation: str
    device_index: int
    width: int
    height: int
    fps: int
    placement: str


@dataclass(frozen=True)
class TaskConfig:
    name: str
    description: str
    timeout_seconds: float
    success_criteria: tuple[str, ...]
    environment: dict[str, object]


@dataclass(frozen=True)
class EvaluationConfig:
    attempts_per_condition: int
    control_hz: float
    seed: int
    record_video: bool
    record_joint_state: bool
    record_policy_metadata: bool
    require_manual_success_label: bool
    metrics: tuple[str, ...]


@dataclass(frozen=True)
class LaundryBenchConfig:
    robot: RobotConfig
    camera: CameraConfig
    task: TaskConfig
    evaluation: EvaluationConfig


# Keys nested under `robot.safety` in robot.yaml, flattened into RobotConfig.
_ROBOT_SAFETY_KEYS = ("max_episode_seconds", "require_manual_supervision")


def load_config(config_dir: Path) -> LaundryBenchConfig:
    """Load robot, camera, task, and evaluation YAML from `config_dir`."""
    config_dir = Path(config_dir)
    robot = _read_section(config_dir, "robot")
    file = "robot.yaml"
    _check_keys(
        robot,
        [f.name for f in fields(RobotConfig) if f.name not in _ROBOT_SAFETY_KEYS] + ["safety"],
        file,
    )
    safety = _as_mapping(robot.pop("safety"), file, "safety")
    _check_keys(safety, list(_ROBOT_SAFETY_KEYS), file)
    return LaundryBenchConfig(
        robot=_build(RobotConfig, {**robot, **safety}, file),
        camera=_build(CameraConfig, _read_section(config_dir, "camera"), "camera.yaml"),
        task=_build(TaskConfig, _read_section(config_dir, "task"), "task.yaml"),
        evaluation=_build(
            EvaluationConfig, _read_section(config_dir, "evaluation"), "evaluation.yaml"
        ),
    )


def _read_section(config_dir: Path, name: str) -> dict[str, Any]:
    path = config_dir / f"{name}.yaml"
    file = path.name
    if not path.is_file():
        raise ConfigError(f"missing config file: {path}")
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{file}: invalid YAML: {exc}") from exc
    if document is None:
        document = {}
    if not isinstance(document, dict):
        raise ConfigError(f"{file}: expected a mapping with top-level key '{name}'")
    _check_keys(document, [name], file)
    return dict(_as_mapping(document[name], file, name))


def _as_mapping(value: object, file: str, key: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{file}: key '{key}' must be a mapping")
    return value


def _check_keys(data: dict[str, Any], allowed: list[str], file: str) -> None:
    for key in data:
        if key not in allowed:
            raise ConfigError(f"{file}: unknown key '{key}'")
    for key in allowed:
        if key not in data:
            raise ConfigError(f"{file}: missing key '{key}'")


def _build(cls: type, data: dict[str, Any], file: str) -> Any:
    _check_keys(data, [f.name for f in fields(cls)], file)
    values: dict[str, Any] = {}
    for f in fields(cls):
        value = data[f.name]
        if get_origin(f.type) is dict:
            values[f.name] = dict(_as_mapping(value, file, f.name))
            continue
        try:
            if f.type is float:
                value = float(value)
            elif get_origin(f.type) is tuple:
                value = tuple(value)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{file}: invalid value for key '{f.name}': {exc}") from exc
        values[f.name] = value
    return cls(**values)
