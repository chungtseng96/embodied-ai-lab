from __future__ import annotations

import hashlib
import json
import shutil
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from laundrybench.policies.act import ACTContractError, LeRobotACTPolicy
from laundrybench.robot.so101_spec import SO101_JOINT_NAMES
from laundrybench.types import Observation


class Tensor:
    def __init__(self, value, *, shape=None):
        self.value = value
        self.shape = shape or getattr(value, "shape", None)
        self.dtype = getattr(value, "dtype", None)
        self.transforms = []

    def permute(self, *dims):
        self.transforms.append(("permute", dims))
        return self

    def div(self, value):
        self.transforms.append(("div", value))
        return self


class FakeTorch:
    float32 = "float32"
    uint8 = "uint8"

    @staticmethod
    def as_tensor(value, dtype=None):
        return Tensor(value)

    @staticmethod
    def inference_mode():
        return nullcontext()


class Frame:
    shape = (24, 32, 3)
    dtype = "uint8"


class FakeModel:
    def __init__(self, result):
        self.result = result
        self.config = SimpleNamespace(
            input_features={
                "observation.state": SimpleNamespace(shape=(6,)),
                "observation.images.front": SimpleNamespace(shape=(3, 24, 32)),
            },
            output_features={"action": SimpleNamespace(shape=(6,))},
        )
        self.reset_count = 0
        self.eval_called = False
        self.batch = None

    def eval(self):
        self.eval_called = True

    def reset(self):
        self.reset_count += 1

    def select_action(self, batch):
        self.batch = batch
        return self.result


class PolicyFiles:
    @staticmethod
    def create(tmp_path, *, joint_names=None, camera_size=(32, 24)):
        checkpoint = tmp_path / "checkpoint"
        checkpoint.mkdir(parents=True)
        state_files = {
            "policy_preprocessor_step_3_normalizer_processor.safetensors": b"normalizer state",
            "policy_postprocessor_step_0_unnormalizer_processor.safetensors": b"unnormalizer state",
        }
        for filename, contents in state_files.items():
            (checkpoint / filename).write_bytes(contents)
        (checkpoint / "policy_preprocessor.json").write_text(
            json.dumps({"steps": [{
                "registry_name": "normalizer_processor",
                "state_file": "policy_preprocessor_step_3_normalizer_processor.safetensors",
            }]}), encoding="utf-8"
        )
        (checkpoint / "policy_postprocessor.json").write_text(
            json.dumps({"steps": [{
                "registry_name": "unnormalizer_processor",
                "state_file": "policy_postprocessor_step_0_unnormalizer_processor.safetensors",
            }]}), encoding="utf-8"
        )
        (checkpoint / "config.json").write_text('{"type": "act"}', encoding="utf-8")
        weights = checkpoint / "model.safetensors"
        weights.write_bytes(b"mock safetensors payload")
        width, height = camera_size
        names = list(joint_names or SO101_JOINT_NAMES)
        native_names = [f"{name}.pos" for name in SO101_JOINT_NAMES]
        sha = hashlib.sha256(weights.read_bytes()).hexdigest()
        contract = {
            "schema_version": 1,
            "task": {"id": "sock-sort", "version": "v1"},
            "protocol": {"id": "home-bench", "version": "v2"},
            "dataset": {"repo_id": "lab/demos", "revision": "rev-001", "fps": 10},
            "checkpoint": {
                "path": "checkpoint-1000",
                "sha256": sha,
                "config_sha256": hashlib.sha256(b'{"type": "act"}').hexdigest(),
                "processor_sha256": {
                    name: hashlib.sha256((checkpoint / name).read_bytes()).hexdigest()
                    for name in ("policy_preprocessor.json", "policy_postprocessor.json")
                },
                "processor_state_sha256": {
                    name: hashlib.sha256(contents).hexdigest()
                    for name, contents in state_files.items()
                },
            },
            "lerobot_version": "0.6.1",
            "use_degrees": False,
            "joint_names": names,
            "joint_units": ["normalized"] * 6,
            "observation_features": {
                "state": {
                    "key": "observation.state",
                    "names": native_names,
                    "shape": [6],
                    "dtype": "float32",
                },
                "cameras": {
                    "observation.images.front": {"shape": [height, width, 3], "dtype": "uint8"}
                },
            },
            "action_features": {
                "key": "action",
                "names": native_names,
                "shape": [6],
                "dtype": "float32",
            },
            "cameras": {
                "front": {"width": width, "height": height, "color_mode": "RGB", "dtype": "uint8"}
            },
            "source_sha": "a" * 40,
            "normalization": {
                "coordinate_space": "normalized",
                "state_min": [-100, -100, -100, -100, -100, 0],
                "state_max": [100, 100, 100, 100, 100, 100],
                "action_min": [-100, -100, -100, -100, -100, 0],
                "action_max": [100, 100, 100, 100, 100, 100],
            },
        }
        contract_path = checkpoint / "policy_contract.json"
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        return checkpoint, contract_path


class Preprocessor:
    def __init__(self):
        self.inputs = []

    def __call__(self, inputs):
        self.inputs.append(inputs)
        return inputs


class Postprocessor:
    def __call__(self, output):
        return output


def observation(**updates):
    values = {
        "timestamp_s": 1.0,
        "joint_positions": [1, 2, 3, 4, 5, 6],
        "joint_names": SO101_JOINT_NAMES,
        "joint_units": "normalized",
        "images": {"front": Frame()},
    }
    values.update(updates)
    return Observation(**values)


