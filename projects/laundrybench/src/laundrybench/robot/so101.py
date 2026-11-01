"""Optional LeRobot SO-101 boundary. Importing this module never opens devices."""
from __future__ import annotations

import importlib
import math
import time
from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from typing import Any

from laundrybench.robot.so101_spec import SO101_JOINT_NAMES
from laundrybench.types import Action, Observation


@dataclass(frozen=True)
class CameraSettings:
    index_or_path: int | str
    width: int
    height: int
    fps: int

    def __post_init__(self) -> None:
        if isinstance(self.index_or_path, bool) or not isinstance(self.index_or_path, (int, str)):
            raise TypeError("camera index_or_path must be an explicit integer or path")
        if isinstance(self.index_or_path, int) and self.index_or_path < 0:
            raise ValueError("camera index cannot be negative")
        if isinstance(self.index_or_path, str) and not self.index_or_path.strip():
            raise ValueError("camera path cannot be empty")
        if any(isinstance(v, bool) or not isinstance(v, int) or v <= 0
               for v in (self.width, self.height, self.fps)):
            raise ValueError("camera width, height, and fps must be positive integers")


class SO101LeRobotRobot:
    """Wrap an already-connected, calibrated follower in normalized units.

    ``stop`` disconnects. ``reset`` starts the next episode by reconnecting
    without calibration when necessary; it never sends a home/motion target.
    """

    def __init__(self, follower: Any, *, camera_names: tuple[str, ...], clock=time.time) -> None:
        if not follower.is_connected or not follower.is_calibrated:
            raise ValueError("follower must already be connected and calibrated")
        if follower.config.use_degrees:
            raise ValueError("adapter requires LeRobot use_degrees=False")
        if len(set(camera_names)) != len(camera_names):
            raise ValueError("camera names must be unique")
        self._follower = follower
        self._camera_names = camera_names
        self._clock = clock
        self._stopped = False
        self._steps = 0
        self.last_sent_action: dict[str, float] | None = None

    def _require_session(self) -> None:
        if self._stopped or not self._follower.is_connected:
            raise RuntimeError("SO-101 session is closed; reset before the next episode")

    def reset(self) -> None:
        if self._stopped or not self._follower.is_connected:
            _connect_calibrated(self._follower)
            self._stopped = False
        self._require_session()
        self._steps = 0
        self.last_sent_action = None

    def observe(self) -> Observation:
        self._require_session()
        raw = self._follower.get_observation()
        positions = [float(raw[f"{name}.pos"]) for name in SO101_JOINT_NAMES]
        if not all(math.isfinite(value) for value in positions):
            raise ValueError("follower returned non-finite joint positions")
        return Observation(
            timestamp_s=self._clock(), joint_positions=positions,
            joint_names=SO101_JOINT_NAMES, joint_units="normalized",
            images={name: raw[name] for name in self._camera_names},
            metadata={"step": self._steps, "robot_implementation": "so101_lerobot",
                      "joint_ranges": "body [-100,100]; gripper [0,100]"},
        )

    def apply(self, action: Action) -> None:
        self._require_session()
        if tuple(action.joint_names) != SO101_JOINT_NAMES:
            raise ValueError("action joint names/order must match SO101_JOINT_NAMES")
        if len(action.joint_targets) != len(SO101_JOINT_NAMES):
            raise ValueError("action must contain six joint targets")
        if any(isinstance(value, bool) or not isinstance(value, Real)
               for value in action.joint_targets):
            raise TypeError("action targets must be real numbers, not booleans or strings")
        values = [float(value) for value in action.joint_targets]
        if not all(math.isfinite(value) for value in values):
            raise ValueError("action targets must be finite")
        if any(not -100 <= value <= 100 for value in values[:-1]) or not 0 <= values[-1] <= 100:
            raise ValueError("normalized body targets must be [-100,100]; gripper [0,100]")
        sent = self._follower.send_action(
            {f"{name}.pos": value for name, value in zip(SO101_JOINT_NAMES, values, strict=True)}
        )
        self.last_sent_action = dict(sent)
        self._steps += 1

    def stop(self) -> None:
        """Disconnect once; propagate failures so cleanup is never silently claimed."""
        if self._stopped:
            return
        self._follower.disconnect()
        self._stopped = True


def _follower_module():
    try:
        return importlib.import_module("lerobot.robots.so_follower")
    except ModuleNotFoundError as error:
        if error.name != "lerobot.robots.so_follower":
            raise
        return importlib.import_module("lerobot.robots.so101_follower")


def create_so101_robot(
    *, port: str, robot_id: str, cameras: dict[str, CameraSettings],
    max_relative_target: float,
) -> SO101LeRobotRobot:
    """Explicit device connection. Never call without a supervised hardware session.

    Requires an existing calibration; calibration is never launched here.
    LeRobot's relative limit is a per-command position delta, not velocity control.
    """
    if not isinstance(port, str) or not port.strip():
        raise ValueError("explicit follower port is required")
    if not isinstance(robot_id, str) or not robot_id.strip():
        raise ValueError("explicit follower robot_id is required")
    if (isinstance(max_relative_target, bool) or not math.isfinite(max_relative_target)
            or max_relative_target <= 0):
        raise ValueError("max_relative_target must be finite and positive")
    if not cameras or any(not isinstance(name, str) or not name.strip() or name.endswith(".pos")
                          for name in cameras):
        raise ValueError("at least one named camera is required; names cannot end with .pos")
    if any(not isinstance(settings, CameraSettings) for settings in cameras.values()):
        raise ValueError("cameras must contain CameraSettings values")
    module = _follower_module()
    camera_module = importlib.import_module("lerobot.cameras.opencv")
    camera_configs = {
        name: camera_module.OpenCVCameraConfig(
            index_or_path=(Path(settings.index_or_path) if isinstance(settings.index_or_path, str)
                           else settings.index_or_path), width=settings.width,
            height=settings.height, fps=settings.fps,
        ) for name, settings in cameras.items()
    }
    config = module.SO101FollowerConfig(
        port=port, id=robot_id, cameras=camera_configs, use_degrees=False,
        max_relative_target=max_relative_target, disable_torque_on_disconnect=True,
    )
    follower = module.SO101Follower(config)
    _connect_calibrated(follower)
    return SO101LeRobotRobot(follower, camera_names=tuple(cameras))


def _connect_calibrated(follower: Any) -> None:
    try:
        follower.connect(calibrate=False)
        if not follower.is_connected or not follower.is_calibrated:
            raise ValueError("follower must be connected and calibrated")
    except BaseException as error:
        try:
            follower.disconnect()
        except BaseException as cleanup_error:  # noqa: BLE001 - preserve original interruption
            error.add_note(f"SO-101 cleanup also failed: {cleanup_error}")
        raise
