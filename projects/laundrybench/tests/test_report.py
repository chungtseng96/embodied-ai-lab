import json

import pytest

from laundrybench.evaluation.quality import QualityFlag, write_quality_report
from laundrybench.evaluation.report import build_summary, render_html, wilson_interval
from laundrybench.observability.logger import JsonlEpisodeLogger, JsonlStepLogger
from laundrybench.observability.manifest import RunManifest, write_manifest
from laundrybench.types import Action, EpisodeResult, FailureCategory, Observation


def test_wilson_interval_known_value():
    assert wilson_interval(7, 10) == pytest.approx((0.397, 0.892), abs=1e-3)
    assert wilson_interval(0, 0) is None


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
    (tmp_path / "labels.json").write_text(
        json.dumps(
            {
                "revision": 4,
                "labels": {
                    f"exp-001-baseline-{i:03d}": {
                        "success": i < 2,
                        "intervention": i == 2,
                        "failure_category": (
                            None if i < 2 else ("missed_grasp" if i == 2 else "unspecified")
                        ),
                        "notes": "reviewed",
                        "revision": i + 1,
                        "updated_at": "now",
                    }
                    for i in range(4)
                },
            }
        ),
        encoding="utf-8",
    )
    steps = JsonlStepLogger(tmp_path / "traces" / "steps.jsonl")
    steps.log("exp-001-baseline-000", 0, Observation(0.0, [0.0] * 6), Action([0.1] * 6))
    write_quality_report(
        tmp_path / "quality.json",
        [QualityFlag("exp-001-baseline-003", "missing_label", "no category")],
        [f"exp-001-baseline-{i:03d}" for i in range(4)],
    )

    summary = build_summary(tmp_path)

    assert summary["episodes"] == 4
    assert summary["reviewed_episodes"] == 4
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


def test_report_provenance_does_not_claim_physical_execution():
    summary = _summary("exp-001-review", 0.7)
    summary["manifest"]["robot_implementation"] = "mock"
    html = render_html(summary)
    assert "MOCK DATA" in html
    assert "not physical robot performance" in html

    summary["manifest"]["robot_implementation"] = "so101"
    assert "EXECUTION UNVERIFIED" in render_html(summary)
    del summary["manifest"]["robot_implementation"]
    assert "EXECUTION UNVERIFIED" in render_html(summary)


def test_report_escapes_run_content_and_shows_comparison_direction():
    candidate = _summary("<script>alert(1)</script>", 0.7)
    candidate["manifest"]["robot_implementation"] = "mock"
    baseline = _summary("exp-000-baseline", 0.9)
    html = render_html(candidate, baseline)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "-20.0 pp vs baseline" in html
    assert "Baseline: EXECUTION UNVERIFIED" in html


def test_report_empty_results_and_missing_quality_are_explicit(tmp_path):
    write_manifest(
        tmp_path / "manifest.yaml",
        RunManifest(
            "exp-000-empty", "2026-11-01T00:00:00Z", "abc", "deadbeef", 7,
            "mock-policy", "mock", "3.11.0", None,
        ),
    )
    (tmp_path / "episodes.jsonl").write_text("", encoding="utf-8")
    summary = build_summary(tmp_path)
    html = render_html(summary)
    assert "No successful episodes" in html
    assert "No quality report available" in html
    assert "No episodes recorded" in html
    assert "No failed episodes" not in html
    assert "0.0%" not in html
    assert "0.000" not in html
    assert "pp vs baseline" not in render_html(summary, _summary("exp-001-baseline", 0.9))


def test_report_no_successful_episodes_has_no_completion_time():
    summary = _summary("exp-001-failed", 0.0)
    summary["median_completion_time_s"] = 0.0
    html = render_html(summary)
    assert "No successful episodes" in html
    assert "— (no successful episodes)" in html
    assert "0.000" not in html


def test_report_does_not_treat_unreviewed_raw_outcomes_as_successes(tmp_path):
    write_manifest(
        tmp_path / "manifest.yaml",
        RunManifest(
            "exp-002-pending", "2026-11-01T00:00:00Z", "abc", "deadbeef", 7,
            "mock-policy", "mock", "3.11.0", None,
        ),
    )
    episodes = JsonlEpisodeLogger(tmp_path / "episodes.jsonl")
    episodes.log(EpisodeResult("ep-001", True, 1.0))
    summary = build_summary(tmp_path)

    assert summary["episodes"] == 1
    assert summary["pending_episodes"] == 1
    assert summary["success_rate"] is None
    assert summary["success_rate_ci"] is None
    html = render_html(summary)
    assert "No reviewed episodes" in html
    assert "Pending episodes</td><td>1</td>" in html
    assert "Excluded episodes</td><td>0</td>" in html
    assert "Label revision</td><td>0</td>" in html
    assert "Outcome schema version</td><td>2</td>" in html
    assert "Recorded quality flags" in html
    assert "Quality flags are recorded as captured;" in html


def test_report_without_supplied_interval_does_not_invent_one():
    summary = _summary("exp-004-review", 0.7)
    del summary["success_rate_ci"]

    html = render_html(summary)

    assert "95% CI unavailable" in html
    assert "95% CI 0.0%–100.0%" not in html


def test_build_summary_reports_invalid_sidecar_path(tmp_path):
    write_manifest(
        tmp_path / "manifest.yaml",
        RunManifest(
            "exp-003-invalid", "2026-11-01T00:00:00Z", "abc", "deadbeef", 7,
            "mock-policy", "mock", "3.11.0", None,
        ),
    )
    (tmp_path / "episodes.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "labels.json").write_text('{"schema_version":99,"revision":0,"labels":{}}')

    with pytest.raises(ValueError, match="labels.json: invalid labels artifact"):
        build_summary(tmp_path)


@pytest.mark.parametrize(
    ("episode_id", "duration_s"),
    [("../unsafe", 1), ("ep-001", 10**400)],
)
def test_build_summary_rejects_api_unsafe_episode_records(tmp_path, episode_id, duration_s):
    write_manifest(
        tmp_path / "manifest.yaml",
        RunManifest(
            "exp-005-invalid-record", "2026-11-01T00:00:00Z", "abc", "deadbeef", 7,
            "mock-policy", "mock", "3.11.0", None,
        ),
    )
    (tmp_path / "episodes.jsonl").write_text(
        json.dumps({"episode_id": episode_id, "success": True, "duration_s": duration_s}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="episode evidence"):
        build_summary(tmp_path)
