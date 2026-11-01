from __future__ import annotations

import pytest

from laundrybench.evaluation.outcomes import summarize_outcomes, validate_labels


def _record(episode_id: str, success: bool) -> dict:
    return {
        "episode_id": episode_id,
        "success": success,
        "duration_s": 2.0,
        "intervention": False,
        "failure_category": None if success else "timeout",
    }


def _review(success: bool, revision: int) -> dict:
    return {
        "success": success,
        "intervention": False,
        "failure_category": None if success else "timeout",
        "notes": "reviewed",
        "revision": revision,
        "updated_at": "2026-11-01T00:00:00+00:00",
    }


def test_provisional_recorded_outcomes_do_not_enter_headline_metrics():
    records = [_record("ep-1", True), _record("ep-2", False)]

    summary = summarize_outcomes(records)

    assert summary["episodes"] == 2
    assert summary["reviewed_episodes"] == 0
    assert summary["pending_episodes"] == 2
    assert summary["metric_episodes"] == 0
    assert summary["successes"] == 0
    assert summary["success_rate"] is None
    assert summary["success_rate_ci"] is None
    assert summary["intervention_rate"] is None
    assert summary["median_completion_time_s"] is None


def test_reviewed_labels_count_and_excluded_labels_leave_denominator():
    records = [_record("ep-1", False), _record("ep-2", True), _record("ep-3", True)]
    labels = {
        "ep-1": {"status": "reviewed", **_review(True, 1)},
        "ep-2": {
            "status": "excluded",
            "exclusion_reason": "trace is incomplete",
            "revision": 2,
            "updated_at": "2026-11-01T00:00:00+00:00",
        },
    }

    summary = summarize_outcomes(records, labels, label_revision=2)

    assert summary["episodes"] == 3
    assert summary["reviewed_episodes"] == 1
    assert summary["pending_episodes"] == 1
    assert summary["excluded_episodes"] == 1
    assert summary["metric_episodes"] == 1
    assert summary["successes"] == 1
    assert summary["success_rate"] == 1.0
    assert summary["reviewed_rate"] == pytest.approx(1 / 3)
    assert summary["failure_category_counts"] == {}
    assert summary["label_revision"] == 2


def test_legacy_v1_labels_are_read_as_reviewed_without_mutation():
    legacy = {"revision": 1, "labels": {"ep-1": _review(True, 1)}}

    normalized = validate_labels(legacy, {"ep-1"})

    assert normalized["schema_version"] == 1
    assert normalized["labels"]["ep-1"] == legacy["labels"]["ep-1"]
    assert legacy == {"revision": 1, "labels": {"ep-1": _review(True, 1)}}
    assert summarize_outcomes([_record("ep-1", False)], normalized["labels"])["success_rate"] == 1


def test_v2_exclusion_requires_nonblank_reason_and_valid_shape():
    v2 = {
        "schema_version": 2,
        "revision": 1,
        "labels": {
            "ep-1": {
                "status": "excluded",
                "exclusion_reason": "   ",
                "revision": 1,
                "updated_at": "now",
            }
        },
    }

    with pytest.raises(ValueError, match="exclusion"):
        validate_labels(v2, {"ep-1"})


@pytest.mark.parametrize(
    "record",
    [
        {**_record("../outside", True)},
        {**_record("ep-1", True), "duration_s": 10**400},
    ],
)
def test_episode_validation_rejects_unsafe_ids_and_unrepresentable_durations(record):
    from laundrybench.evaluation.outcomes import validate_episode_records

    with pytest.raises(ValueError):
        validate_episode_records([record])
