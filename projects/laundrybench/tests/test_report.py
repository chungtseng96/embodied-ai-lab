import pytest

from laundrybench.evaluation.quality import QualityFlag, write_quality_report
from laundrybench.evaluation.report import build_summary, render_html, wilson_interval
from laundrybench.observability.logger import JsonlEpisodeLogger, JsonlStepLogger
from laundrybench.observability.manifest import RunManifest, write_manifest
from laundrybench.types import Action, EpisodeResult, FailureCategory, Observation


def test_wilson_interval_known_value():
    assert wilson_interval(7, 10) == pytest.approx((0.397, 0.892), abs=1e-3)
    assert wilson_interval(0, 0) == (0.0, 0.0)


def test_build_summary_reads_experiment_dir(tmp_path):
    write_manifest(
        tmp_path / "manifest.yaml",
        RunManifest(
            "exp-001-baseline", "2026-10-31T00:00:00Z", "abc", "deadbeef", 7,
            "mock-policy", "mock", "3.11.0", None,
        ),
    )
    episodes = JsonlEpisodeLogger(tmp_path / "episodes.jsonl")
    episodes.log(EpisodeResult("exp-001-baseline-000", True, 1.0))
    episodes.log(EpisodeResult("exp-001-baseline-001", True, 3.0))
    episodes.log(
        EpisodeResult(
            "exp-001-baseline-002", False, 5.0, intervention=True,
            failure_category=FailureCategory.MISSED_GRASP,
        )
    )
    episodes.log(EpisodeResult("exp-001-baseline-003", False, 6.0))
    steps = JsonlStepLogger(tmp_path / "traces" / "steps.jsonl")
    steps.log("exp-001-baseline-000", 0, Observation(0.0, [0.0] * 6), Action([0.1] * 6))
    write_quality_report(
        tmp_path / "quality.json",
        [QualityFlag("exp-001-baseline-003", "missing_label", "no category")],
        [f"exp-001-baseline-{i:03d}" for i in range(4)],
    )

    summary = build_summary(tmp_path)

    assert summary["episodes"] == 4
    assert summary["success_rate"] == 0.5
    assert summary["intervention_rate"] == 0.25
    assert summary["failure_category_counts"] == {"missed_grasp": 1, "unspecified": 1}
    assert summary["success_rate_ci"] == pytest.approx(list(wilson_interval(2, 4)))
    assert summary["quality"] == {"episodes": 4, "flagged": 1}
    assert summary["manifest"]["experiment_id"] == "exp-001-baseline"
    assert summary["manifest"]["seed"] == 7


def _summary(experiment_id: str, success_rate: float) -> dict:
    return {
        "episodes": 10,
        "successes": int(success_rate * 10),
        "success_rate": success_rate,
        "success_rate_ci": list(wilson_interval(int(success_rate * 10), 10)),
        "median_completion_time_s": 1.5,
        "intervention_rate": 0.1,
        "failure_category_counts": {"missed_grasp": 3},
        "quality": {"episodes": 10, "flagged": 2},
        "manifest": {"experiment_id": experiment_id, "policy_name": "mock-policy"},
    }


def test_render_html_includes_baseline_column():
    candidate = _summary("exp-001-baseline", 0.7)
    baseline = _summary("exp-000-mock-smoke", 0.9)

    html = render_html(candidate, baseline=baseline)
    assert "exp-001-baseline" in html
    assert "exp-000-mock-smoke" in html
    assert "Baseline" in html
    assert "70.0%" in html and "90.0%" in html
    assert "missed_grasp" in html

    assert "Baseline" not in render_html(candidate)
