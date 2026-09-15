from __future__ import annotations

from statistics import median

from laundrybench.types import EpisodeResult


def summarize(results: list[EpisodeResult]) -> dict[str, float | int]:
    if not results:
        return {
            "episodes": 0,
            "successes": 0,
            "success_rate": 0.0,
            "median_duration_s": 0.0,
            "interventions": 0,
        }

    successes = sum(result.success for result in results)
    interventions = sum(result.intervention for result in results)

    return {
        "episodes": len(results),
        "successes": successes,
        "success_rate": successes / len(results),
        "median_duration_s": median(result.duration_s for result in results),
        "interventions": interventions,
    }
