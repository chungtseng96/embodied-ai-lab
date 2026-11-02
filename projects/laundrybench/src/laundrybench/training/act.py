"""Strict, optional-dependency wrapper around LeRobot's ACT training CLI."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shlex
import signal
import subprocess
import sys
import tempfile
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from laundrybench.data.recording import (
    DATASET_IDENTITY_CONTRACT,
    RecordingConfigError,
    canonicalize_so101_joint_names,
    dataset_content_identity,
)

LEROBOT_VERSION = "0.6.1"
SO101_JOINT_NAMES = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]
_CONFIG_KEYS = {"training", "contract", "task", "protocol"}
_TRAINING_KEYS = {
    "dataset_id",
    "dataset_repo_id",
    "dataset_revision",
    "dataset_root",
    "dataset_manifest",
    "output_dir",
    "steps",
    "batch_size",
    "seed",
    "device",
    "mode",
    "cloud",
    "allow_private_upload",
    "control_hz",
}
_CONTRACT_KEYS = {
    "state_names",
    "state_units",
    "action_names",
    "action_units",
    "cameras",
    "normalization",
    "use_degrees",
    "joint_names",
}
_CLOUD_KEYS = {"target", "model_repo_id", "private", "timeout"}


class TrainingError(ValueError):
    """Invalid training config, dataset contract, environment or run output."""


class TrainingInterrupted(Exception):
    """Native command was interrupted; contains logs captured before the signal."""

    def __init__(self, output: str) -> None:
        super().__init__("native training command was interrupted")
        self.output = output


def _mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TrainingError(f"{where} must be a mapping")
    return value


def _strict_keys(value: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise TrainingError(f"{where} has unknown keys: {', '.join(sorted(unknown))}")


def _required(value: dict[str, Any], key: str, where: str) -> Any:
    if key not in value or value[key] is None or value[key] == "":
        raise TrainingError(f"{where}.{key} is required")
    return value[key]


def _names(value: Any, where: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
    ):
        raise TrainingError(f"{where} must be a non-empty list of names")
    if len(set(value)) != len(value):
        raise TrainingError(f"{where} must not contain duplicates")
    return value


def _json_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint_dataset(root: Path) -> str:
    """Return an immutable local dataset revision covering every file below root."""
    try:
        return dataset_content_identity(Path(root).expanduser().resolve())
    except RecordingConfigError as exc:
        raise TrainingError(str(exc)) from exc


def _source_identity() -> tuple[str, str, str]:
    project = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        ["git", "-C", str(project), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        source_sha = result.stdout.strip()
        source_origin = "git_rev_parse"
    else:
        source_sha = os.environ.get("LAUNDRYBENCH_SOURCE_SHA", "").lower()
        if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
            raise TrainingError(
                "could not determine source git SHA; use a git checkout or set "
                "LAUNDRYBENCH_SOURCE_SHA to the full build commit SHA"
            )
        source_origin = "build_argument_operator_asserted"
    digest = hashlib.sha256()
    source_files = [
        project / "scripts" / "train.py",
        project / "src" / "laundrybench" / "policies" / "act.py",
        project / "src" / "laundrybench" / "robot" / "so101_spec.py",
    ]
    source_files.extend((project / "src" / "laundrybench" / "training").glob("*.py"))
    for path in sorted(source_files):
        digest.update(path.relative_to(project).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return source_sha, digest.hexdigest(), source_origin


def _load_config(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise TrainingError(f"cannot read training config {path}: {exc}") from exc
    root = _mapping(document, "config")
    _strict_keys(root, _CONFIG_KEYS, "config")
    training = _mapping(_required(root, "training", "config"), "training")
    contract = _mapping(_required(root, "contract", "config"), "contract")
    _strict_keys(training, _TRAINING_KEYS, "training")
    _strict_keys(contract, _CONTRACT_KEYS, "contract")
    return {
        **training,
        "task": _mapping(_required(root, "task", "config"), "task"),
        "protocol": _mapping(_required(root, "protocol", "config"), "protocol"),
    }, contract


def _validate_config(
    training: dict[str, Any],
    contract: dict[str, Any],
    config_path: Path,
    *,
    allow_existing_output: bool = False,
) -> dict[str, Any]:
    required = [
        "dataset_id",
        "dataset_repo_id",
        "dataset_revision",
        "dataset_root",
        "dataset_manifest",
        "output_dir",
        "steps",
        "batch_size",
        "seed",
        "device",
        "mode",
        "control_hz",
    ]
    for key in required:
        _required(training, key, "training")
    for section_name in ("task", "protocol"):
        section = _mapping(training[section_name], section_name)
        _strict_keys(section, {"id", "version"}, section_name)
        for key in ("id", "version"):
            value = _required(section, key, section_name)
            if not isinstance(value, str):
                raise TrainingError(f"{section_name}.{key} must be a string")
    if training["mode"] not in {"local", "cloud"}:
        raise TrainingError("training.mode must be 'local' or 'cloud'")
    for key in ("steps", "batch_size"):
        if (
            isinstance(training[key], bool)
            or not isinstance(training[key], int)
            or training[key] <= 0
        ):
            raise TrainingError(f"training.{key} must be a positive integer")
    if isinstance(training["seed"], bool) or not isinstance(training["seed"], int):
        raise TrainingError("training.seed must be an integer")
    if training["device"] not in {"cuda", "mps", "cpu"}:
        raise TrainingError("training.device must be cuda, mps or cpu")
    if not isinstance(training["control_hz"], (int, float)) or training["control_hz"] <= 0:
        raise TrainingError("training.control_hz must be a positive number")
    if not isinstance(training["dataset_repo_id"], str) or not re.fullmatch(
        r"[^/]+/[^/]+", training["dataset_repo_id"]
    ):
        raise TrainingError("training.dataset_repo_id must be an explicit namespace/name")
    if not isinstance(training["dataset_id"], str) or not re.fullmatch(
        r"local-sha256:[0-9a-f]{64}", training["dataset_id"]
    ):
        raise TrainingError("training.dataset_id must be a portable local-sha256 content identity")
    revision = training["dataset_revision"]
    is_hub_revision = isinstance(revision, str) and re.fullmatch(r"[0-9a-f]{40}", revision)
    local_match = (
        re.fullmatch(r"local-sha256:([0-9a-f]{64})", revision)
        if isinstance(revision, str)
        else None
    )
    if not is_hub_revision and not local_match:
        raise TrainingError(
            "dataset_revision must be a Hub commit SHA or local-sha256:<64 hex> tree digest"
        )
    if training["mode"] == "cloud" and not is_hub_revision:
        raise TrainingError(
            "cloud Jobs require an immutable Hub dataset commit SHA in dataset_revision; "
            "a local content digest cannot pin the remote dataset used by LeRobot Jobs"
        )
    for key in ("allow_private_upload",):
        if key in training and not isinstance(training[key], bool):
            raise TrainingError(f"training.{key} must be boolean")

    _strict_keys(contract, _CONTRACT_KEYS, "contract")
    for key in ("state_names", "action_names", "joint_names"):
        _names(_required(contract, key, "contract"), f"contract.{key}")
    if contract["joint_names"] != SO101_JOINT_NAMES:
        raise TrainingError("contract.joint_names must exactly match canonical SO-101 joint order")
    for feature_name in ("state", "action"):
        try:
            canonical_names = canonicalize_so101_joint_names(
                contract[f"{feature_name}_names"], feature_name
            )
        except RecordingConfigError as exc:
            raise TrainingError(str(exc)) from exc
        if canonical_names != SO101_JOINT_NAMES:
            raise TrainingError(
                f"{feature_name} feature names must preserve canonical SO-101 order"
            )
    for feature in ("state", "action"):
        names = contract[f"{feature}_names"]
        units = _required(contract, f"{feature}_units", "contract")
        if (
            not isinstance(units, list)
            or len(names) != len(units)
            or any(unit != "normalized" for unit in units)
        ):
            raise TrainingError(
                f"contract.{feature}_units must explicitly mark every ordered joint normalized"
            )
    if len(contract["state_names"]) != len(contract["joint_names"]) or len(
        contract["action_names"]
    ) != len(contract["joint_names"]):
        raise TrainingError(
            "state/action feature names must have the same number of entries as joint_names"
        )
    if contract.get("use_degrees") is not False:
        raise TrainingError(
            "contract.use_degrees must explicitly be false for normalized SO-101 coordinates"
        )
    norm = _mapping(_required(contract, "normalization", "contract"), "contract.normalization")
    _strict_keys(
        norm,
        {"coordinate_space", "state_min", "state_max", "action_min", "action_max"},
        "contract.normalization",
    )
    if norm.get("coordinate_space") != "normalized":
        raise TrainingError("contract.normalization.coordinate_space must be normalized")
    for label in ("state", "action"):
        minima = _required(norm, f"{label}_min", "contract.normalization")
        maxima = _required(norm, f"{label}_max", "contract.normalization")
        count = len(contract[f"{label}_names"])
        if (
            not isinstance(minima, list)
            or not isinstance(maxima, list)
            or len(minima) != count
            or len(maxima) != count
        ):
            raise TrainingError(
                f"contract.normalization.{label}_min/max must match the ordered joint count"
            )
        if any(
            not isinstance(lo, (int, float)) or not isinstance(hi, (int, float)) or lo >= hi
            for lo, hi in zip(minima, maxima, strict=True)
        ):
            raise TrainingError(
                f"contract.normalization.{label}_min/max must be finite ordered numeric bounds"
            )
        if minima != [-100, -100, -100, -100, -100, 0] or maxima != [100, 100, 100, 100, 100, 100]:
            raise TrainingError(
                f"contract.normalization.{label}_min/max must follow SO-101 normalized ranges"
            )
    cameras = _required(contract, "cameras", "contract")
    if not isinstance(cameras, dict) or not cameras:
        raise TrainingError("contract.cameras must be a non-empty mapping")
    for camera, spec in cameras.items():
        if not isinstance(camera, str) or not camera:
            raise TrainingError("camera feature names must be non-empty strings")
        spec = _mapping(spec, f"contract.cameras.{camera}")
        _strict_keys(spec, {"width", "height", "color", "dtype"}, f"contract.cameras.{camera}")
        if not all(isinstance(spec.get(key), int) and spec[key] > 0 for key in ("width", "height")):
            raise TrainingError(f"camera {camera} requires positive width and height")
        if spec.get("color") != "RGB" or spec.get("dtype") != "uint8":
            raise TrainingError(f"camera {camera} contract must be RGB uint8")

    if training["mode"] == "cloud":
        cloud = _mapping(_required(training, "cloud", "training"), "training.cloud")
        _strict_keys(cloud, _CLOUD_KEYS, "training.cloud")
        for key in ("target", "model_repo_id"):
            _required(cloud, key, "training.cloud")
        if cloud.get("private") is not True:
            raise TrainingError("cloud training requires training.cloud.private: true")
        if not re.fullmatch(r"[^/]+/[^/]+", cloud["model_repo_id"]):
            raise TrainingError("cloud.model_repo_id must be an explicit namespace/name")
        if training.get("allow_private_upload") is not True:
            raise TrainingError(
                "cloud training requires allow_private_upload: true to authorize "
                "the private model upload and cloud-job handling"
            )
    elif "cloud" in training:
        raise TrainingError("training.cloud is only valid when mode is cloud")

    config_base = config_path.expanduser().resolve().parent

    def config_path_value(value: str) -> Path:
        path = Path(value).expanduser()
        return (path if path.is_absolute() else config_base / path).resolve()

    root = config_path_value(training["dataset_root"])
    if not root.is_dir():
        raise TrainingError(f"dataset_root is not a directory: {root}")
    info_path = root / "meta" / "info.json"
    if not info_path.is_file():
        raise TrainingError(f"missing LeRobot dataset metadata: {info_path}")
    manifest_path = config_path_value(training["dataset_manifest"])
    try:
        recording = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TrainingError(
            f"cannot read completed recording manifest {manifest_path}: {exc}"
        ) from exc
    if recording.get("schema_version") != 1 or recording.get("status") != "completed":
        raise TrainingError("dataset_manifest must be a completed LaundryBench recording manifest")
    if (
        recording.get("return_code") != 0
        or recording.get("supervision", {}).get("operator_confirmed") is not True
    ):
        raise TrainingError("recording manifest must show a successful supervised collection")
    if (
        recording.get("lerobot", {}).get("pinned_version") != LEROBOT_VERSION
        or recording.get("lerobot", {}).get("observed_version") != LEROBOT_VERSION
    ):
        raise TrainingError("recording manifest must confirm LeRobot 0.6.1")
    if (
        recording.get("robot", {}).get("use_degrees") is not False
        or recording.get("teleoperator", {}).get("use_degrees") is not False
    ):
        raise TrainingError(
            "recording manifest must prove robot and teleoperator use_degrees=false"
        )
    argv = recording.get("command")
    if (
        recording.get("shell") is not False
        or not isinstance(argv, list)
        or not {"--robot.use_degrees=false", "--teleop.use_degrees=false"}.issubset(argv)
    ):
        raise TrainingError(
            "recording command must explicitly set robot and teleoperator use_degrees=false"
        )
    recording_dataset = recording.get("dataset", {})
    if recording_dataset.get("fps") != training["control_hz"] or (
        f"--dataset.fps={training['control_hz']}" not in argv
    ):
        raise TrainingError(
            "recording manifest and argv must pin dataset fps to the selected control rate"
        )
    if recording_dataset.get("dataset_id") != training["dataset_id"]:
        raise TrainingError("recording manifest dataset ID does not match training.dataset_id")
    if recording_dataset.get("dataset_id_contract") != DATASET_IDENTITY_CONTRACT:
        raise TrainingError("recording manifest uses an unsupported dataset identity contract")
    native_dataset_id = recording_dataset.get("repo_id_effective") or recording_dataset.get(
        "repo_id_requested"
    )
    if native_dataset_id != training["dataset_repo_id"]:
        raise TrainingError(
            "training.dataset_repo_id must match the recording manifest effective dataset ID"
        )
    if recording_dataset.get("meta_info_sha256") != _json_sha(info_path):
        raise TrainingError(
            "recording manifest metadata SHA-256 does not bind this dataset meta/info.json"
        )
    recorded_camera = recording.get("camera", {})
    act_io = recording_dataset.get("act_io_contract", {})
    recorded_root = Path(recording_dataset.get("root", "")).expanduser().resolve()
    if act_io.get("status") != "validated" or Path(act_io.get("source", "")).resolve() != (
        recorded_root / "meta" / "info.json"
    ):
        raise TrainingError(
            "recording manifest must validate ACT I/O against its source dataset metadata"
        )
    for feature_name in ("state", "action"):
        feature = act_io.get(feature_name, {})
        if (
            feature.get("names") != contract[f"{feature_name}_names"]
            or feature.get("canonical_joint_names") != SO101_JOINT_NAMES
        ):
            raise TrainingError(
                f"recording {feature_name} contract must preserve metadata names and "
                "canonical joint order"
            )
    if len(contract.get("cameras", {})) != 1:
        raise TrainingError("current recording manifest contract supports exactly one named camera")
    camera_name, camera_spec = next(iter(contract["cameras"].items()))
    if (
        recorded_camera.get("name") != camera_name
        or recorded_camera.get("width") != camera_spec["width"]
        or recorded_camera.get("height") != camera_spec["height"]
    ):
        raise TrainingError("recorded camera name/dimensions do not match the training contract")
    if recorded_camera.get("color_mode") != "RGB":
        raise TrainingError("recording manifest must declare the camera color mode as RGB")
    if camera_name not in act_io.get("camera_names", []):
        raise TrainingError("recorded I/O contract does not confirm the declared named camera")
    try:
        metadata = json.loads(info_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TrainingError(f"cannot read dataset metadata {info_path}: {exc}") from exc
    if metadata.get("repo_id") and metadata["repo_id"] != training["dataset_repo_id"]:
        raise TrainingError("dataset metadata repo_id does not match training.dataset_repo_id")
    fps = metadata.get("fps")
    if type(fps) is not int or fps <= 0:
        raise TrainingError("dataset metadata must declare a positive integer fps")
    if fps != training["control_hz"]:
        raise TrainingError("training.control_hz must exactly match the dataset effective fps")
    camera_fps = recorded_camera.get("fps")
    if type(camera_fps) is not int or camera_fps < training["control_hz"]:
        raise TrainingError("camera acquisition fps must be at least the dataset control fps")
    dataset_revision = metadata.get("revision")
    if (
        dataset_revision is not None
        and re.fullmatch(r"[0-9a-f]{40}", training["dataset_revision"])
        and dataset_revision != training["dataset_revision"]
    ):
        raise TrainingError("dataset metadata revision does not match training.dataset_revision")
    try:
        content_identity = dataset_content_identity(root)
    except RecordingConfigError as exc:
        raise TrainingError(str(exc)) from exc
    if content_identity != training["dataset_id"]:
        raise TrainingError("selected dataset root content does not match training.dataset_id")
    if local_match and training["dataset_revision"] != content_identity:
        raise TrainingError(
            "local dataset_revision must match the selected dataset content identity"
        )
    features = _mapping(metadata.get("features"), "dataset metadata.features")
    state_feature = features.get("observation.state")
    action_feature = features.get("action")
    if not isinstance(state_feature, dict) or not isinstance(action_feature, dict):
        raise TrainingError("dataset metadata must expose observation.state and action features")
    if state_feature.get("names") != contract["state_names"]:
        raise TrainingError(
            "contract.state_names must exactly match ordered dataset observation.state names"
        )
    if action_feature.get("names") != contract["action_names"]:
        raise TrainingError(
            "contract.action_names must exactly match dataset action feature names and order"
        )
    for label, feature in (("state", state_feature), ("action", action_feature)):
        if feature.get("dtype") != "float32" or feature.get("shape") != [6]:
            raise TrainingError(f"dataset {label} feature must be float32 with six ordered joints")
    image_features = {
        key.removeprefix("observation.images."): value
        for key, value in features.items()
        if key.startswith("observation.images.")
    }
    camera_names = set(contract["cameras"])
    if set(image_features) != camera_names:
        raise TrainingError(
            "contract.cameras must exactly match dataset observation.images.* camera names"
        )
    for name, spec in contract["cameras"].items():
        shape = image_features[name].get("shape")
        if not isinstance(shape, list) or len(shape) < 2:
            raise TrainingError(
                f"dataset metadata has no usable image shape for observation.images.{name}"
            )
        # LeRobot video feature metadata stores [height, width, channels].
        if (
            shape[0] != spec["height"]
            or shape[1] != spec["width"]
            or (len(shape) > 2 and shape[2] != 3)
        ):
            raise TrainingError(f"camera {name} dimensions do not match dataset metadata")

    output = config_path_value(training["output_dir"])
    if output.exists() and not allow_existing_output:
        raise TrainingError(f"output_dir already exists; refusing to overwrite: {output}")
    return {
        "dataset_root": root,
        "dataset_metadata": metadata,
        "dataset_metadata_path": info_path,
        "dataset_fps": fps,
        "dataset_revision_verified": (
            False
            if training["mode"] == "cloud"
            else content_identity == training["dataset_revision"]
            if local_match
            else dataset_revision == training["dataset_revision"]
        ),
        "dataset_revision_kind": "local_content_sha256" if local_match else "hub_commit",
        "dataset_manifest_path": manifest_path,
        "dataset_manifest_sha256": _json_sha(manifest_path),
        "output_dir": output,
        # LeRobot 0.6.1 refuses an existing --output_dir. Keep LaundryBench's
        # run manifest in the exclusive root and let LeRobot create this child.
        "native_output_dir": output / "native",
        "contract": contract,
        "config_path": config_path.resolve(),
    }


def build_command(training: dict[str, Any], resolved: dict[str, Any], python: Path) -> list[str]:
    command = [
        str(python),
        "-m",
        "lerobot.scripts.lerobot_train",
        f"--dataset.repo_id={training['dataset_repo_id']}",
        f"--dataset.root={resolved['dataset_root']}",
        "--policy.type=act",
        f"--policy.device={training['device']}",
        f"--steps={training['steps']}",
        f"--batch_size={training['batch_size']}",
        f"--seed={training['seed']}",
        f"--output_dir={resolved['native_output_dir']}",
        f"--job_name={resolved['output_dir'].name}",
        "--wandb.enable=false",
    ]
    if re.fullmatch(r"[0-9a-f]{40}", training["dataset_revision"]):
        command.insert(3, f"--dataset.revision={training['dataset_revision']}")
    if training["mode"] == "cloud":
        cloud = training["cloud"]
        command.extend(
            [
                f"--job.target={cloud['target']}",
                f"--policy.repo_id={cloud['model_repo_id']}",
                "--policy.private=true",
                "--policy.push_to_hub=true",
            ]
        )
        if "timeout" in cloud:
            command.append(f"--job.timeout={cloud['timeout']}")
    else:
        command.append("--policy.push_to_hub=false")
    return command


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _check_lerobot(python: Path, runner: Callable[..., subprocess.CompletedProcess[str]]) -> str:
    probe = runner(
        [str(python), "-c", "import importlib.metadata as m; print(m.version('lerobot'))"],
        text=True,
        capture_output=True,
        check=False,
    )
    if probe.returncode != 0:
        raise TrainingError(f"selected Python cannot import LeRobot: {probe.stderr.strip()}")
    version = probe.stdout.strip()
    if version != LEROBOT_VERSION:
        raise TrainingError(
            f"LeRobot {LEROBOT_VERSION} is required, selected environment has {version}"
        )
    return version


def _verify_cloud_dataset_snapshot(
    python: Path,
    training: dict[str, Any],
    expected_content_id: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> dict[str, Any]:
    """Verify a private, exact Hub dataset snapshot before submitting an HF Job."""
    code = """
