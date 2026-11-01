from __future__ import annotations

from statistics import median

from laundrybench.types import EpisodeResult, FailureCategory


def format_status(results: list[EpisodeResult], total: int | None) -> str:
    """One-line operator status, e.g. ``episode 7/20 | 4 ok | last: missed_grasp | median 3.1s``.

    ``median`` is over successful episodes' ``duration_s``. ``last`` is ``ok`` for a
    success, else the failure category value (``unspecified`` when unset). A ``None``
    total renders as ``?``.
    """

    successes = [r.duration_s for r in results if r.success]
    if not results:
        last = "-"
    elif results[-1].success:
        last = "ok"
    else:
        last = (results[-1].failure_category or FailureCategory.UNSPECIFIED).value
    median_text = f"{median(successes):.1f}s" if successes else "-"
    total_text = "?" if total is None else str(total)
    return (
        f"episode {len(results)}/{total_text} | {len(successes)} ok | last: {last} "
        f"| median {median_text}"
    )
