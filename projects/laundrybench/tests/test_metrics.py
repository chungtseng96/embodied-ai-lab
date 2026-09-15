from laundrybench.evaluation.metrics import summarize
from laundrybench.types import EpisodeResult


def test_summarize_results() -> None:
    results = [
        EpisodeResult("a", True, 1.0),
        EpisodeResult("b", False, 3.0, intervention=True),
    ]

    summary = summarize(results)

    assert summary["episodes"] == 2
    assert summary["successes"] == 1
    assert summary["success_rate"] == 0.5
    assert summary["median_duration_s"] == 2.0
    assert summary["interventions"] == 1


def test_summarize_empty_results() -> None:
    summary = summarize([])
    assert summary["episodes"] == 0
    assert summary["success_rate"] == 0.0
