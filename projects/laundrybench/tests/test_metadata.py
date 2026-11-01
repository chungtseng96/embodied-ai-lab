from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from laundrybench.evaluation.metadata import (
    MetadataError,
    compare_run_context,
    read_experiment_metadata,
    validate_experiment_metadata,
    write_experiment_metadata,
)


def metadata(**updates):
    value = {
        "schema_version": 1,
        "name": "Baseline",
        "hypothesis": "The tuned grasp helps",
        "what_changed": "Baseline config",
        "task": {"id": "fold-shirt", "version": "2"},
        "protocol": {"id": "tabletop-v1", "version": "1"},
        "dataset": {"id": "shirts", "revision": "abc123"},
        "checkpoint": {"identity": "sha256:123"},
        "effective_overrides": {"control_hz": 10},
        "evidence_links": [{"label": "run notes", "url": "https://example.org/run"}],
    }
    value.update(updates)
    return value


def summary(**updates):
    value = {
        "reviewed_episodes": 4,
        "successes": 2,
        "success_rate": 0.5,
        "reviewed_rate": 1.0,
        "intervention_rate": 0.25,
        "failure_category_counts": {"missed_grasp": 2},
    }
    value.update(updates)
    return value


def compare(candidate=None, baseline=None, **kwargs):
    return compare_run_context(
        candidate,
        baseline,
        candidate_manifest=kwargs.pop("candidate_manifest", {"config_hash": "same"}),
        baseline_manifest=kwargs.pop("baseline_manifest", {"config_hash": "same"}),
        candidate_summary=kwargs.pop("candidate_summary", summary()),
        baseline_summary=kwargs.pop("baseline_summary", summary()),
        **kwargs,
    )


def test_metadata_validation_normalizes_and_preserves_readable_unicode():
    value = validate_experiment_metadata(metadata(name="Graspé experiment"))
    assert value["name"] == "Graspé experiment"
    assert value["revision"] == 0
    assert value["task"] == {"id": "fold-shirt", "version": "2"}


@pytest.mark.parametrize(
    "change",
    [
        {"unknown": True},
        {"schema_version": 2},
        {"revision": True},
        {"revision": 2**53},
        {"name": 4},
        {"task": {"id": "x", "oops": 1}},
        {"effective_overrides": {"lr": float("nan")}},
        {"effective_overrides": {"large": 10**100}},
        {"evidence_links": [{"label": "bad", "url": "javascript:alert(1)"}]},
        {"evidence_links": [{"label": "private", "url": "https://u:p@example.org/"}]},
        {"evidence_links": [{"label": None, "url": "https://example.org/"}]},
        {"evidence_links": [{"label": "broken ipv6", "url": "https://[invalid/"}]},
        {"evidence_links": [{"label": "control", "url": "https://example.org/\n"}]},
        {"evidence_links": [{"label": "bad port", "url": "https://example.org:99999/"}]},
    ],
)
def test_rejects_malformed_or_unsafe_metadata(change):
    value = metadata()
    value.update(change)
    with pytest.raises(MetadataError):
        validate_experiment_metadata(value)


def test_sidecar_creation_is_atomic_no_clobber_and_revision_checked(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    original_manifest = b"config_hash: original\n"
    (run / "manifest.yaml").write_bytes(original_manifest)

    first = write_experiment_metadata(run, metadata())
    assert first["revision"] == 0
    assert read_experiment_metadata(run) == first
    with pytest.raises(MetadataError, match="expected_revision"):
        write_experiment_metadata(run, metadata(name="stale"))
    with pytest.raises(MetadataError, match="revision conflict"):
        write_experiment_metadata(run, metadata(name="stale"), expected_revision=4)

    second = write_experiment_metadata(run, metadata(name="Updated"), expected_revision=0)
    assert second["revision"] == 1
    assert second["name"] == "Updated"
    assert (run / "manifest.yaml").read_bytes() == original_manifest
    assert json.loads((run / "experiment.json").read_text())["revision"] == 1


def test_missing_sidecar_is_legacy_and_invalid_present_sidecar_is_not_ignored(tmp_path):
    assert read_experiment_metadata(tmp_path) is None
    (tmp_path / "experiment.json").write_text("{broken")
    with pytest.raises(MetadataError, match="invalid experiment metadata"):
        read_experiment_metadata(tmp_path)


def test_concurrent_updates_allow_only_one_writer_per_expected_revision(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    write_experiment_metadata(run, metadata())
    barrier = threading.Barrier(2)

    def update(name):
        barrier.wait()
        try:
            return write_experiment_metadata(run, metadata(name=name), expected_revision=0)
        except MetadataError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, ("writer-a", "writer-b")))
    assert sum(not isinstance(result, MetadataError) for result in results) == 1
    assert sum(isinstance(result, MetadataError) for result in results) == 1
    assert read_experiment_metadata(run)["revision"] == 1


