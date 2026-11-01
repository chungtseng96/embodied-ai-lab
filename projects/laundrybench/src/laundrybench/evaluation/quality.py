from __future__ import annotations

import itertools
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

FROZEN_ACTION_STEPS = 10
TIMESTAMP_GAP_PERIODS = 3.0


@dataclass(frozen=True)
class QualityFlag:
    episode_id: str
    check: str
    detail: str


def check_episode_quality(
    steps: list[dict],
    *,
    control_hz: float,
    joint_limits: tuple[float, float] = (-100.0, 100.0),
    result: dict | None = None,
) -> list[QualityFlag]:
    """Flag suspect evidence in one episode's step records from ``traces/steps.jsonl``.

    ``result`` is the episode's ``episodes.jsonl`` record; ``missing_label`` is only
    checked when it is given. ``nan_action`` and ``joint_limit`` raise at most one flag
    per episode, counting the offending steps in ``detail``. ``joint_limit`` only
    considers finite targets, so a non-finite target is reported as ``nan_action``.
    """

    if steps:
        episode_id = str(steps[0]["episode_id"])
    elif result is not None:
        episode_id = str(result["episode_id"])
    else:
        return []

    flags: list[QualityFlag] = []

    def flag(check: str, detail: str) -> None:
        flags.append(QualityFlag(episode_id, check, detail))

    low, high = joint_limits
    nan_steps = []
    limit_steps = []
    for record in steps:
        targets = record["joint_targets"]
        if not all(math.isfinite(value) for value in targets):
            nan_steps.append(record["step"])
        if any(math.isfinite(v) and not low <= v <= high for v in targets):
            limit_steps.append(record["step"])
    if nan_steps:
        flag(
            "nan_action",
            f"{len(nan_steps)} steps with non-finite joint targets, first at step {nan_steps[0]}",
        )
    if limit_steps:
        flag(
            "joint_limit",
            f"{len(limit_steps)} steps with targets outside [{low}, {high}], "
            f"first at step {limit_steps[0]}",
        )

    run_start = 0
    for index in range(1, len(steps) + 1):
        if index < len(steps) and steps[index]["joint_targets"] == steps[run_start]["joint_targets"]:
            continue
        if index - run_start >= FROZEN_ACTION_STEPS:
            flag(
                "frozen_actions",
                f"steps {steps[run_start]['step']}-{steps[index - 1]['step']}: "
                f"{index - run_start} identical joint targets",
            )
        run_start = index

    max_gap_s = TIMESTAMP_GAP_PERIODS / control_hz
    for previous, current in itertools.pairwise(steps):
        gap_s = current["timestamp_s"] - previous["timestamp_s"]
        if gap_s > max_gap_s:
            flag(
                "timestamp_gap",
                f"steps {previous['step']}-{current['step']}: {gap_s:.3f}s gap "
                f"exceeds {max_gap_s:.3f}s",
            )

    if (
        result is not None
        and not result["success"]
        and result.get("failure_category") in (None, "unspecified")
    ):
        flag("missing_label", f"failed episode has failure_category {result.get('failure_category')!r}")

    return flags


def write_quality_report(path: Path, flags: list[QualityFlag], episode_ids: list[str]) -> None:
    """Write ``quality.json``: episode count, distinct flagged episodes, and every flag."""

    report = {
        "episodes": len(episode_ids),
        "flagged": len({flag.episode_id for flag in flags}),
        "flags": [asdict(flag) for flag in flags],
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
