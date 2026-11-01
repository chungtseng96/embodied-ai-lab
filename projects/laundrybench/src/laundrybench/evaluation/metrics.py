from __future__ import annotations

from collections import Counter
from statistics import median

from laundrybench.types import EpisodeResult, FailureCategory


def summarize(results: list[EpisodeResult]) -> dict[str, object]:
    """Aggregate episode results into the metrics named in ``configs/evaluation.yaml``.

    ``median_completion_time_s`` is taken over successful episodes only. A failed
    episode without a category counts as ``"unspecified"``.
    """

    episodes = len(results)
    successful_durations = [result.duration_s for result in results if result.success]
    interventions = sum(result.intervention for result in results)
    failure_counts = Counter(
        (result.failure_category or FailureCategory.UNSPECIFIED).value
        for result in results
        if not result.success
    )

    return {
        "episodes": episodes,
        "successes": len(successful_durations),
        "success_rate": len(successful_durations) / episodes if episodes else 0.0,
        "median_completion_time_s": median(successful_durations) if successful_durations else 0.0,
        "intervention_rate": interventions / episodes if episodes else 0.0,
        "failure_category_counts": dict(failure_counts),
    }
