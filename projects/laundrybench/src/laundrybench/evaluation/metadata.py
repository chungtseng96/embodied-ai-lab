"""Versioned human context and compatibility summaries for experiment runs."""

from __future__ import annotations

import fcntl
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

EXPERIMENT_FILE = "experiment.json"
EXPERIMENT_SCHEMA_VERSION = 1
_MAX_SAFE_INTEGER = 9007199254740991
_TEXT_LIMITS = {"name": 200, "hypothesis": 4000, "what_changed": 4000}
_SECTION_FIELDS = {
    "task": {"id", "version"},
    "protocol": {"id", "version"},
    "dataset": {"id", "revision"},
    "checkpoint": {"identity"},
}


class MetadataError(ValueError):
    """Experiment context is malformed or could not be safely updated."""


def _valid_json(value: Any, path: str = "effective_overrides") -> Any:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        if abs(value) <= _MAX_SAFE_INTEGER:
            return value
        raise MetadataError(f"{path} integer exceeds the interoperable JSON range")
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        raise MetadataError(f"{path} must contain only finite numbers")
    if isinstance(value, list):
        return [_valid_json(item, f"{path}[]") for item in value]
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise MetadataError(f"{path} keys must be strings")
        return {key: _valid_json(item, f"{path}.{key}") for key, item in value.items()}
    raise MetadataError(f"{path} must contain JSON-compatible values")


def _optional_text(value: Any, field: str, limit: int = 300) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > limit or not value.strip():
        raise MetadataError(f"{field} must be a non-empty string of at most {limit} characters")
    if any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise MetadataError(f"{field} contains unsupported control characters")
    return value.strip()


def validate_experiment_metadata(value: Any) -> dict:
    """Validate and normalize the strict v1 `experiment.json` sidecar schema."""
    if not isinstance(value, dict):
        raise MetadataError("experiment metadata must be an object")
    allowed = {
        "schema_version",
        "revision",
        "name",
        "hypothesis",
        "what_changed",
        "task",
        "protocol",
        "dataset",
        "checkpoint",
        "effective_overrides",
        "evidence_links",
    }
    if set(value) - allowed:
        raise MetadataError(
            f"unknown experiment metadata fields: {', '.join(sorted(set(value) - allowed))}"
        )
    if (
        type(value.get("schema_version")) is not int
        or value["schema_version"] != EXPERIMENT_SCHEMA_VERSION
    ):
        raise MetadataError(f"schema_version must be {EXPERIMENT_SCHEMA_VERSION}")
    revision = value.get("revision", 0)
    if type(revision) is not int or not 0 <= revision <= _MAX_SAFE_INTEGER:
        raise MetadataError("revision must be a non-negative interoperable JSON integer")

    result = {
        "schema_version": EXPERIMENT_SCHEMA_VERSION,
        "revision": revision,
        **{key: _optional_text(value.get(key), key, limit) for key, limit in _TEXT_LIMITS.items()},
    }
    for section, fields in _SECTION_FIELDS.items():
        raw = value.get(section, {})
        if not isinstance(raw, dict) or set(raw) - fields:
            raise MetadataError(
                f"{section} must be an object with fields {', '.join(sorted(fields))}"
            )
        result[section] = {
            field: _optional_text(raw.get(field), f"{section}.{field}") for field in fields
        }

    overrides = value.get("effective_overrides", {})
    if not isinstance(overrides, dict):
        raise MetadataError("effective_overrides must be an object")
    result["effective_overrides"] = _valid_json(overrides)

    links = value.get("evidence_links", [])
    if not isinstance(links, list) or len(links) > 100:
        raise MetadataError("evidence_links must be a list of at most 100 links")
    normalized_links = []
    for index, link in enumerate(links):
        if not isinstance(link, dict) or set(link) != {"label", "url"}:
            raise MetadataError(f"evidence_links[{index}] requires label and url")
        if not isinstance(link.get("label"), str) or not isinstance(link.get("url"), str):
            raise MetadataError(f"evidence_links[{index}] label and url must be strings")
        label = _optional_text(link["label"], f"evidence_links[{index}].label", 200)
        if not isinstance(link["url"], str) or any(
            ord(char) < 32 or ord(char) == 127 for char in link["url"]
        ):
            raise MetadataError(f"evidence_links[{index}].url contains control characters")
        url = _optional_text(link["url"], f"evidence_links[{index}].url", 2048)
        try:
            parsed = urlsplit(url)
        except ValueError as error:
            raise MetadataError(f"evidence_links[{index}].url is malformed") from error
        if any(ord(char) < 32 or ord(char) == 127 for char in url):
            raise MetadataError(f"evidence_links[{index}].url contains control characters")
        if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
            raise MetadataError(f"evidence_links[{index}].url must be an http(s) URL")
        if parsed.username is not None or parsed.password is not None:
            raise MetadataError(f"evidence_links[{index}].url must not contain credentials")
        try:
            port = parsed.port
        except ValueError as error:
            raise MetadataError(f"evidence_links[{index}].url has an invalid port") from error
        if port is not None and not 0 <= port <= 65535:
            raise MetadataError(f"evidence_links[{index}].url has an invalid port")
        normalized_links.append({"label": label, "url": url})
    result["evidence_links"] = normalized_links
    return result


