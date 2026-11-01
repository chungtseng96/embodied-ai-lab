"""Shared outcome overlay and reviewed-only metric contract.

Episode evidence is immutable. Human review is stored in a small sidecar and
resolved at read time so the API and offline reports use the same rules.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from statistics import median

from laundrybench.types import FailureCategory

OUTCOME_SCHEMA_VERSION = 2
LABEL_FILE = "labels.json"
_EPISODE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,199}\Z")


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """Wilson score interval, or ``None`` when there are no reviewed episodes."""
    if n == 0:
        return None
    p = successes / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half_width = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return (max(0.0, center - half_width), min(1.0, center + half_width))


def validate_labels(labels: object, episode_ids: set[str]) -> dict:
    """Validate and normalize legacy v1 or current v2 label sidecars.

    Missing ``schema_version`` identifies the legacy envelope. Legacy labels
    are interpreted as reviewed without writing a migration to disk.
    """
    if not isinstance(labels, dict):
        raise TypeError("invalid labels artifact")
    version = labels.get("schema_version", 1)
    allowed = ({"revision", "labels"}, {"schema_version", "revision", "labels"}) \
        if version == 1 else ({"schema_version", "revision", "labels"},)
    if (
        type(version) is not int
        or version not in (1, OUTCOME_SCHEMA_VERSION)
        or set(labels) not in allowed
        or type(labels.get("revision")) is not int
        or labels["revision"] < 0
        or not isinstance(labels.get("labels"), dict)
    ):
        raise ValueError("invalid labels artifact")

    for episode_id, entry in labels["labels"].items():
        if episode_id not in episode_ids or not isinstance(entry, dict):
            raise ValueError("invalid stored episode label")
        status = entry.get("status", "reviewed") if version == 1 else entry.get("status")
        common = {"revision", "updated_at"}
        if (
            type(entry.get("revision")) is not int
            or not 1 <= entry["revision"] <= labels["revision"]
            or not isinstance(entry.get("updated_at"), str)
        ):
            raise ValueError("invalid stored episode label")
        if status == "excluded":
            if version != OUTCOME_SCHEMA_VERSION or set(entry) != common | {
                "status", "exclusion_reason"
            }:
                raise ValueError("invalid stored episode label")
            reason = entry.get("exclusion_reason")
            if not isinstance(reason, str) or not reason.strip() or len(reason) > 4000:
                raise ValueError("invalid stored exclusion reason")
            continue
        expected = common | {"success", "intervention", "failure_category", "notes"}
        if version == OUTCOME_SCHEMA_VERSION:
            expected.add("status")
        if status != "reviewed" or set(entry) != expected:
            raise ValueError("invalid stored episode label")
        if (
            type(entry["success"]) is not bool
            or type(entry["intervention"]) is not bool
            or not isinstance(entry["notes"], str)
            or len(entry["notes"]) > 4000
        ):
            raise ValueError("invalid stored episode label")
        category = entry["failure_category"]
        if category is not None and category not in [value.value for value in FailureCategory]:
            raise ValueError("invalid stored episode label")
        if entry["success"] and (entry["intervention"] or category is not None):
            raise ValueError("invalid stored episode label")
        if not entry["success"] and category is None:
            raise ValueError("invalid stored episode label")

    return {"schema_version": version, "revision": labels["revision"], "labels": labels["labels"]}


def validate_episode_records(records: object) -> list[dict]:
    """Validate the shared immutable episode input contract for API and reports."""
    if not isinstance(records, list):
        raise TypeError("episode evidence must be a list")
    episode_ids: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise TypeError("invalid episode evidence")
        episode_id = record.get("episode_id")
        duration = record.get("duration_s")
        try:
            finite_duration = math.isfinite(duration) if type(duration) in (int, float) else False
        except OverflowError:
            finite_duration = False
        if (
            not isinstance(episode_id, str)
            or not _EPISODE_ID.fullmatch(episode_id)
            or episode_id in episode_ids
            or type(record.get("success")) is not bool
            or type(record.get("intervention", False)) is not bool
            or type(duration) not in (int, float)
            or not finite_duration
            or duration < 0
            or not isinstance(record.get("metadata", {}), dict)
        ):
            raise ValueError("invalid or duplicate episode evidence")
        category = record.get("failure_category")
        if category is not None and category not in [value.value for value in FailureCategory]:
            raise ValueError("invalid episode failure_category")
        episode_ids.add(episode_id)
    return records


def resolve_episode(record: dict, label: dict | None = None) -> dict:
    """Return original/effective outcome and explicit review provenance."""
    keys = ("success", "failure_category", "intervention")
    original = {key: record.get(key) for key in keys}
    original["intervention"] = record.get("intervention", False)
    if label is None:
        status, source, effective = "provisional", "recorded", dict(original)
    elif label.get("status", "reviewed") == "excluded":
        status, source, effective = "excluded", "recorded", dict(original)
    else:
        status, source = "reviewed", "label"
        effective = {key: label.get(key) for key in keys}
    return {
        "original_outcome": original,
        "effective_outcome": effective,
        "review_status": status,
        "outcome_source": source,
    }


def summarize_outcomes(
    records: list[dict], labels: dict | None = None, label_revision: int = 0
) -> dict:
    """Summarize immutable episode records using reviewed, included labels only."""
    label_map = labels or {}
    reviewed, pending, excluded = [], 0, 0
    for record in records:
        label = label_map.get(record["episode_id"])
        resolved = resolve_episode(record, label)
        status = resolved["review_status"]
        if status == "reviewed":
            reviewed.append((record, resolved["effective_outcome"]))
        elif status == "excluded":
            excluded += 1
        else:
            pending += 1

    n = len(reviewed)
    successes = sum(outcome["success"] for _, outcome in reviewed)
    success_durations = [record["duration_s"] for record, outcome in reviewed if outcome["success"]]
    interventions = sum(bool(outcome["intervention"]) for _, outcome in reviewed)
    failures = Counter(
        (outcome["failure_category"] or FailureCategory.UNSPECIFIED.value)
        for _, outcome in reviewed
        if not outcome["success"]
    )
    interval = wilson_interval(successes, n)
    total = len(records)
    return {
        "episodes": total,
        "reviewed_episodes": n,
        "pending_episodes": pending,
        "excluded_episodes": excluded,
        "metric_episodes": n,
        "successes": successes,
        "success_rate": successes / n if n else None,
        "reviewed_rate": n / total if total else None,
        "success_rate_ci": list(interval) if interval is not None else None,
        "median_completion_time_s": median(success_durations) if success_durations else None,
        "intervention_rate": interventions / n if n else None,
        "failure_category_counts": dict(failures),
        "outcome_schema_version": OUTCOME_SCHEMA_VERSION,
        "label_revision": label_revision,
    }
