import json
import math

from laundrybench.evaluation.experiment import run_experiment
from laundrybench.evaluation.judge import MockSuccessJudge
from laundrybench.evaluation.report import build_summary
from laundrybench.evaluation.runner import run_episode
from laundrybench.observability.manifest import RunManifest
from laundrybench.policies.faulty import FaultyMockPolicy
from laundrybench.policies.mock import MockPolicy
from laundrybench.robot.mock import MockRobot
from laundrybench.types import FailureCategory, Observation


def _manifest(experiment_id: str, policy_name: str) -> RunManifest:
    return RunManifest(
        experiment_id, "2026-10-31T00:00:00Z", "abc", "deadbeef", 7,
        policy_name, "mock", "3.11.0", None,
    )


def _run(tmp_path, experiment_id, policy, judge, fake_clock):
    experiment_dir = tmp_path / experiment_id
    run_experiment(
        experiment_dir,
        _manifest(experiment_id, policy.name),
        robot=MockRobot(seed=7),
        policy=policy,
        judge=judge,
        episodes=5,
        control_hz=10,
        timeout_s=1.0,
        clock=fake_clock.now,
        sleep=fake_clock.sleep,
    )
    return experiment_dir


def _review_recorded_outcomes(experiment_dir):
    records = [
        json.loads(line)
        for line in (experiment_dir / "episodes.jsonl").read_text().splitlines()
        if line.strip()
    ]
    labels = {}
    for revision, record in enumerate(records, start=1):
        success = record["success"]
        labels[record["episode_id"]] = {
            "status": "reviewed",
            "success": success,
            "intervention": record.get("intervention", False),
            "failure_category": None if success else record.get("failure_category", "unspecified"),
            "notes": "synthetic review for comparison test",
            "revision": revision,
            "updated_at": "2026-11-01T00:00:00+00:00",
        }
    (experiment_dir / "labels.json").write_text(
        json.dumps({"schema_version": 2, "revision": len(labels), "labels": labels})
    )


def test_faulty_policy_emits_nan_from_fault_step() -> None:
    policy = FaultyMockPolicy(fault_step=2)
    policy.reset()
    assert policy.name == "faulty-mock-policy"
    before = policy.act(Observation(0.0, [0.0] * 6, metadata={"step": 1}))
    at = policy.act(Observation(0.0, [0.0] * 6, metadata={"step": 2}))
    after = policy.act(Observation(0.0, [0.0] * 6, metadata={"step": 5}))
    assert all(math.isfinite(v) for v in before.joint_targets)
    assert all(math.isnan(v) for v in at.joint_targets)
    assert all(math.isnan(v) for v in after.joint_targets)


def test_timeout_uses_judge_failure_category(fake_clock) -> None:
    result = run_episode(
        MockRobot(),
        MockPolicy(),
        MockSuccessJudge(success_after_steps=10_000),
        control_hz=10,
        timeout_s=1.0,
        clock=fake_clock.now,
        sleep=fake_clock.sleep,
    )
    assert result.success is False
    assert result.failure_category is FailureCategory.MISSED_GRASP


def test_faulty_candidate_is_worse_than_mock_baseline(tmp_path, fake_clock) -> None:
    baseline_dir = _run(
        tmp_path, "exp-000-mock-smoke", MockPolicy(), MockSuccessJudge(seed=7), fake_clock
    )
    candidate_dir = _run(
        tmp_path,
        "exp-000-faulty-smoke",
        FaultyMockPolicy(),
        MockSuccessJudge(seed=7, success_after_steps=10_000),
        fake_clock,
    )

    quality = json.loads((candidate_dir / "quality.json").read_text())
    assert "nan_action" in {flag["check"] for flag in quality["flags"]}
    baseline_quality = json.loads((baseline_dir / "quality.json").read_text())
    assert "nan_action" not in {flag["check"] for flag in baseline_quality["flags"]}

    baseline_pending = build_summary(baseline_dir)
    candidate_pending = build_summary(candidate_dir, baseline_dir=baseline_dir)
    assert baseline_pending["success_rate"] is None
    assert candidate_pending["success_rate"] is None
    assert candidate_pending["delta"]["success_rate"] is None

    # Recorded mock outcomes remain provisional until a reviewer supplies labels.
    _review_recorded_outcomes(baseline_dir)
    _review_recorded_outcomes(candidate_dir)
    baseline = build_summary(baseline_dir)
    summary = build_summary(candidate_dir, baseline_dir=baseline_dir)
    assert summary["success_rate"] < baseline["success_rate"]
    assert summary["delta"]["success_rate"] < 0
    assert summary["delta"]["success_rate"] == summary["success_rate"] - baseline["success_rate"]
    assert summary["delta"]["failure_category_counts"]["missed_grasp"] == (
        summary["failure_category_counts"].get("missed_grasp", 0)
        - baseline["failure_category_counts"].get("missed_grasp", 0)
    )
    assert "delta" not in baseline
