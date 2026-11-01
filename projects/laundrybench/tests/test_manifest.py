import re

import yaml
from conftest import REPO_CONFIGS, copy_configs

from laundrybench.observability.manifest import (
    EXPERIMENT_ID_RE,
    RunManifest,
    config_hash,
    git_revision,
    write_manifest,
)


def test_git_revision_unknown_outside_repo(tmp_path):
    assert git_revision(cwd=tmp_path) == "unknown"


def test_config_hash_is_stable_and_changes_with_content(tmp_path):
    copy_configs(REPO_CONFIGS, tmp_path)
    h1 = config_hash(tmp_path)
    assert h1 == config_hash(tmp_path)
    (tmp_path / "task.yaml").write_text("task:\n  name: other\n")
    assert config_hash(tmp_path) != h1


def test_write_manifest_round_trips(tmp_path):
    m = RunManifest(
        "exp-001-baseline",
        "2026-10-31T00:00:00Z",
        "abc",
        "deadbeef",
        7,
        "mock-policy",
        "mock",
        "3.11.0",
        None,
    )
    write_manifest(tmp_path / "manifest.yaml", m)
    loaded = yaml.safe_load((tmp_path / "manifest.yaml").read_text())
    assert loaded["experiment_id"] == "exp-001-baseline"


def test_evaluate_rejects_bad_experiment_id():
    assert re.match(EXPERIMENT_ID_RE, "exp-001-baseline")
    assert not re.match(EXPERIMENT_ID_RE, "baseline")
