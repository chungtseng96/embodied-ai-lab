import importlib
import sys
from types import SimpleNamespace

import pytest

from laundrybench.robot.so101 import CameraSettings, SO101LeRobotRobot, create_so101_robot
from laundrybench.robot.so101_spec import SO101_JOINT_NAMES
from laundrybench.types import Action


class FakeFollower:
    def __init__(self, config=None):
        self.config = config or SimpleNamespace(use_degrees=False)
        self.is_connected = True
        self.is_calibrated = True
        self.calls = []
        self.frame = object()

    def connect(self, *, calibrate):
        self.calls.append(("connect", calibrate))
        self.is_connected = True

    def get_observation(self):
        self.calls.append("observe")
        return {**{f"{name}.pos": float(i) for i, name in enumerate(SO101_JOINT_NAMES)},
                "front": self.frame}

    def send_action(self, action):
        self.calls.append(("action", action))
        return {key: value / 2 for key, value in action.items()}

    def disconnect(self):
        self.calls.append("disconnect")
        self.is_connected = False


def test_adapter_maps_observation_and_actual_sent_command():
    follower = FakeFollower()
    robot = SO101LeRobotRobot(follower, camera_names=("front",), clock=lambda: 123.0)
    robot.reset()
    assert follower.calls == []  # reset never moves, reads or connects.
    observation = robot.observe()
    assert observation.joint_positions == [0., 1., 2., 3., 4., 5.]
    assert observation.images["front"] is follower.frame
    assert observation.timestamp_s == 123.0
    assert observation.joint_units == "normalized"
    robot.apply(Action([10.] * 6))
    assert follower.calls[-1] == (
        "action", {f"{name}.pos": 10. for name in SO101_JOINT_NAMES},
    )
    assert robot.last_sent_action == {f"{name}.pos": 5. for name in SO101_JOINT_NAMES}
    assert robot.observe().metadata["step"] == 1


@pytest.mark.parametrize("values", [
    [float("nan")] * 6, [float("inf")] * 6, [101.] * 6, [0.] * 5 + [-1.],
])
def test_invalid_targets_never_reach_follower(values):
    follower = FakeFollower()
    robot = SO101LeRobotRobot(follower, camera_names=("front",))
    with pytest.raises(ValueError):
        robot.apply(Action(values))
    assert follower.calls == []


def test_mutated_action_length_and_wrong_joint_order_rejected():
    follower = FakeFollower()
    robot = SO101LeRobotRobot(follower, camera_names=("front",))
    action = Action([0.] * 6)
    action.joint_targets.pop()
    with pytest.raises(ValueError, match="six"):
        robot.apply(action)
    with pytest.raises(ValueError, match="names/order"):
        robot.apply(Action([0.] * 6, joint_names=tuple(reversed(SO101_JOINT_NAMES))))
    assert follower.calls == []


def test_stop_is_idempotent_and_reset_reconnects_without_motion():
    follower = FakeFollower()
    robot = SO101LeRobotRobot(follower, camera_names=("front",))
    robot.stop()
    robot.stop()
    assert follower.calls == ["disconnect"]
    for operation in (robot.observe, lambda: robot.apply(Action([0.] * 6))):
        with pytest.raises(RuntimeError, match="closed"):
            operation()
    robot.reset()
    assert follower.calls == ["disconnect", ("connect", False)]
    robot.apply(Action([0.] * 6))
    robot.stop()
    assert follower.calls[-1] == "disconnect"


def test_stop_failure_is_visible_and_retryable():
    follower = FakeFollower()
    robot = SO101LeRobotRobot(follower, camera_names=("front",))
    original = follower.disconnect
    follower.disconnect = lambda: (_ for _ in ()).throw(OSError("usb failed"))
    with pytest.raises(OSError, match="usb failed"):
        robot.stop()
    follower.disconnect = original
    robot.stop()
    assert not follower.is_connected


@pytest.mark.parametrize("attribute,value", [
    ("is_connected", False), ("is_calibrated", False),
])
def test_unready_injected_follower_rejected(attribute, value):
    follower = FakeFollower()
    setattr(follower, attribute, value)
    with pytest.raises(ValueError):
        SO101LeRobotRobot(follower, camera_names=("front",))
    assert follower.calls == []


def test_degree_mode_rejected():
    with pytest.raises(ValueError, match="use_degrees=False"):
        SO101LeRobotRobot(FakeFollower(SimpleNamespace(use_degrees=True)), camera_names=("front",))


