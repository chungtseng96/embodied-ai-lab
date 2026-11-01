import pytest

from laundrybench.robot.mock import MockRobot
from laundrybench.robot.so101_spec import SO101_JOINT_NAMES
from laundrybench.types import Action, Observation


def test_observation_defaults_to_so101_joints():
    obs = Observation(0.0, [0.0] * 6)
    assert obs.joint_names == SO101_JOINT_NAMES and obs.joint_units == "normalized"


def test_observation_rejects_joint_length_mismatch():
    with pytest.raises(ValueError, match="6 joint names"):
        Observation(0.0, [0.0] * 5)


def test_action_rejects_joint_length_mismatch():
    with pytest.raises(ValueError):
        Action(joint_targets=[0.0] * 7)


def test_mock_robot_observation_has_front_camera_slot():
    assert "front" in MockRobot().observe().images
