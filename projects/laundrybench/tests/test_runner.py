import pytest

from laundrybench.evaluation.judge import MockSuccessJudge
from laundrybench.evaluation.runner import run_episode
from laundrybench.policies.mock import MockPolicy
from laundrybench.robot.mock import MockRobot
from laundrybench.types import FailureCategory


def test_episode_times_out_at_timeout_s(fake_clock) -> None:
    result = run_episode(
        MockRobot(),
        MockPolicy(),
        MockSuccessJudge(success_after_steps=10_000, failure_category=FailureCategory.TIMEOUT),
        control_hz=10,
        timeout_s=2.0,
        clock=fake_clock.now,
        sleep=fake_clock.sleep,
    )
    assert result.success is False
    assert result.failure_category is FailureCategory.TIMEOUT
    assert result.metadata["steps"] == 20
    assert result.duration_s == pytest.approx(2.0)


def test_episode_paces_at_control_hz(fake_clock) -> None:
    result = run_episode(
        MockRobot(),
        MockPolicy(),
        MockSuccessJudge(success_after_steps=4, success_probability=1.0),
        control_hz=5,
        timeout_s=10.0,
        clock=fake_clock.now,
        sleep=fake_clock.sleep,
    )
    assert result.success is True
    assert result.metadata["steps"] == 4
    assert result.duration_s == pytest.approx(0.6)  # success returns before the 4th pacing sleep


@pytest.mark.parametrize(
    "kwargs", [{"control_hz": 0, "timeout_s": 1}, {"control_hz": 10, "timeout_s": 0}]
)
def test_episode_rejects_non_positive_timing(kwargs) -> None:
    with pytest.raises(ValueError):
        run_episode(MockRobot(), MockPolicy(), MockSuccessJudge(), **kwargs)


def test_robot_protocol_has_no_task_success() -> None:
    assert not hasattr(MockRobot(), "task_success")


def test_runner_resets_policy_each_episode(fake_clock) -> None:
    policy = MockPolicy()
    robot = MockRobot()
    judge = MockSuccessJudge(success_after_steps=1)
    timing = {"control_hz": 10, "timeout_s": 1.0, "clock": fake_clock.now, "sleep": fake_clock.sleep}
    run_episode(robot, policy, judge, **timing)
    run_episode(robot, policy, judge, **timing)
    assert policy.reset_calls == 2


def test_runner_stops_robot_when_policy_raises(fake_clock) -> None:
    class ExplodingPolicy:
        name = "boom"

        def reset(self) -> None: ...

        def act(self, observation):
            raise RuntimeError("boom")

    robot = MockRobot()
    with pytest.raises(RuntimeError):
        run_episode(
            robot,
            ExplodingPolicy(),
            MockSuccessJudge(),
            control_hz=10,
            timeout_s=1.0,
            clock=fake_clock.now,
            sleep=fake_clock.sleep,
        )
    assert robot.stopped is True


def test_runner_stops_robot_after_normal_episode(fake_clock) -> None:
    robot = MockRobot()
    run_episode(
        robot,
        MockPolicy(),
        MockSuccessJudge(success_after_steps=1),
        control_hz=10,
        timeout_s=1.0,
        clock=fake_clock.now,
        sleep=fake_clock.sleep,
    )
    assert robot.stopped is True


def test_runner_uses_given_episode_id(fake_clock) -> None:
    result = run_episode(
        MockRobot(),
        MockPolicy(),
        MockSuccessJudge(success_after_steps=1, success_probability=1.0),
        control_hz=10,
        timeout_s=1.0,
        clock=fake_clock.now,
        sleep=fake_clock.sleep,
        episode_id="exp-001-baseline-001",
    )
    assert result.episode_id == "exp-001-baseline-001"


def test_runner_calls_on_step_each_step(fake_clock) -> None:
    seen = []
    run_episode(
        MockRobot(),
        MockPolicy(),
        MockSuccessJudge(success_after_steps=3, success_probability=1.0),
        control_hz=10,
        timeout_s=5.0,
        clock=fake_clock.now,
        sleep=fake_clock.sleep,
        episode_id="e",
        on_step=lambda eid, i, o, a: seen.append((eid, i)),
    )
    assert seen == [("e", 0), ("e", 1), ("e", 2)]
