"""Supervised physical LaundryBench runner with provisional, human-reviewed outcomes."""

from __future__ import annotations

import json
import math
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from laundrybench.evaluation.capture import CameraVideoSpec, EpisodeCapture
from laundrybench.evaluation.experiment import run_experiment
from laundrybench.evaluation.metadata import write_experiment_metadata
from laundrybench.observability.manifest import RunManifest, git_revision, write_manifest
from laundrybench.policies.base import Policy
from laundrybench.robot.base import Robot
from laundrybench.robot.so101_spec import SO101_JOINT_NAMES
from laundrybench.types import Action, EpisodeResult, FailureCategory, Observation


class PendingPhysicalJudge:
    """Physical outcomes are always provisional until a person labels them."""

    failure_category = FailureCategory.UNSPECIFIED

    def is_success(self, observation: Observation) -> bool:
        del observation
        return False

    def on_timeout(self, observation: Observation) -> bool:
        del observation
        return False


def run_physical_experiment(
    *,
    experiment_dir: Path,
    config_path: Path,
    config: dict[str, Any],
    robot: Robot,
    policy: Policy,
    lerobot_version: str,
) -> list:
    """Run a finite supervised physical protocol and guarantee teardown on every path."""
    output = Path(experiment_dir)
    try:
        output.mkdir(parents=True, exist_ok=False)
        return _run_physical(output, Path(config_path), config, robot, policy, lerobot_version)
    finally:
        robot.stop()


def _run_physical(
    output: Path,
    config_path: Path,
    config: dict[str, Any],
    robot: Robot,
    policy: Policy,
    lerobot_version: str,
) -> list:
    runtime = config["runtime"]
    task = config["task"]
    protocol = config["protocol"]
    dataset = config["dataset"]
    checkpoint = config["checkpoint"]
    manifest = RunManifest(
        experiment_id=config["experiment_id"],
        created_at=datetime.now(UTC).isoformat(),
        git_revision=git_revision(Path(__file__).resolve().parents[5]),
        config_hash=_sha256(config_path),
        seed=0,
        policy_name=policy.name,
        robot_implementation="so101_lerobot",
        python_version=sys.version.split()[0],
        lerobot_version=lerobot_version,
    )
    # RunManifest is emitted before the runner so a partial run retains provenance.
    write_manifest(output / "manifest.yaml", manifest)
    contract_file = Path(checkpoint["contract_path"]).expanduser()
    if not contract_file.is_absolute():
        contract_file = (config_path.parent / contract_file).resolve()
    policy_contract = getattr(policy, "contract", {})
    context = {
        "schema_version": 1,
        "name": "Physical ACT rollout",
        "hypothesis": None,
        "what_changed": "Supervised bounded physical ACT evaluation",
        "task": task,
        "protocol": protocol,
        "dataset": {"id": dataset["id"], "revision": dataset["revision"]},
        "checkpoint": {"identity": checkpoint["identity"]},
        "effective_overrides": {
            "robot": config["robot"],
            "cameras": config["cameras"],
            "runtime": runtime,
            "checkpoint_path": checkpoint["path"],
            "policy_contract_path": checkpoint["contract_path"],
            "policy_contract_sha256": _sha256(contract_file),
            "checkpoint_model_sha256": policy_contract.get("checkpoint", {}).get("sha256"),
            "checkpoint_processor_sha256": policy_contract.get("checkpoint", {}).get(
                "processor_sha256"
            ),
            "training_source_sha": policy_contract.get("source_sha"),
            "lerobot_version": lerobot_version,
            "operator_supervised": True,
        },
    }
    write_experiment_metadata(output, context)
    capture = EpisodeCapture(
        output,
        cameras={
            name: CameraVideoSpec(
                width=camera["width"],
                height=camera["height"],
                fps=runtime["control_hz"],
            )
            for name, camera in config["cameras"].items()
        },
        max_duration_s=runtime["timeout_s"],
        max_frames=math.ceil(runtime["timeout_s"] * runtime["control_hz"]) + 2,
    )
    command_path = output / "traces" / "commands.jsonl"
    command_path.parent.mkdir(parents=True, exist_ok=True)

    def on_observation(episode_id: str, step: int, observation: Observation) -> None:
        if not capture.active:
            capture.start(episode_id)
        capture.observe(observation)

    def on_apply(episode_id: str, step: int, observation: Observation, action: Action) -> None:
        sent = getattr(robot, "last_sent_action", None)
        if not isinstance(sent, dict):
            raise TypeError("physical robot adapter did not report its actual sent action")
        namespaced = {f"{name}.pos": name for name in SO101_JOINT_NAMES}
        missing = set(namespaced) - set(sent)
        if missing:
            raise RuntimeError(
                f"SO-101 adapter actual command is missing joints: {sorted(missing)}"
            )
        sent_targets = [float(sent[f"{name}.pos"]) for name in SO101_JOINT_NAMES]
        if not all(math.isfinite(value) for value in sent_targets):
            raise RuntimeError("SO-101 adapter reported non-finite sent command values")
        if (
            any(value < -100 or value > 100 for value in sent_targets[:-1])
            or not 0 <= sent_targets[-1] <= 100
        ):
            raise RuntimeError(
                "SO-101 adapter reported sent command outside normalized joint ranges"
            )
        record = {
            "episode_id": episode_id,
            "step": step,
            "requested_joint_targets": list(action.joint_targets),
            "requested_joint_names": list(action.joint_names),
            "sent_joint_targets": sent_targets,
            "sent_joint_names": list(SO101_JOINT_NAMES),
            "max_relative_target": runtime["max_relative_target"],
            "command_timestamp_s": time.time(),
            "observation_timestamp_s": observation.timestamp_s,
        }
        with command_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    def on_episode_complete(result: EpisodeResult) -> None:
        if capture.active:
            capture.finalize()

    try:
        return run_experiment(
            output,
            manifest,
            robot=robot,
            policy=policy,
            judge=PendingPhysicalJudge(),
            episodes=runtime["episodes"],
            control_hz=runtime["control_hz"],
            timeout_s=runtime["timeout_s"],
            on_observation=on_observation,
            on_apply=on_apply,
            on_episode_complete=on_episode_complete,
            refresh_observation_before_action=True,
        )
    except BaseException as error:
        if capture.active:
            capture.abort(f"physical rollout failed: {error}")
        raise