def build_policy(tmp_path, result):
    checkpoint, contract = PolicyFiles.create(tmp_path)
    model = FakeModel(result)
    processor = Preprocessor()
    policy = LeRobotACTPolicy(
        checkpoint,
        contract,
        model=model,
        preprocessor=processor,
        postprocessor=Postprocessor(),
        torch_module=FakeTorch,
        expected_task="sock-sort",
        expected_protocol="home-bench",
        expected_dataset_id="lab/demos",
        expected_dataset_revision="rev-001",
    )
    return policy, model, processor


def test_act_preprocess_reset_inference_and_joint_order(tmp_path):
    policy, model, processor = build_policy(tmp_path, [10, 20, 30, 40, 50, 60])
    assert model.eval_called
    policy.reset()
    action = policy.act(observation())
    assert model.reset_count == 1
    assert action.joint_names == SO101_JOINT_NAMES
    assert action.joint_targets == [10, 20, 30, 40, 50, 60]
    inputs = processor.inputs[0]
    assert set(inputs) == {"observation.state", "observation.images.front"}
    image = inputs["observation.images.front"]
    assert image.transforms == [("permute", (2, 0, 1)), ("div", 255.0)]
    assert model.batch is inputs


@pytest.mark.parametrize(
    "updates",
    [
        {"joint_names": tuple(reversed(SO101_JOINT_NAMES))},
        {"joint_units": "degrees"},
        {"images": {"wrist": Frame()}},
        {"images": {"front": SimpleNamespace(shape=(24, 32, 3), dtype="float32")}},
    ],
)
def test_act_rejects_observation_contract_mismatch(tmp_path, updates):
    policy, _, _ = build_policy(tmp_path, [1, 2, 3, 4, 5, 6])
    with pytest.raises(ACTContractError):
        policy.act(observation(**updates))


@pytest.mark.parametrize("result", [[1, 2, 3, 4, 5, float("nan")], [101, 0, 0, 0, 0, 0]])
def test_act_rejects_nonfinite_and_out_of_range_outputs(tmp_path, result):
    policy, _, _ = build_policy(tmp_path, result)
    with pytest.raises(ACTContractError):
        policy.act(observation())


def test_act_refuses_contract_order_or_provenance_mismatch(tmp_path):
    checkpoint, contract = PolicyFiles.create(
        tmp_path, joint_names=list(reversed(SO101_JOINT_NAMES))
    )
    with pytest.raises(ACTContractError, match="joint layout"):
        LeRobotACTPolicy(
            checkpoint,
            contract,
            model=FakeModel([1, 2, 3, 4, 5, 6]),
            preprocessor=Preprocessor(),
            postprocessor=Postprocessor(),
            torch_module=FakeTorch,
        )
    checkpoint, contract = PolicyFiles.create(tmp_path / "other")
    with pytest.raises(ACTContractError, match="task.id mismatch"):
        LeRobotACTPolicy(
            checkpoint,
            contract,
            model=FakeModel([1, 2, 3, 4, 5, 6]),
            preprocessor=Preprocessor(),
            postprocessor=Postprocessor(),
            torch_module=FakeTorch,
            expected_task="different-task",
        )


@pytest.mark.parametrize("feature", ["state", "action"])
def test_contract_rejects_reordered_native_joint_features(tmp_path, feature):
    checkpoint, contract_path = PolicyFiles.create(tmp_path)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    field = "names"
    if feature == "state":
        contract["observation_features"][feature][field].reverse()
    else:
        contract["action_features"][field].reverse()
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    with pytest.raises(ACTContractError, match="exactly match canonical or native SO-101 names"):
        LeRobotACTPolicy(
            checkpoint,
            contract_path,
            model=FakeModel([1, 2, 3, 4, 5, 6]),
            preprocessor=Preprocessor(),
            postprocessor=Postprocessor(),
            torch_module=FakeTorch,
        )


def test_contract_accepts_exact_canonical_feature_name_aliases(tmp_path):
    checkpoint, contract_path = PolicyFiles.create(tmp_path)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["observation_features"]["state"]["names"] = list(SO101_JOINT_NAMES)
    contract["action_features"]["names"] = list(SO101_JOINT_NAMES)
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    policy = LeRobotACTPolicy(
        checkpoint,
        contract_path,
        model=FakeModel([1, 2, 3, 4, 5, 6]),
        preprocessor=Preprocessor(),
        postprocessor=Postprocessor(),
        torch_module=FakeTorch,
    )
    assert policy.act(observation()).joint_names == SO101_JOINT_NAMES


def test_checkpoint_contract_is_portable_but_binds_config_content(tmp_path):
    checkpoint, contract_path = PolicyFiles.create(tmp_path)
    copied = tmp_path / "portable-copy" / checkpoint.name
    copied.parent.mkdir()
    shutil.copytree(checkpoint, copied)
    copy_contract = copied / "policy_contract.json"
    policy = LeRobotACTPolicy(
        copied,
        copy_contract,
        model=FakeModel([1, 2, 3, 4, 5, 6]),
        preprocessor=Preprocessor(),
        postprocessor=Postprocessor(),
        torch_module=FakeTorch,
    )
    assert policy.checkpoint == copied.resolve()
    assert contract_path.exists()

    (copied / "config.json").write_text('{"type": "act", "tampered": true}', encoding="utf-8")
    with pytest.raises(ACTContractError, match="config.json SHA-256"):
        LeRobotACTPolicy(
            copied,
            copy_contract,
            model=FakeModel([1, 2, 3, 4, 5, 6]),
            preprocessor=Preprocessor(),
            postprocessor=Postprocessor(),
            torch_module=FakeTorch,
        )
