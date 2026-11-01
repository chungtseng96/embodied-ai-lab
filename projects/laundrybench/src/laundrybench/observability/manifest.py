from __future__ import annotations

import hashlib
import importlib.metadata
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

EXPERIMENT_ID_RE = r"^exp-\d{3}-[a-z0-9-]+$"

_CONFIG_FILES = ("camera.yaml", "evaluation.yaml", "robot.yaml", "task.yaml")


@dataclass(frozen=True)
class RunManifest:
    """Provenance for one experiment run, written as `manifest.yaml`."""

    experiment_id: str
    created_at: str
    git_revision: str
    config_hash: str
    seed: int
    policy_name: str
    robot_implementation: str
    python_version: str
    lerobot_version: str | None


def git_revision(cwd: Path | None = None) -> str:
    """Return the HEAD commit of the repository at `cwd`, or "unknown" on any failure."""
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if completed.returncode != 0:
        return "unknown"
    return completed.stdout.strip() or "unknown"


def config_hash(config_dir: Path) -> str:
    """Return the sha256 hex digest of the four config files' bytes, sorted by filename."""
    digest = hashlib.sha256()
    for name in sorted(_CONFIG_FILES):
        digest.update((Path(config_dir) / name).read_bytes())
    return digest.hexdigest()


def lerobot_version() -> str | None:
    """Return the installed LeRobot version without importing it, or None."""
    try:
        return importlib.metadata.version("lerobot")
    except importlib.metadata.PackageNotFoundError:
        return None


def write_manifest(path: Path, manifest: RunManifest) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(asdict(manifest), sort_keys=True), encoding="utf-8")
