"""Lazy LeRobot ACT bridge with an explicit local checkpoint contract."""

from __future__ import annotations

import hashlib
import importlib
import json
import math
from numbers import Real
from pathlib import Path, PurePosixPath
from typing import Any

from laundrybench.robot.so101_spec import SO101_JOINT_NAMES
from laundrybench.types import Action, Observation


class ACTContractError(ValueError):
    """Checkpoint, processor, or live observation does not match its contract."""


class LeRobotACTPolicy:
    """LeRobot v0.6.1 ACT adapter. Importing this class never imports LeRobot/Torch."""

    name = "lerobot_act"

    def __init__(
        self,
        checkpoint: str | Path,
        contract_path: str | Path | None = None,
        *,
        device: str = "cpu",
        model: Any | None = None,
        preprocessor: Any | None = None,
        postprocessor: Any | None = None,
        torch_module: Any | None = None,
        expected_task: str | None = None,
        expected_protocol: str | None = None,
        expected_dataset_id: str | None = None,
        expected_dataset_revision: str | None = None,
    ) -> None:
        self.checkpoint = Path(checkpoint).expanduser().resolve()
        self.contract_path = (
            Path(contract_path).expanduser().resolve()
            if contract_path
            else self.checkpoint / "policy_contract.json"
        )
        self.device = device
        self.contract = load_act_contract(self.contract_path, self.checkpoint)
        self._validate_expected_provenance(
            expected_task, expected_protocol, expected_dataset_id, expected_dataset_revision
        )
        if (model is None) != (preprocessor is None) or (model is None) != (postprocessor is None):
            raise ValueError("model, preprocessor, and postprocessor must be injected together")
        if model is None:
            model, preprocessor, postprocessor, torch_module = _load_lerobot_checkpoint(
                self.checkpoint, device
            )
        if torch_module is None:
            torch_module = importlib.import_module("torch")
        self._model = model
        self._preprocessor = preprocessor
        self._postprocessor = postprocessor
        self._torch = torch_module
        _verify_model_features(self._model.config, self.contract)
        self._model.eval()

    def _validate_expected_provenance(
        self,
        task: str | None,
        protocol: str | None,
        dataset_id: str | None,
        dataset_revision: str | None,
    ) -> None:
        checks = (
            ("task.id", task, self.contract["task"]["id"]),
            ("protocol.id", protocol, self.contract["protocol"]["id"]),
            ("dataset.id", dataset_id, self.contract["dataset"]["repo_id"]),
            ("dataset.revision", dataset_revision, self.contract["dataset"]["revision"]),
        )
        for name, expected, found in checks:
            if expected is not None and expected != found:
                raise ACTContractError(
                    f"{name} mismatch: expected {expected!r}, contract has {found!r}"
                )

    def reset(self) -> None:
        self._model.reset()

    def act(self, observation: Observation) -> Action:
        if tuple(observation.joint_names) != SO101_JOINT_NAMES:
            raise ACTContractError("live joint names/order do not match the SO-101 contract")
        if observation.joint_units != "normalized":
            raise ACTContractError(
                "live joint units must be normalized as declared by the checkpoint"
            )
        if len(observation.joint_positions) != 6 or any(
            isinstance(value, bool)
            or not isinstance(value, Real)
            or not math.isfinite(float(value))
            for value in observation.joint_positions
        ):
            raise ACTContractError("live joint positions must contain six finite normalized values")
        positions = [float(value) for value in observation.joint_positions]
        if (
            any(value < -100 or value > 100 for value in positions[:-1])
            or not 0 <= positions[-1] <= 100
        ):
            raise ACTContractError("live joint positions are outside normalized SO-101 ranges")
        contract_cameras = self.contract["cameras"]
        if set(observation.images) != set(contract_cameras):
            raise ACTContractError(
                "camera keys mismatch: "
                f"expected {sorted(contract_cameras)}, got {sorted(observation.images)}"
            )

        inputs: dict[str, Any] = {"observation.state": self._tensor(positions, dtype="float32")}
        for name, spec in contract_cameras.items():
            frame = observation.images[name]
            height, width = spec["height"], spec["width"]
            if frame is None or getattr(frame, "shape", None) != (height, width, 3):
                raise ACTContractError(f"camera {name!r} must be an HWC {height}x{width} RGB frame")
            if getattr(frame, "dtype", None) is None or str(frame.dtype) not in (
                "uint8",
                "torch.uint8",
            ):
                raise ACTContractError(f"camera {name!r} must have uint8 RGB pixels")
            # LeRobot's ACT image features are CHW float tensors in [0,1]. Convert explicitly;
            # the saved pipeline still owns normalization and device placement.
            image = self._torch.as_tensor(frame, dtype=self._torch.float32)
            image = image.permute(2, 0, 1).div(255.0)
            inputs[f"observation.images.{name}"] = image

        batch = self._preprocessor(inputs)
        with self._torch.inference_mode():
            raw = self._model.select_action(batch)
            output = self._postprocessor(raw)
        if hasattr(output, "detach"):
            output = output.detach().cpu().numpy()
        values = _flat_six_values(output)
        if not all(math.isfinite(value) for value in values):
            raise ACTContractError("ACT produced a non-finite joint target")
        if any(value < -100 or value > 100 for value in values[:-1]) or not 0 <= values[-1] <= 100:
            raise ACTContractError("ACT output is outside normalized SO-101 joint ranges")
        return Action(
            joint_targets=values,
            metadata={
                "policy": self.name,
                "output_units": "normalized",
                "checkpoint": str(self.checkpoint),
            },
        )

    def _tensor(self, values: list[float], *, dtype: str) -> Any:
        return self._torch.as_tensor(values, dtype=getattr(self._torch, dtype))