def test_revision_increment_rejects_json_safe_integer_overflow(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    maximum = 2**53 - 1
    value = metadata(revision=maximum)
    (run / "experiment.json").write_text(json.dumps(value), encoding="utf-8")
    original = (run / "experiment.json").read_bytes()
    with pytest.raises(MetadataError, match="cannot be incremented"):
        write_experiment_metadata(run, metadata(), expected_revision=maximum)
    assert (run / "experiment.json").read_bytes() == original


def test_compatibility_requires_task_protocol_ids_and_versions():
    result = compare(None, None)
    assert result["compatibility"]["status"] == "unknown"
    assert result["delta"] is None
    assert any("protocol.version" in reason for reason in result["compatibility"]["reasons"])


def test_matching_context_computes_reviewed_deltas_without_significance_claims():
    candidate = metadata()
    baseline = metadata()
    result = compare(
        candidate,
        baseline,
        candidate_summary=summary(
            reviewed_episodes=5,
            successes=4,
            success_rate=0.8,
            failure_category_counts={"missed_grasp": 1, "timeout": 0},
        ),
        baseline_summary=summary(),
    )
    assert result["compatibility"]["status"] == "matched"
    assert result["delta"]["success_rate"] == pytest.approx(0.3)
    assert result["delta"]["reviewed_episodes"] == 1
    assert result["delta"]["failure_category_counts"] == {"missed_grasp": -1, "timeout": 0}


def test_config_dataset_checkpoint_differences_gate_deltas_until_acknowledged():
    candidate = metadata(dataset={"id": "shirts-v2", "revision": "def456"})
    candidate["checkpoint"] = {"identity": "sha256:other"}
    result = compare(
        candidate,
        metadata(),
        candidate_manifest={"config_hash": "candidate"},
        baseline_manifest={"config_hash": "baseline"},
    )
    assert result["compatibility"]["status"] == "matched"
    assert result["compatibility"]["advisories"]
    assert {"dataset.id", "dataset.revision", "checkpoint.identity", "config_hash"}.issubset(
        result["compatibility"]["differences"]
    )
    assert result["delta"] is not None


def test_task_or_protocol_mismatch_is_incompatible_even_with_other_unknowns():
    candidate = metadata(task={"id": "different-task", "version": "2"})
    baseline = metadata()
    baseline["dataset"] = {"id": None, "revision": None}
    result = compare(candidate, baseline)
    assert result["compatibility"]["status"] == "mismatched"
    assert "task.id" in result["compatibility"]["differences"]
    assert result["delta"] is None
    acknowledged = compare(
        candidate,
        metadata(),
        candidate_manifest={"config_hash": "candidate"},
        baseline_manifest={"config_hash": "baseline"},
        acknowledge_incompatible=True,
    )
    assert acknowledged["delta"] is not None


def test_zero_reviewed_metrics_remain_null_and_unknown_delta_stays_gated():
    empty = summary(reviewed_episodes=0, successes=0, success_rate=None, intervention_rate=None)
    result = compare(metadata(), metadata(), candidate_summary=empty, baseline_summary=empty)
    assert result["compatibility"]["status"] == "matched"
    assert result["delta"]["success_rate"] is None
    assert result["delta"]["intervention_rate"] is None

    no_context = compare(None, metadata())
    assert no_context["compatibility"]["status"] == "unknown"
    assert no_context["delta"] is None
