from __future__ import annotations

import json
import time
from itertools import pairwise
from pathlib import Path
from typing import ClassVar

import pytest

from laundrybench.evaluation import physical
from laundrybench.evaluation.runner import run_episode
from laundrybench.types import SO101_JOINT_NAMES, Action, Observation


class FakeCapture:
    instances: ClassVar[list] = []

    def __init__(self, run_root, cameras, **kwargs):
        self.run_root = Path(run_root)
        self.cameras = cameras
        self.kwargs = kwargs
        self.active = False
        self.started = []
        self.frames = []
        self.aborted = []
        FakeCapture.instances.append(self)

    def start(self, episode_id):
        self.active = True
        self.started.append(episode_id)

    def observe(self, observation):
        self.frames.append(observation.timestamp_s)

    def finalize(self):
        self.active = False
        return {"status": "complete"}

    def abort(self, reason):
        self.active = False
        self.aborted.append(reason)


class FakeRobot:
    def __init__(self):
        self.last_sent_action = {
            "shoulder_pan.pos": 1.0,
            "shoulder_lift.pos": 2.0,
            "elbow_flex.pos": 3.0,
            "wrist_flex.pos": 4.0,
            "wrist_roll.pos": 5.0,
            "gripper.pos": 6.0,
        }
        self.stopped = False
        self.stop_calls = 0
        self.step = 0
        self.actions = []

    def reset(self):
        self.step = 0

    def observe(self):
        return Observation(
            timestamp_s=time.time(),
            joint_positions=[1, 2, 3, 4, 5, 6],
            joint_names=SO101_JOINT_NAMES,
            joint_units="normalized",
            images={"front": object()},
        )

    def apply(self, action):
        self.actions.append(action)
        self.step += 1

    def stop(self):
        self.stop_calls += 1
        self.stopped = True


class FakePolicy:
    name = "fake_act"

    def __init__(self, *, fail=False):
        self.fail = fail
        self.reset_calls = 0
        self.observation_times = []

    def reset(self):
        self.reset_calls += 1

    def act(self, observation):
        if self.fail:
            raise RuntimeError("inference failed")
        self.observation_times.append(observation.timestamp_s)
        return Action([10, 20, 30, 40, 50, 60])


def config(tmp_path):
    contract = tmp_path / "policy_contract.json"
    contract.write_text("{}", encoding="utf-8")
    return {
        "experiment_id": "exp-003-act-bench",
        "task": {"id": "sock-sort", "version": "v1"},
        "protocol": {"id": "home-bench", "version": "v2"},
        "dataset": {"id": "lab/demos", "revision": "rev-1", "fps": 10},
        "checkpoint": {
            "path": str(tmp_path / "checkpoint"),
            "contract_path": str(contract),
            "identity": "act-exp/checkpoint-1000",
        },
        "runtime": {
            "episodes": 1,
            "control_hz": 10,
            "timeout_s": 0.01,
            "max_relative_target": 1.0,
            "device": "cpu",
        },
        "robot": {"port": "/dev/mock-follower", "id": "calibrated-id"},
        "cameras": {"front": {"width": 2, "height": 2, "fps": 10, "index_or_path": 0}},
        "output_dir": str(tmp_path / "output"),
    }


@pytest.fixture(autouse=True)
def capture_factory(monkeypatch):
    FakeCapture.instances.clear()
    monkeypatch.setattr(physical, "EpisodeCapture", FakeCapture)


