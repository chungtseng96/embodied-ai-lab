from laundrybench.evaluation.metrics import summarize
from laundrybench.types import EpisodeResult, FailureCategory


def test_summarize_counts_failure_categories_and_rates() -> None:
    results = [
        EpisodeResult("a", True, 1.0),
        EpisodeResult("b", True, 3.0),
        EpisodeResult(
            "c", False, 5.0, intervention=True, failure_category=FailureCategory.MISSED_GRASP
        ),
        EpisodeResult("d", False, 6.0, failure_category=None),
    ]
    s = summarize(results)
    assert s["success_rate"] == 0.5
    assert s["median_completion_time_s"] == 2.0
    assert s["intervention_rate"] == 0.25
    assert s["failure_category_counts"] == {"missed_grasp": 1, "unspecified": 1}


def test_summarize_empty_results() -> None:
    s = summarize([])
    assert s["episodes"] == 0 and s["success_rate"] == 0.0
    assert s["failure_category_counts"] == {}
