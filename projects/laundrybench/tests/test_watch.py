from laundrybench.observability.status import format_status
from laundrybench.types import EpisodeResult, FailureCategory


def test_format_status_with_three_results():
    results = [
        EpisodeResult("exp-001-baseline-000", True, 2.0),
        EpisodeResult("exp-001-baseline-001", True, 4.0),
        EpisodeResult(
            "exp-001-baseline-002", False, 5.0, failure_category=FailureCategory.MISSED_GRASP
        ),
    ]
    assert format_status(results, 20) == "episode 3/20 | 2 ok | last: missed_grasp | median 3.0s"


def test_format_status_with_no_results():
    assert format_status([], 20) == "episode 0/20 | 0 ok | last: - | median -"