def read_experiment_metadata(run_dir: Path) -> dict | None:
    """Load optional sidecar context; return None for a legacy run."""
    path = Path(run_dir) / EXPERIMENT_FILE
    if path.is_symlink():
        raise MetadataError("experiment metadata symlinks are not supported")
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MetadataError(f"{path}: invalid experiment metadata JSON") from error
    try:
        return validate_experiment_metadata(value)
    except MetadataError as error:
        raise MetadataError(f"{path}: {error}") from error


def write_experiment_metadata(
    run_dir: Path, value: dict, *, expected_revision: int | None = None
) -> dict:
    """Atomically create/update sidecar using optimistic revision and no-clobber creation.

    New sidecars require `expected_revision=None` and are revision 0. Existing
    sidecars require an explicit matching revision, and are incremented by one.
    """
    directory = Path(run_dir).resolve(strict=True)
    if not directory.is_dir():
        raise MetadataError("run directory must be a directory")
    path = directory / EXPERIMENT_FILE
    lock_path = directory / ".experiment.json.lock"
    if lock_path.is_symlink():
        raise MetadataError("experiment metadata lock symlinks are not supported")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    try:
        lock_fd = os.open(lock_path, flags, 0o600)
    except OSError as error:
        raise MetadataError("cannot safely open experiment metadata lock") from error
    with os.fdopen(lock_fd, "a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        current = read_experiment_metadata(directory)
        if current is None:
            if expected_revision is not None:
                raise MetadataError(
                    "experiment metadata does not exist; omit expected_revision to create"
                )
            revision = 0
        else:
            if expected_revision is None:
                raise MetadataError("experiment metadata exists; expected_revision is required")
            if type(expected_revision) is not int or expected_revision != current["revision"]:
                raise MetadataError(f"revision conflict: current revision is {current['revision']}")
            if current["revision"] == _MAX_SAFE_INTEGER:
                raise MetadataError(
                    "revision cannot be incremented beyond the interoperable JSON range"
                )
            revision = current["revision"] + 1
        if not isinstance(value, dict):
            raise MetadataError("experiment metadata must be an object")
        payload = dict(value)
        payload["schema_version"] = EXPERIMENT_SCHEMA_VERSION
        payload["revision"] = revision
        normalized = validate_experiment_metadata(payload)
        fd, temp_name = tempfile.mkstemp(prefix=".experiment.json.", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(normalized, handle, indent=2, sort_keys=True, allow_nan=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            if current is None:
                # Hard-link creation is atomic and fails instead of replacing an unexpected file.
                os.link(temp_name, path)
                os.unlink(temp_name)
            else:
                os.replace(temp_name, path)
            dir_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return normalized


def _comparable_context(metadata: dict | None, manifest: dict, section: str, field: str):
    if section == "manifest":
        return manifest.get(field)
    if metadata is None:
        return None
    return metadata.get(section, {}).get(field)


def compare_run_context(
    candidate_metadata: dict | None,
    baseline_metadata: dict | None,
    *,
    candidate_manifest: dict,
    baseline_manifest: dict,
    candidate_summary: dict,
    baseline_summary: dict,
    acknowledge_incompatible: bool = False,
) -> dict:
    """Compare context and reviewed outcome summaries without significance claims."""
    checks = [
        ("task.id", "task", "id", True),
        ("task.version", "task", "version", True),
        ("protocol.id", "protocol", "id", True),
        ("protocol.version", "protocol", "version", True),
        ("dataset.id", "dataset", "id", False),
        ("dataset.revision", "dataset", "revision", False),
        ("checkpoint.identity", "checkpoint", "identity", False),
        ("config_hash", "manifest", "config_hash", False),
    ]
    differences, unknown, mismatches, advisories = {}, [], [], []
    for label, section, field, required in checks:
        candidate = _comparable_context(candidate_metadata, candidate_manifest, section, field)
        baseline = _comparable_context(baseline_metadata, baseline_manifest, section, field)
        if candidate is None or baseline is None:
            if required and (candidate is None or baseline is None):
                missing_runs = "both runs" if candidate is None and baseline is None else "one run"
                unknown.append(f"{label} is missing from {missing_runs}")
            elif candidate != baseline:
                differences[label] = {"candidate": candidate, "baseline": baseline}
                advisories.append(f"{label} is present in only one run")
            continue
        if candidate != baseline:
            differences[label] = {"candidate": candidate, "baseline": baseline}
            if required:
                mismatches.append(f"{label} differs")
            else:
                advisories.append(f"{label} differs")

    for field in ("effective_overrides",):
        candidate = (candidate_metadata or {}).get(field)
        baseline = (baseline_metadata or {}).get(field)
        if candidate is not None and baseline is not None and candidate != baseline:
            differences[field] = {"candidate": candidate, "baseline": baseline}
            advisories.append(f"{field} differ")
        elif (candidate is None) != (baseline is None):
            differences[field] = {"candidate": candidate, "baseline": baseline}
            advisories.append(f"{field} is present in only one run")

    status = "mismatched" if mismatches else "unknown" if unknown else "matched"
    delta = None
    if status == "matched" or acknowledge_incompatible:
        delta = {
            "reviewed_episodes": candidate_summary.get("reviewed_episodes", 0)
            - baseline_summary.get("reviewed_episodes", 0),
            "successes": candidate_summary.get("successes", 0)
            - baseline_summary.get("successes", 0),
            "success_rate": _subtract(
                candidate_summary.get("success_rate"), baseline_summary.get("success_rate")
            ),
            "reviewed_rate": _subtract(
                candidate_summary.get("reviewed_rate"), baseline_summary.get("reviewed_rate")
            ),
            "intervention_rate": _subtract(
                candidate_summary.get("intervention_rate"),
                baseline_summary.get("intervention_rate"),
            ),
            "failure_category_counts": {
                key: candidate_summary.get("failure_category_counts", {}).get(key, 0)
                - baseline_summary.get("failure_category_counts", {}).get(key, 0)
                for key in sorted(
                    set(candidate_summary.get("failure_category_counts", {}))
                    | set(baseline_summary.get("failure_category_counts", {}))
                )
            },
        }
    return {
        "compatibility": {
            "status": status,
            "reasons": mismatches + unknown,
            "differences": differences,
            "advisories": advisories,
        },
        "candidate": candidate_summary,
        "baseline": baseline_summary,
        "delta": delta,
    }


def _subtract(candidate: Any, baseline: Any) -> float | None:
    if type(candidate) not in (int, float) or type(baseline) not in (int, float):
        return None
    if not math.isfinite(candidate) or not math.isfinite(baseline):
        return None
    return candidate - baseline