def _install_fake_modules(monkeypatch, *, legacy=False, calibrated=True, broken_dependency=False):
    followers = []

    def factory(config):
        follower = FakeFollower(config)
        follower.is_connected = False
        follower.is_calibrated = calibrated
        followers.append(follower)
        return follower

    def import_module(name):
        if name == "lerobot.robots.so_follower":
            if broken_dependency:
                raise ModuleNotFoundError("missing feetech", name="feetech")
            if legacy:
                raise ModuleNotFoundError(name=name)
        if name in {"lerobot.robots.so_follower", "lerobot.robots.so101_follower"}:
            return SimpleNamespace(SO101Follower=factory, SO101FollowerConfig=SimpleNamespace)
        if name == "lerobot.cameras.opencv":
            return SimpleNamespace(OpenCVCameraConfig=SimpleNamespace)
        raise AssertionError(f"unexpected import {name}")

    monkeypatch.setattr("laundrybench.robot.so101.importlib.import_module", import_module)
    return followers


@pytest.mark.parametrize("legacy", [False, True])
def test_factory_uses_explicit_configuration_and_no_calibration(monkeypatch, legacy):
    followers = _install_fake_modules(monkeypatch, legacy=legacy)
    robot = create_so101_robot(
        port="/dev/explicit-follower", robot_id="arm-1",
        cameras={"front": CameraSettings(2, 640, 480, 30)}, max_relative_target=2.0,
    )
    follower = followers[0]
    assert follower.calls == [("connect", False)]
    assert follower.config.port == "/dev/explicit-follower"
    assert follower.config.id == "arm-1"
    assert follower.config.use_degrees is False
    assert follower.config.max_relative_target == 2.0
    assert follower.config.disable_torque_on_disconnect is True
    assert follower.config.cameras["front"].index_or_path == 2
    robot.stop()


def test_factory_cleans_up_uncalibrated_follower(monkeypatch):
    followers = _install_fake_modules(monkeypatch, calibrated=False)
    with pytest.raises(ValueError, match="calibrated"):
        create_so101_robot(port="port", robot_id="id", cameras={
            "front": CameraSettings(0, 640, 480, 30)}, max_relative_target=1.)
    assert followers[0].calls == [("connect", False), "disconnect"]


def test_missing_transitive_dependency_is_not_hidden_by_legacy_fallback(monkeypatch):
    _install_fake_modules(monkeypatch, broken_dependency=True)
    with pytest.raises(ModuleNotFoundError) as caught:
        create_so101_robot(port="port", robot_id="id", cameras={
            "front": CameraSettings(0, 640, 480, 30)}, max_relative_target=1.)
    assert caught.value.name == "feetech"


@pytest.mark.parametrize("changes", [
    {"port": ""}, {"robot_id": " "}, {"cameras": {}},
    {"max_relative_target": 0.}, {"max_relative_target": float("inf")},
])
def test_factory_rejects_missing_settings_before_import(monkeypatch, changes):
    monkeypatch.setattr("laundrybench.robot.so101.importlib.import_module",
                        lambda name: pytest.fail("must validate before importing hardware"))
    settings = {"port": "port", "robot_id": "id", "cameras": {
        "front": CameraSettings(0, 640, 480, 30)}, "max_relative_target": 1.}
    settings.update(changes)
    with pytest.raises(ValueError):
        create_so101_robot(**settings)


def test_import_does_not_load_lerobot(monkeypatch):
    module = sys.modules["laundrybench.robot.so101"]
    monkeypatch.setattr(importlib, "import_module",
                        lambda name: pytest.fail("import must not load hardware dependencies"))
    importlib.reload(module)


def test_two_episodes_use_existing_runner_lifecycle():
    from laundrybench.evaluation.judge import MockSuccessJudge
    from laundrybench.evaluation.runner import run_episode
    from laundrybench.policies.mock import MockPolicy

    follower = FakeFollower()
    robot = SO101LeRobotRobot(follower, camera_names=("front",))
    for episode in range(2):
        result = run_episode(
            robot, MockPolicy(), MockSuccessJudge(success_after_steps=1, success_probability=1.),
            control_hz=30., timeout_s=1., episode_id=str(episode),
        )
        assert result.success
    assert follower.calls.count("disconnect") == 2
    assert follower.calls.count(("connect", False)) == 1


def test_reconnect_failure_attempts_cleanup_and_never_sends_action():
    follower = FakeFollower()
    robot = SO101LeRobotRobot(follower, camera_names=("front",))
    robot.stop()

    def fail_connect(*, calibrate):
        raise OSError("connect failed")

    follower.connect = fail_connect
    with pytest.raises(OSError, match="connect failed"):
        robot.reset()
    assert follower.calls == ["disconnect", "disconnect"]


@pytest.mark.parametrize("values", [[True] * 6, ["1"] * 6])
def test_non_numeric_action_values_are_rejected(values):
    follower = FakeFollower()
    robot = SO101LeRobotRobot(follower, camera_names=("front",))
    with pytest.raises(TypeError):
        robot.apply(Action(values))
    assert follower.calls == []