def test_physical_run_writes_provisional_artifacts_and_actual_command(tmp_path):
    cfg = config(tmp_path)
    config_path = tmp_path / "rollout.yaml"
    config_path.write_text("test: config\n", encoding="utf-8")
    output = tmp_path / "run"
    robot = FakeRobot()
    results = physical.run_physical_experiment(
        experiment_dir=output,
        config_path=config_path,
        config=cfg,
        robot=robot,
        policy=FakePolicy(),
        lerobot_version="0.6.1",
    )
    assert robot.stopped and robot.stop_calls >= 1
    assert results[0].success is False
    assert results[0].failure_category.value == "unspecified"
    assert FakeCapture.instances[0].started == ["exp-003-act-bench-000"]
    assert len(FakeCapture.instances[0].frames) == 1
    episode = json.loads((output / "episodes.jsonl").read_text().splitlines()[0])
    assert episode["success"] is False
    commands = json.loads((output / "traces" / "commands.jsonl").read_text().splitlines()[0])
    assert commands["requested_joint_targets"] == [10, 20, 30, 40, 50, 60]
    assert commands["sent_joint_targets"] == [1, 2, 3, 4, 5, 6]
    assert (output / "manifest.yaml").is_file()
    assert (output / "traces" / "steps.jsonl").is_file()
    assert (output / "quality.json").is_file()
    context = json.loads((output / "experiment.json").read_text())
    assert context["dataset"] == {"id": "lab/demos", "revision": "rev-1"}
    assert context["effective_overrides"]["runtime"]["control_hz"] == 10


def test_inference_failure_aborts_capture_and_stops_robot(tmp_path):
    cfg = config(tmp_path)
    config_path = tmp_path / "rollout.yaml"
    config_path.write_text("test: config\n", encoding="utf-8")
    robot = FakeRobot()
    with pytest.raises(RuntimeError, match="inference failed"):
        physical.run_physical_experiment(
            experiment_dir=tmp_path / "failed",
            config_path=config_path,
            config=cfg,
            robot=robot,
            policy=FakePolicy(fail=True),
            lerobot_version="0.6.1",
        )
    assert robot.stopped
    assert FakeCapture.instances[0].aborted
    assert not FakeCapture.instances[0].active


def test_physical_runner_refreshes_each_policy_observation_on_control_cadence(tmp_path):
    cfg = config(tmp_path)
    cfg["runtime"]["timeout_s"] = 0.21
    config_path = tmp_path / "rollout.yaml"
    config_path.write_text("test: config\n", encoding="utf-8")
    policy = FakePolicy()
    physical.run_physical_experiment(
        experiment_dir=tmp_path / "paced",
        config_path=config_path,
        config=cfg,
        robot=FakeRobot(),
        policy=policy,
        lerobot_version="0.6.1",
    )
    frame_times = FakeCapture.instances[0].frames
    assert len(frame_times) >= 2
    assert len(frame_times) == len(policy.observation_times)
    intervals = [later - earlier for earlier, later in pairwise(frame_times)]
    assert all(0.05 <= interval <= 0.15 for interval in intervals)


def test_inference_that_finishes_after_episode_deadline_cannot_apply_action():
    robot = FakeRobot()
    now = [0.0]

    class SlowPolicy(FakePolicy):
        def act(self, observation):
            now[0] = 1.1
            return super().act(observation)

    result = run_episode(
        robot,
        SlowPolicy(),
        physical.PendingPhysicalJudge(),
        control_hz=10,
        timeout_s=1.0,
        clock=lambda: now[0],
        sleep=lambda _: None,
    )
    assert result.duration_s == 1.1
    assert robot.actions == []
    assert robot.stopped


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        (
            {
                "runtime": {
                    "episodes": 1,
                    "control_hz": float("nan"),
                    "timeout_s": 1,
                    "max_relative_target": 1,
                    "device": "cpu",
                }
            },
            "finite and positive",
        ),
        (
            {
                "runtime": {
                    "episodes": 1,
                    "control_hz": 10.5,
                    "timeout_s": 1,
                    "max_relative_target": 1,
                    "device": "cpu",
                }
            },
            "match trained dataset fps",
        ),
        (
            {"cameras": {"front": {"width": 3, "height": 2, "fps": 10, "index_or_path": 0}}},
            "must be even",
        ),
        (
            {
                "runtime": {
                    "episodes": 1,
                    "control_hz": 10,
                    "timeout_s": 1,
                    "max_relative_target": 6,
                    "device": "cpu",
                }
            },
            "capped at 5",
        ),
    ],
)
def test_rollout_config_rejects_bad_cadence_before_robot_creation(tmp_path, updates, message):
    cfg = config(tmp_path)
    cfg.update(updates)
    with pytest.raises(ValueError, match=message):
        physical.validate_rollout_config(cfg)