def load_rollout_config(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"cannot read rollout config {path}: {error}") from error
    return validate_rollout_config(value)


def validate_rollout_config(value: Any) -> dict[str, Any]:
    expected = {
        "experiment_id",
        "task",
        "protocol",
        "dataset",
        "checkpoint",
        "runtime",
        "robot",
        "cameras",
        "output_dir",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"rollout config must contain exactly: {', '.join(sorted(expected))}")
    if (
        not isinstance(value["experiment_id"], str)
        or re.fullmatch(r"exp-\d{3}-[a-z0-9-]+", value["experiment_id"]) is None
    ):
        raise ValueError("experiment_id must match exp-NNN-lowercase-name")
    for name in ("task", "protocol", "dataset", "checkpoint", "runtime", "robot"):
        if not isinstance(value[name], dict):
            raise TypeError(f"{name} must be an object")
    value = dict(value)
    value["runtime"] = dict(value["runtime"])
    for section in ("task", "protocol"):
        if set(value[section]) != {"id", "version"} or not all(value[section].values()):
            raise ValueError(f"{section} must declare non-empty id and version")
    if (
        set(value["dataset"]) != {"id", "revision", "fps"}
        or not value["dataset"]["id"]
        or not value["dataset"]["revision"]
    ):
        raise ValueError("dataset must declare non-empty id, revision, and fps")
    if type(value["dataset"]["fps"]) is not int or value["dataset"]["fps"] <= 0:
        raise ValueError("dataset.fps must be a positive integer")
    if set(value["checkpoint"]) != {"path", "contract_path", "identity"} or not all(
        value["checkpoint"].values()
    ):
        raise ValueError("checkpoint must declare local path, contract_path, and identity")
    runtime_keys = {"episodes", "control_hz", "timeout_s", "max_relative_target", "device"}
    if set(value["runtime"]) != runtime_keys:
        raise ValueError(f"runtime must contain exactly: {', '.join(sorted(runtime_keys))}")
    if type(value["runtime"]["episodes"]) is not int or not 1 <= value["runtime"]["episodes"] <= 10:
        raise ValueError("episodes must be an integer from 1 through 10")
    for key in ("control_hz", "timeout_s", "max_relative_target"):
        number = value["runtime"][key]
        if (
            isinstance(number, bool)
            or not isinstance(number, (int, float))
            or not math.isfinite(number)
            or number <= 0
        ):
            raise ValueError(f"runtime.{key} must be finite and positive")
    if value["runtime"]["timeout_s"] > 120 or value["runtime"]["control_hz"] > 30:
        raise ValueError("physical rollout is capped at 120 seconds per episode and 30 Hz")
    if value["runtime"]["control_hz"] != value["dataset"]["fps"]:
        raise ValueError(
            "runtime.control_hz must exactly match trained dataset fps; no resampling is supported"
        )
    if value["runtime"]["max_relative_target"] > 5:
        raise ValueError(
            "runtime.max_relative_target is capped at 5 normalized position units per command"
        )
    value["runtime"]["max_relative_target"] = float(value["runtime"]["max_relative_target"])
    if not float(value["runtime"]["control_hz"]).is_integer():
        raise ValueError(
            "runtime.control_hz must be an integer cadence for physical evidence capture"
        )
    if value["runtime"]["device"] not in ("cpu", "cuda", "mps"):
        raise ValueError("runtime.device must be cpu, cuda, or mps")
    if set(value["robot"]) != {"port", "id"} or not all(value["robot"].values()):
        raise ValueError("robot must explicitly declare follower port and calibrated id")
    if not isinstance(value["cameras"], dict) or not value["cameras"]:
        raise ValueError("cameras must declare at least one named camera")
    for name, camera in value["cameras"].items():
        if (
            not isinstance(name, str)
            or not isinstance(camera, dict)
            or set(camera) != {"index_or_path", "width", "height", "fps"}
        ):
            raise ValueError(f"camera {name!r} must declare index_or_path, width, height and fps")
        if any(
            type(camera[key]) is not int or camera[key] <= 0 for key in ("width", "height", "fps")
        ):
            raise ValueError(f"camera {name!r} dimensions and fps must be positive integers")
        if camera["width"] % 2 or camera["height"] % 2:
            raise ValueError(f"camera {name!r} width and height must be even for H.264 evidence")
        source = camera["index_or_path"]
        if isinstance(source, bool) or not isinstance(source, (int, str)):
            raise TypeError(f"camera {name!r} index_or_path must be an integer or path")
        if isinstance(source, int) and source < 0 or isinstance(source, str) and not source.strip():
            raise ValueError(f"camera {name!r} index_or_path is invalid")
        if camera["fps"] < value["runtime"]["control_hz"]:
            raise ValueError(f"camera {name!r} acquisition fps cannot be lower than control_hz")
    if len({camera["fps"] for camera in value["cameras"].values()}) != 1:
        raise ValueError("all camera acquisition fps values must match")
    if not isinstance(value["output_dir"], str) or not value["output_dir"]:
        raise ValueError("output_dir must be explicit")
    return value


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