import json
import sys
from huggingface_hub import HfApi, snapshot_download

repo, revision, local_dir, model_repo = sys.argv[1:]
api = HfApi()
dataset_info = api.repo_info(repo, repo_type="dataset", revision=revision)
if dataset_info.private is not True:
    raise RuntimeError("dataset repository must be private")
if dataset_info.sha != revision:
    raise RuntimeError("Hub did not resolve the requested dataset commit SHA")
model_visibility = "new_private"
if api.repo_exists(model_repo, repo_type="model"):
    model_info = api.repo_info(model_repo, repo_type="model")
    if model_info.private is not True:
        raise RuntimeError("existing model repository must be private")
    model_visibility = "existing_private"
path = snapshot_download(
    repo_id=repo,
    repo_type="dataset",
    revision=revision,
    local_dir=local_dir,
    allow_patterns=["meta/**", "data/**", "videos/**"],
)
print(
    json.dumps(
        {
            "path": str(path),
            "repo_id": repo,
            "revision": dataset_info.sha,
            "private": dataset_info.private,
            "model_repo_id": model_repo,
            "model_repo_visibility": model_visibility,
        }
    )
)
"""
    with tempfile.TemporaryDirectory(prefix="laundrybench-hub-dataset-") as temp_dir:
        local_dir = Path(temp_dir) / "snapshot"
        result = runner(
            [
                str(python),
                "-c",
                code,
                training["dataset_repo_id"],
                training["dataset_revision"],
                str(local_dir),
                training["cloud"]["model_repo_id"],
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise TrainingError(
                "could not verify private Hub dataset snapshot at the configured revision: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        try:
            downloaded = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise TrainingError("Hub dataset snapshot probe returned invalid JSON") from exc
        snapshot = Path(downloaded.get("path", "")).expanduser().resolve()
        if (
            downloaded.get("repo_id") != training["dataset_repo_id"]
            or downloaded.get("revision") != training["dataset_revision"]
            or downloaded.get("private") is not True
            or downloaded.get("model_repo_id") != training["cloud"]["model_repo_id"]
            or downloaded.get("model_repo_visibility") not in {"existing_private", "new_private"}
            or snapshot != local_dir.resolve()
        ):
            raise TrainingError("Hub dataset snapshot identity/private status did not match config")
        try:
            remote_content_id = dataset_content_identity(snapshot)
        except RecordingConfigError as exc:
            raise TrainingError(f"cannot fingerprint exact Hub dataset snapshot: {exc}") from exc
        if remote_content_id != expected_content_id:
            raise TrainingError(
                "private Hub dataset content does not match the validated local recording "
                f"(expected {expected_content_id}, found {remote_content_id})"
            )
    return {
        "repo_id": training["dataset_repo_id"],
        "revision": training["dataset_revision"],
        "private": True,
        "content_id": expected_content_id,
        "model_repo_visibility": downloaded["model_repo_visibility"],
        "verification": "selected_lerobot_python_snapshot_and_content_hash",
    }


def _run_streaming(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Stream native CLI logs to the operator while retaining a bounded manifest log."""
    process = subprocess.Popen(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        start_new_session=(os.name == "posix"),
    )
    captured: deque[str] = deque(maxlen=512)
    interrupted_by = signal.SIGINT

    def handle_sigterm(_signum: int, _frame: Any) -> None:
        nonlocal interrupted_by
        interrupted_by = signal.SIGTERM
        raise KeyboardInterrupt

    old_sigterm = signal.signal(signal.SIGTERM, handle_sigterm)

    def signal_child(sig: int) -> None:
        try:
            if os.name == "posix":
                os.killpg(process.pid, sig)
            else:
                process.send_signal(sig)
        except ProcessLookupError:
            pass

    assert process.stdout is not None
    try:
        for line in process.stdout:
            print(line, end="", flush=True)
            captured.append(line[-4096:])
        returncode = process.wait()
    except KeyboardInterrupt as exc:
        signal_child(interrupted_by)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            # Stop only the local log client. A detached HF Job can continue remotely.
            signal_child(signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                signal_child(signal.SIGKILL)
                process.wait(timeout=5)
        raise TrainingInterrupted("".join(captured)) from exc
    finally:
        signal.signal(signal.SIGTERM, old_sigterm)
    return subprocess.CompletedProcess(command, returncode, "".join(captured), "")


def _has_completed_checkpoint(output: Path) -> Path | None:
    candidates = sorted(output.glob("checkpoints/*/pretrained_model"))
    for candidate in reversed(candidates):
        has_config = (candidate / "config.json").is_file()
        has_weights = (candidate / "model.safetensors").is_file()
        has_processors = (candidate / "policy_preprocessor.json").is_file() and (
            candidate / "policy_postprocessor.json"
        ).is_file()
        if has_config and has_weights and has_processors:
            try:
                _processor_state_hashes(candidate)
            except TrainingError:
                continue
            return candidate
    return None


def _processor_state_hashes(checkpoint: Path) -> dict[str, str]:
    """Hash every external state tensor referenced by saved processor JSON."""
    result: dict[str, str] = {}
    normalizer_steps: set[str] = set()
    referenced: set[str] = set()
    for processor_name in ("policy_preprocessor.json", "policy_postprocessor.json"):
        try:
            document = json.loads((checkpoint / processor_name).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TrainingError(f"checkpoint processor {processor_name} is not valid JSON") from exc
        if not isinstance(document, dict):
            raise TrainingError(f"checkpoint processor {processor_name} must be an object")
        steps = document.get("steps", [])
        if not isinstance(steps, list):
            raise TrainingError(f"checkpoint processor {processor_name}.steps must be a list")
        for step in steps:
            if not isinstance(step, dict):
                raise TrainingError(f"checkpoint processor {processor_name} has an invalid step")
            state_file = step.get("state_file")
            if state_file is None:
                continue
            registry_name = step.get("registry_name")
            if registry_name in {"normalizer_processor", "unnormalizer_processor"}:
                normalizer_steps.add(registry_name)
            if (
                not isinstance(state_file, str)
                or not state_file
                or Path(state_file).is_absolute()
                or len(Path(state_file).parts) != 1
                or "\\" in state_file
                or state_file in referenced
            ):
                raise TrainingError(
                    f"checkpoint processor {processor_name} has duplicate or unsafe state_file"
                )
            referenced.add(state_file)
            state_path = checkpoint / state_file
            if state_path.is_symlink() or not state_path.is_file():
                raise TrainingError(
                    f"checkpoint processor state file is missing or unsafe: {state_file}"
                )
            relative = state_path.relative_to(checkpoint).as_posix()
            result[relative] = _json_sha(state_path)
    if normalizer_steps != {"normalizer_processor", "unnormalizer_processor"}:
        raise TrainingError(
            "ACT checkpoint must include normalizer and unnormalizer processor state"
        )
    return dict(sorted(result.items()))


def _make_policy_contract(
    training: dict[str, Any],
    resolved: dict[str, Any],
    version: str,
    checkpoint: Path,
    *,
    source_sha: str | None = None,
) -> dict[str, Any]:
    contract = resolved["contract"]
    processor_hashes = {
        name: _json_sha(checkpoint / name)
        for name in ("policy_preprocessor.json", "policy_postprocessor.json")
    }
    processor_state_hashes = _processor_state_hashes(checkpoint)
    return {
        "schema_version": 1,
        "task": training["task"],
        "protocol": training["protocol"],
        "dataset": {
            "repo_id": training["dataset_id"],
            "revision": training["dataset_revision"],
            "fps": resolved["dataset_fps"],
        },
        "source_sha": source_sha or _source_identity()[0],
        "lerobot_version": version,
        "use_degrees": False,
        "joint_names": contract["joint_names"],
        "joint_units": "normalized",
        "observation_features": {
            "state": {
                "key": "observation.state",
                "names": contract["state_names"],
                "shape": [len(contract["state_names"])],
                "dtype": "float32",
            },
            "cameras": {
                f"observation.images.{name}": {
                    "shape": [spec["height"], spec["width"], 3],
                    "dtype": "uint8",
                }
                for name, spec in contract["cameras"].items()
            },
        },
        "action_features": {
            "key": "action",
            "names": contract["action_names"],
            "shape": [len(contract["action_names"])],
            "dtype": "float32",
        },
        "cameras": {
            name: {
                "width": spec["width"],
                "height": spec["height"],
                "color_mode": spec["color"],
                "dtype": spec["dtype"],
            }
            for name, spec in contract["cameras"].items()
        },
        "normalization": contract["normalization"],
        "checkpoint": {
            "path": ".",
            "sha256": _json_sha(checkpoint / "model.safetensors"),
            "config_sha256": _json_sha(checkpoint / "config.json"),
            "processor_sha256": processor_hashes,
            "processor_state_sha256": processor_state_hashes,
        },
    }


def _write_json_new(path: Path, value: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as file:
        file.write(json.dumps(value, indent=2, sort_keys=True) + "\n")


def finalize_checkpoint(
    config_path: Path,
    checkpoint_path: Path,
    *,
    confirm_remote_complete: bool,
    remote_model_revision: str,
) -> dict[str, Any]:
    """Bind a downloaded native HF Jobs checkpoint to the reviewed training inputs."""
    if not confirm_remote_complete:
        raise TrainingError(
            "confirm the HF Job is complete before finalizing its downloaded checkpoint"
        )
    if not re.fullmatch(r"[0-9a-f]{40}", remote_model_revision):
        raise TrainingError(
            "remote_model_revision must be the model repo's 40-character commit SHA"
        )
    training, contract = _load_config(Path(config_path))
    resolved = _validate_config(training, contract, Path(config_path), allow_existing_output=True)
    if training["mode"] != "cloud":
        raise TrainingError("checkpoint finalization requires a cloud-mode training config")
    output = resolved["output_dir"]
    manifest_path = output / "laundrybench_training.json"
    try:
        run_record = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TrainingError("cloud submission manifest is unavailable or invalid") from exc
    if run_record.get("status") not in {"submitted", "detached", "submission_error"}:
        raise TrainingError("finalization requires a recorded cloud submission attempt")
    if not run_record.get("job_id"):
        raise TrainingError(
            "finalization requires a recorded HF Job ID; this submission attempt has no job ID"
        )
    if (
        run_record.get("mode") != "cloud"
        or run_record.get("cloud", {}).get("model_repo_id") != training["cloud"]["model_repo_id"]
    ):
        raise TrainingError("submitted cloud model repository does not match finalization config")
    if run_record.get("config_sha256") != _json_sha(resolved["config_path"]):
        raise TrainingError("submitted run config hash does not match this finalization config")
    if run_record.get("dataset", {}).get("id") != training["dataset_id"]:
        raise TrainingError("submitted dataset identity does not match finalization config")
    if run_record.get("dataset", {}).get("revision") != training["dataset_revision"]:
        raise TrainingError("submitted dataset revision does not match finalization config")

    checkpoint = Path(checkpoint_path).expanduser().resolve()
    required = (
        "config.json",
        "model.safetensors",
        "policy_preprocessor.json",
        "policy_postprocessor.json",
    )
    missing = [name for name in required if not (checkpoint / name).is_file()]
    if not checkpoint.is_dir() or missing:
        raise TrainingError(
            f"downloaded ACT checkpoint is incomplete; missing: {', '.join(missing) or 'directory'}"
        )
    try:
        native_config = json.loads((checkpoint / "config.json").read_text(encoding="utf-8"))
        _processor_state_hashes(checkpoint)
    except (OSError, json.JSONDecodeError) as exc:
        raise TrainingError("downloaded checkpoint config/processors must be valid JSON") from exc
    if not isinstance(native_config, dict) or native_config.get("type") != "act":
        raise TrainingError("downloaded checkpoint config must identify policy type 'act'")
    contract_path = checkpoint / "policy_contract.json"
    finalization_path = checkpoint / "laundrybench_finalize.json"
    if contract_path.exists() or finalization_path.exists():
        raise TrainingError(
            "checkpoint already contains a LaundryBench contract/finalization record"
        )
    policy_contract = _make_policy_contract(
        training,
        resolved,
        LEROBOT_VERSION,
        checkpoint,
        source_sha=run_record["source_sha"],
    )
    finalization = {
        "schema_version": 1,
        "status": "contract_finalized",
        "finalized_at": datetime.now(UTC).isoformat(),
        "remote_completion_confirmed_by_operator": True,
        "submission_record_status": run_record["status"],
        "job_id": run_record.get("job_id"),
        "model_repo_id": training["cloud"]["model_repo_id"],
        "model_repo_revision_asserted": remote_model_revision,
        "download_revision_verification": "operator_asserted_not_queried",
        "download_command_recipe": [
            "hf",
            "download",
            training["cloud"]["model_repo_id"],
            "--repo-type",
            "model",
            "--revision",
            "<model-repo-commit-sha>",
            "--local-dir",
            "<private-download-dir>",
        ],
        "downloaded_checkpoint_path": str(checkpoint),
        "model_sha256": policy_contract["checkpoint"]["sha256"],
        "processor_sha256": policy_contract["checkpoint"]["processor_sha256"],
        "processor_state_sha256": policy_contract["checkpoint"]["processor_state_sha256"],
        "config_sha256": run_record["config_sha256"],
        "source_sha": run_record["source_sha"],
        "source_sha_origin": run_record["source_sha_origin"],
    }
    _write_json_new(contract_path, policy_contract)
    _write_json_new(finalization_path, finalization)
    return {
        "status": "contract_finalized",
        "checkpoint": str(checkpoint),
        "policy_contract": str(contract_path),
        "job_id": run_record.get("job_id"),
    }


def run_training(
    config_path: Path,
    *,
    execute: bool = False,
    lerobot_python: Path | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, Any]:
    config_path = Path(config_path)
    training, contract = _load_config(config_path)
    resolved = _validate_config(training, contract, config_path)
    # Keep a venv's bin/python symlink intact; resolving it can switch to the
    # base interpreter and lose the LeRobot installation selected by the user.
    python = Path(lerobot_python or sys.executable).expanduser().absolute()
    if not execute:
        return {
            "status": "planned",
            "command": build_command(training, resolved, python),
            "output_dir": str(resolved["output_dir"]),
            "native_output_dir": str(resolved["native_output_dir"]),
            "dataset_revision_verified": resolved["dataset_revision_verified"],
            "remote_dataset_verification": (
                "pending_execution" if training["mode"] == "cloud" else "not_applicable"
            ),
        }

    version = _check_lerobot(python, runner or subprocess.run)
    remote_dataset = None
    if training["mode"] == "cloud":
        remote_dataset = _verify_cloud_dataset_snapshot(
            python,
            training,
            training["dataset_id"],
            runner or subprocess.run,
        )
    output = resolved["output_dir"]
    source_sha, source_tree_sha, source_sha_origin = _source_identity()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=False)
    command = build_command(training, resolved, python)
    run_record: dict[str, Any] = {
        "schema_version": 1,
        "status": "running",
        "started_at": datetime.now(UTC).isoformat(),
        "output_dir": str(output),
        "native_output_dir": str(resolved["native_output_dir"]),
        "command": command,
        "command_display": shlex.join(command),
        "config_path": str(resolved["config_path"]),
        "config_sha256": _json_sha(resolved["config_path"]),
        "source_sha": source_sha,
        "source_sha_origin": source_sha_origin,
        "source_tree_sha256": source_tree_sha,
        "mode": training["mode"],
        "cloud": training.get("cloud"),
        "dataset": {
            "id": training["dataset_id"],
            "repo_id": training["dataset_repo_id"],
            "revision": training["dataset_revision"],
            "revision_kind": resolved["dataset_revision_kind"],
            "root": str(resolved["dataset_root"]),
            "manifest": str(resolved["dataset_manifest_path"]),
            "manifest_sha256": resolved["dataset_manifest_sha256"],
            "revision_verified": (
                remote_dataset is not None or resolved["dataset_revision_verified"]
            ),
            "fps": resolved["dataset_fps"],
            "metadata_sha256": _json_sha(resolved["dataset_metadata_path"]),
        },
        "remote_dataset": remote_dataset,
        "lerobot_version": version,
        "python_version": platform.python_version(),
        "policy": "act",
        "contract": contract,
    }
    _write_json(output / "laundrybench_training.json", run_record)
    try:
        result = (
            _run_streaming(command)
            if runner is None
            else runner(command, text=True, capture_output=True, check=False)
        )
    except TrainingInterrupted as exc:
        run_record["stdout"] = exc.output[-12000:]
        run_record["status"] = "detached" if training["mode"] == "cloud" else "interrupted"
        run_record["remote_status"] = "unknown" if training["mode"] == "cloud" else None
        run_record["finished_at"] = datetime.now(UTC).isoformat()
        if training["mode"] == "cloud":
            match = re.search(
                r"\bjob(?:\s+id|_id)?\s*[:=]\s*([A-Za-z0-9_-]+)",
                exc.output,
                re.IGNORECASE,
            )
            if match:
                run_record["job_id"] = match.group(1)
            run_record["note"] = (
                "Local log client was interrupted. The HF Job may still be running; "
                "verify its status and logs before finalizing or retrying."
            )
        else:
            run_record["note"] = (
                "Local training was interrupted; inspect partial artifacts before retrying."
            )
        _write_json(output / "laundrybench_training.json", run_record)
        return run_record
    except KeyboardInterrupt:
        run_record["status"] = "detached" if training["mode"] == "cloud" else "interrupted"
        run_record["remote_status"] = "unknown" if training["mode"] == "cloud" else None
        run_record["finished_at"] = datetime.now(UTC).isoformat()
        run_record["note"] = (
            "Training command was interrupted. The HF Job may still be running; "
            "verify its status and logs before finalizing or retrying."
            if training["mode"] == "cloud"
            else "Local training was interrupted; inspect partial artifacts before retrying."
        )
        _write_json(output / "laundrybench_training.json", run_record)
        return run_record
    except OSError as exc:
        run_record.update(
            status="failed", error=str(exc), finished_at=datetime.now(UTC).isoformat()
        )
        _write_json(output / "laundrybench_training.json", run_record)
        raise TrainingError(f"could not launch LeRobot training: {exc}") from exc
    run_record["returncode"] = result.returncode
    run_record["stdout"] = result.stdout[-12000:]
    run_record["stderr"] = result.stderr[-12000:]
    run_record["finished_at"] = datetime.now(UTC).isoformat()
    if training["mode"] == "cloud":
        run_record["status"] = "submitted" if result.returncode == 0 else "submission_error"
        match = re.search(
            r"\bjob(?:\s+id|_id)?\s*[:=]\s*([A-Za-z0-9_-]+)",
            result.stdout,
            re.IGNORECASE,
        )
        if match:
            run_record["job_id"] = match.group(1)
        if result.returncode != 0:
            run_record["remote_status"] = "unknown"
            run_record["note"] = (
                "The LeRobot job command exited nonzero. This does not prove whether a remote job "
                "started or completed; inspect HF Jobs and logs before retrying."
            )
        else:
            run_record["note"] = (
                "Native HF Jobs command returned zero; this wrapper did not independently "
                "verify remote completion or the final model artifact."
            )
    else:
        checkpoint = _has_completed_checkpoint(resolved["native_output_dir"])
        if result.returncode == 0 and checkpoint is not None:
            run_record["status"] = "completed"
            run_record["checkpoint_path"] = str(checkpoint)
            checkpoint_files = sorted(path for path in checkpoint.rglob("*") if path.is_file())
            run_record["checkpoint_files"] = [
                str(path.relative_to(checkpoint)) for path in checkpoint_files
            ]
            policy_contract = _make_policy_contract(training, resolved, version, checkpoint)
            processor_hashes = policy_contract["checkpoint"]["processor_sha256"]
            run_record["processor_sha256"] = processor_hashes
            _write_json(output / "policy_contract.json", policy_contract)
            _write_json(checkpoint / "policy_contract.json", policy_contract)
        else:
            run_record["status"] = "failed"
            if result.returncode == 0:
                run_record["error"] = (
                    "LeRobot exited successfully but no completed checkpoint was found"
                )
    _write_json(output / "laundrybench_training.json", run_record)
    return run_record