def load_act_contract(path: Path, checkpoint: Path) -> dict:
    if not checkpoint.is_dir():
        raise ACTContractError(f"checkpoint must be an existing local directory: {checkpoint}")
    required = (
        "config.json",
        "model.safetensors",
        "policy_preprocessor.json",
        "policy_postprocessor.json",
    )
    missing = [name for name in required if not (checkpoint / name).is_file()]
    if missing:
        raise ACTContractError(
            f"checkpoint is missing required LeRobot files: {', '.join(missing)}"
        )
    try:
        checkpoint_config = json.loads((checkpoint / "config.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ACTContractError("checkpoint config.json is not valid JSON") from error
    if not isinstance(checkpoint_config, dict) or checkpoint_config.get("type") != "act":
        raise ACTContractError("checkpoint config.json must identify LeRobot policy type 'act'")
    if not path.is_file():
        raise ACTContractError(f"explicit policy contract file is missing: {path}")
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ACTContractError(f"invalid policy contract JSON: {path}") from error
    required_top = {
        "schema_version",
        "task",
        "protocol",
        "dataset",
        "checkpoint",
        "lerobot_version",
        "use_degrees",
        "joint_names",
        "joint_units",
        "observation_features",
        "action_features",
        "cameras",
        "source_sha",
        "normalization",
    }
    if not isinstance(contract, dict) or set(contract) != required_top:
        raise ACTContractError(
            f"policy contract must have exactly: {', '.join(sorted(required_top))}"
        )
    if type(contract["schema_version"]) is not int or contract["schema_version"] != 1:
        raise ACTContractError("only policy contract schema_version=1 is supported")
    for section in ("task", "protocol", "dataset", "checkpoint"):
        if not isinstance(contract[section], dict):
            raise ACTContractError(f"contract {section} must be an object")
    for section in ("task", "protocol"):
        if contract[section].keys() != {"id", "version"} or any(
            not isinstance(item, str) or not item for item in contract[section].values()
        ):
            raise ACTContractError(f"contract {section} must declare id and version")
    if contract["dataset"].keys() != {"repo_id", "revision", "fps"}:
        raise ACTContractError("dataset must declare repo_id, revision and fps")
    if (
        not isinstance(contract["dataset"]["repo_id"], str)
        or not contract["dataset"]["repo_id"]
        or not isinstance(contract["dataset"]["revision"], str)
        or not contract["dataset"]["revision"]
    ):
        raise ACTContractError("dataset repo_id and revision must be explicit non-empty strings")
    if type(contract["dataset"]["fps"]) is not int or contract["dataset"]["fps"] <= 0:
        raise ACTContractError("dataset fps must be an explicit positive integer")
    if contract["checkpoint"].keys() != {
        "path", "sha256", "config_sha256", "processor_sha256", "processor_state_sha256"
    }:
        raise ACTContractError(
            "checkpoint must declare portable path, config/model digests and processor digests"
        )
    checkpoint_locator = contract["checkpoint"]["path"]
    if (
        not isinstance(checkpoint_locator, str)
        or not checkpoint_locator
        or PurePosixPath(checkpoint_locator).is_absolute()
        or ".." in PurePosixPath(checkpoint_locator).parts
        or "\\" in checkpoint_locator
    ):
        raise ACTContractError("checkpoint path must be a portable relative locator")
    if (
        not isinstance(contract["source_sha"], str)
        or len(contract["source_sha"]) != 40
        or any(char not in "0123456789abcdef" for char in contract["source_sha"].lower())
    ):
        raise ACTContractError("contract source_sha must be a 40-character git commit")
    if contract["joint_names"] != list(SO101_JOINT_NAMES) or contract["joint_units"] not in (
        "normalized",
        ["normalized"] * 6,
    ):
        raise ACTContractError("checkpoint joint layout/units must exactly match normalized SO-101")
    if contract["use_degrees"] is not False:
        raise ACTContractError("checkpoint contract must explicitly declare use_degrees=false")
    normalization = contract["normalization"]
    expected_bounds = {
        "state_min": [-100, -100, -100, -100, -100, 0],
        "state_max": [100, 100, 100, 100, 100, 100],
        "action_min": [-100, -100, -100, -100, -100, 0],
        "action_max": [100, 100, 100, 100, 100, 100],
    }
    if not isinstance(normalization, dict) or set(normalization) != {
        "coordinate_space",
        *expected_bounds,
    }:
        raise ACTContractError(
            "normalization must declare coordinate_space and explicit state/action bounds"
        )
    if normalization["coordinate_space"] != "normalized" or any(
        not isinstance(normalization[key], list)
        or len(normalization[key]) != 6
        or any(
            isinstance(item, bool) or not isinstance(item, Real) or not math.isfinite(item)
            for item in normalization[key]
        )
        or normalization[key] != bounds
        for key, bounds in expected_bounds.items()
    ):
        raise ACTContractError(
            "checkpoint coordinate bounds must be normalized SO-101 identity units"
        )
    observation_features = contract["observation_features"]
    action_features = contract["action_features"]
    if not isinstance(observation_features, dict) or set(observation_features) != {
        "state",
        "cameras",
    }:
        raise ACTContractError("observation_features must declare state and cameras")
    state_feature = observation_features["state"]
    if not isinstance(state_feature, dict) or set(state_feature) != {
        "key",
        "names",
        "shape",
        "dtype",
    }:
        raise ACTContractError("state feature must declare key, names, shape and dtype")
    state_joint_names = _canonical_so101_names(state_feature["names"], "state")
    if (
        state_feature["key"] != "observation.state"
        or state_joint_names != list(SO101_JOINT_NAMES)
        or state_feature["shape"] != [6]
        or state_feature["dtype"] != "float32"
    ):
        raise ACTContractError(
            "state feature layout must explicitly match normalized SO-101 float32"
        )
    if not isinstance(action_features, dict) or set(action_features) != {
        "key",
        "names",
        "shape",
        "dtype",
    }:
        raise ACTContractError("action_features must declare key, names, shape and dtype")
    action_joint_names = _canonical_so101_names(action_features["names"], "action")
    if (
        action_features["key"] != "action"
        or action_joint_names != list(SO101_JOINT_NAMES)
        or action_features["shape"] != [6]
        or action_features["dtype"] != "float32"
    ):
        raise ACTContractError(
            "action feature layout must explicitly match normalized SO-101 float32"
        )
    cameras = contract["cameras"]
    if not isinstance(cameras, dict) or not cameras:
        raise ACTContractError("contract must declare at least one named camera")
    camera_features = observation_features["cameras"]
    if not isinstance(camera_features, dict) or set(camera_features) != {
        f"observation.images.{name}" for name in cameras
    }:
        raise ACTContractError("camera feature keys do not match contract camera names")
    for name, spec in cameras.items():
        if not isinstance(name, str) or not name or not isinstance(spec, dict):
            raise ACTContractError("camera contracts must be named objects")
        if set(spec) != {"width", "height", "color_mode", "dtype"}:
            raise ACTContractError(f"camera contract {name!r} has unsupported fields")
        if any(type(spec[key]) is not int or spec[key] <= 0 for key in ("width", "height")):
            raise ACTContractError(f"camera {name!r} width/height must be positive integers")
        if spec["color_mode"] != "RGB" or spec["dtype"] != "uint8":
            raise ACTContractError(f"camera {name!r} contract must state RGB uint8")
        feature = camera_features[f"observation.images.{name}"]
        if feature != {"shape": [spec["height"], spec["width"], 3], "dtype": "uint8"}:
            raise ACTContractError(
                f"camera feature {name!r} dimensions/dtype do not match camera contract"
            )
    if contract["lerobot_version"] != "0.6.1":
        raise ACTContractError("ACT bridge currently supports only contract LeRobot version 0.6.1")
    if contract["checkpoint"].get("sha256") != _sha256(checkpoint / "model.safetensors"):
        raise ACTContractError("checkpoint model.safetensors SHA-256 does not match the contract")
    if contract["checkpoint"].get("config_sha256") != _sha256(checkpoint / "config.json"):
        raise ACTContractError("checkpoint config.json SHA-256 does not match the contract")
    processor_hashes = contract["checkpoint"]["processor_sha256"]
    processor_names = {"policy_preprocessor.json", "policy_postprocessor.json"}
    if not isinstance(processor_hashes, dict) or set(processor_hashes) != processor_names:
        raise ACTContractError("contract must bind both saved policy processor files by SHA-256")
    for name in processor_names:
        if processor_hashes[name] != _sha256(checkpoint / name):
            raise ACTContractError(f"checkpoint processor SHA-256 mismatch for {name}")
    state_hashes = contract["checkpoint"]["processor_state_sha256"]
    if not isinstance(state_hashes, dict):
        raise ACTContractError(
            "contract processor_state_sha256 must map filenames to SHA-256 values"
        )
    referenced_state_files = _processor_state_files(checkpoint)
    if set(state_hashes) != referenced_state_files:
        raise ACTContractError(
            "contract processor state files do not match saved processor references"
        )
    for name in referenced_state_files:
        if state_hashes[name] != _sha256(checkpoint / name):
            raise ACTContractError(f"checkpoint processor state SHA-256 mismatch for {name}")
    return contract


def _load_lerobot_checkpoint(checkpoint: Path, device: str) -> tuple[Any, Any, Any, Any]:
    try:
        importlib.metadata.version("lerobot")
    except importlib.metadata.PackageNotFoundError as error:
        raise RuntimeError(
            "LeRobot 0.6.1 is required; install the optional LeRobot environment"
        ) from error
    torch = importlib.import_module("torch")
    if importlib.metadata.version("lerobot") != "0.6.1":
        raise RuntimeError("ACT bridge was verified for LeRobot 0.6.1 only")
    from lerobot.policies import make_pre_post_processors
    from lerobot.policies.act.modeling_act import ACTPolicy

    model = ACTPolicy.from_pretrained(str(checkpoint), local_files_only=True, strict=True)
    model.to(device)
    preprocessor, postprocessor = make_pre_post_processors(
        policy_cfg=model.config,
        pretrained_path=str(checkpoint),
        preprocessor_overrides={"device_processor": {"device": device}},
    )
    return model, preprocessor, postprocessor, torch


def _flat_six_values(value: Any) -> list[float]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    while isinstance(value, (list, tuple)) and len(value) == 1:
        value = value[0]
    if not isinstance(value, (list, tuple)) or len(value) != 6:
        raise ACTContractError("ACT must return one six-joint action")
    try:
        if any(isinstance(item, bool) for item in value):
            raise TypeError("boolean action value")
        return [float(item) for item in value]
    except (TypeError, ValueError) as error:
        raise ACTContractError("ACT action must contain numeric joint values") from error


def _canonical_so101_names(feature_names: Any, feature: str) -> list[str]:
    """Normalize only exact known bare or native LeRobot `.pos` name lists."""
    canonical = list(SO101_JOINT_NAMES)
    native = [f"{name}.pos" for name in SO101_JOINT_NAMES]
    if not isinstance(feature_names, list) or feature_names not in (canonical, native):
        raise ACTContractError(
            f"{feature} feature names/order must exactly match canonical or native SO-101 names"
        )
    if feature_names == native:
        return [name.removesuffix(".pos") for name in feature_names]
    return feature_names


def _verify_model_features(model_config: Any, contract: dict) -> None:
    input_features = getattr(model_config, "input_features", None)
    output_features = getattr(model_config, "output_features", None)
    cameras = contract["cameras"]
    if not isinstance(input_features, dict) or not isinstance(output_features, dict):
        raise ACTContractError("loaded ACT config must expose input_features and output_features")
    expected_inputs = {"observation.state"} | {f"observation.images.{name}" for name in cameras}
    if set(input_features) != expected_inputs or set(output_features) != {"action"}:
        raise ACTContractError("loaded ACT feature keys do not match the training contract")
    if tuple(input_features["observation.state"].shape) != (6,):
        raise ACTContractError("loaded ACT state feature must have six joints")
    if tuple(output_features["action"].shape) != (6,):
        raise ACTContractError("loaded ACT action feature must have six joints")
    for name, spec in cameras.items():
        actual_shape = tuple(input_features[f"observation.images.{name}"].shape)
        expected_shape = (3, spec["height"], spec["width"])
        if actual_shape != expected_shape:
            raise ACTContractError(
                f"loaded ACT camera {name!r} shape {actual_shape} does not match {expected_shape}"
            )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _processor_state_files(checkpoint: Path) -> set[str]:
    references: set[str] = set()
    stateful_steps: set[str] = set()
    for processor_name in ("policy_preprocessor.json", "policy_postprocessor.json"):
        try:
            document = json.loads((checkpoint / processor_name).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ACTContractError(f"saved processor {processor_name} is invalid JSON") from error
        if not isinstance(document, dict) or not isinstance(document.get("steps"), list):
            raise ACTContractError(f"saved processor {processor_name} must declare a steps list")
        for step in document["steps"]:
            if not isinstance(step, dict):
                raise ACTContractError(f"saved processor {processor_name} has an invalid step")
            registry_name = step.get("registry_name")
            state_file = step.get("state_file")
            if state_file is None:
                if registry_name in ("normalizer_processor", "unnormalizer_processor"):
                    raise ACTContractError(
                        f"processor {processor_name} {registry_name} must declare state_file"
                    )
                continue
            if (
                not isinstance(state_file, str)
                or not state_file
                or PurePosixPath(state_file).is_absolute()
                or len(PurePosixPath(state_file).parts) != 1
                or "\\" in state_file
                or state_file in references
            ):
                raise ACTContractError(
                    "processor state_file references must be unique safe basenames"
                )
            state_path = checkpoint / state_file
            if state_path.is_symlink() or not state_path.is_file():
                raise ACTContractError(
                    f"referenced processor state file is missing or unsafe: {state_file}"
                )
            references.add(state_file)
            if registry_name in ("normalizer_processor", "unnormalizer_processor"):
                stateful_steps.add(registry_name)
    if stateful_steps != {"normalizer_processor", "unnormalizer_processor"}:
        raise ACTContractError(
            "ACT checkpoint must include normalizer and unnormalizer state files"
        )
    state_files_on_disk = set()
    for state_path in checkpoint.glob("policy_*_step_*.safetensors"):
        if state_path.is_symlink():
            raise ACTContractError("processor state files cannot be symlinks")
        if state_path.is_file():
            state_files_on_disk.add(state_path.name)
    if state_files_on_disk != references:
        raise ACTContractError(
            "on-disk processor state files do not match saved processor references"
        )
    return references
