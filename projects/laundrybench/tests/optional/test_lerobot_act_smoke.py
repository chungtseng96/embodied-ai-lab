"""Optional real-package ACT integration probe (CPU only, no downloaded weights)."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def test_cpu_act_checkpoint_processors_and_laundrybench_adapter(tmp_path: Path) -> None:
    torch = pytest.importorskip("torch", reason="optional ACT smoke needs PyTorch")
    pytest.importorskip("lerobot", reason="optional ACT smoke needs LeRobot")
    np = pytest.importorskip("numpy", reason="optional ACT smoke needs NumPy")

    if sys.platform == "darwin" and platform.machine().lower() in {"x86_64", "amd64"}:
        pytest.skip("Intel macOS uses the PyAV edge profile; TorchCodec ACT smoke runs on Linux")
    try:
        torchcodec_version = importlib.metadata.version("torchcodec")
    except importlib.metadata.PackageNotFoundError:
        pytest.skip("optional ACT smoke needs the Linux TorchCodec runtime")
    if not torch.__version__.startswith("2.7.1"):
        pytest.skip("optional ACT smoke requires the pinned PyTorch 2.7.1 runtime")

    from lerobot.configs.types import FeatureType, PolicyFeature
    from lerobot.policies import make_pre_post_processors
    from lerobot.policies.act.configuration_act import ACTConfig
    from lerobot.policies.act.modeling_act import ACTPolicy

    from laundrybench.policies.act import LeRobotACTPolicy
    from laundrybench.robot.so101_spec import SO101_JOINT_NAMES
    from laundrybench.training.act import _make_policy_contract
    from laundrybench.types import Observation

    assert importlib.metadata.version("lerobot") == "0.6.1"
    assert torchcodec_version in {"0.5", "0.5.0"}
    assert not torch.cuda.is_available()
    train_help = subprocess.run(
        [sys.executable, "-m", "lerobot.scripts.lerobot_train", "--help"],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert train_help.returncode == 0, train_help.stderr

    checkpoint = tmp_path / "generated_act_checkpoint"
    checkpoint.mkdir()
    camera_height = camera_width = 32
    config = ACTConfig(
        input_features={
            "observation.state": PolicyFeature(FeatureType.STATE, (6,)),
            "observation.images.front": PolicyFeature(
                FeatureType.VISUAL, (3, camera_height, camera_width)
            ),
        },
        output_features={"action": PolicyFeature(FeatureType.ACTION, (6,))},
        device="cpu",
        push_to_hub=False,
        pretrained_backbone_weights=None,
        chunk_size=2,
        n_action_steps=1,
        dim_model=32,
        n_heads=4,
        dim_feedforward=64,
        n_encoder_layers=1,
        n_decoder_layers=1,
        latent_dim=8,
        n_vae_encoder_layers=1,
    )
    # These deliberately non-identity values exercise LeRobot's saved
    # normalizer/unnormalizer state, rather than an injected fake processor.
    stats = {
        "observation.state": {
            "mean": torch.tensor([20, 10, 0, -10, -20, 50], dtype=torch.float32),
            "std": torch.tensor([10, 5, 2, 4, 8, 10], dtype=torch.float32),
            "min": torch.tensor([-100, -100, -100, -100, -100, 0], dtype=torch.float32),
            "max": torch.tensor([100, 100, 100, 100, 100, 100], dtype=torch.float32),
        },
        "observation.images.front": {
            "mean": torch.tensor([0.25, 0.5, 0.75], dtype=torch.float32).view(3, 1, 1),
            "std": torch.tensor([0.5, 0.25, 0.125], dtype=torch.float32).view(3, 1, 1),
            "min": torch.zeros(3, 1, 1, dtype=torch.float32),
            "max": torch.ones(3, 1, 1, dtype=torch.float32),
        },
        "action": {
            "mean": torch.tensor([10, -10, 20, -20, 5, 50], dtype=torch.float32),
            "std": torch.tensor([10, 10, 10, 10, 10, 10], dtype=torch.float32),
            "min": torch.tensor([-100, -100, -100, -100, -100, 0], dtype=torch.float32),
            "max": torch.tensor([100, 100, 100, 100, 100, 100], dtype=torch.float32),
        },
    }
    model = ACTPolicy(config)
    # A valid deterministic zero-output checkpoint keeps the smoke action
    # safely inside the normalized SO-101 ranges while testing real ACT code.
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.zero_()
    model.save_pretrained(checkpoint, push_to_hub=False)
    preprocessor, postprocessor = make_pre_post_processors(
        policy_cfg=config,
        dataset_stats=stats,
    )
    preprocessor.save_pretrained(
        checkpoint,
        push_to_hub=False,
        config_filename="policy_preprocessor.json",
    )
    postprocessor.save_pretrained(
        checkpoint,
        push_to_hub=False,
        config_filename="policy_postprocessor.json",
    )

    source_root = Path(__file__).resolve().parents[4]
    source_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    camera_feature = "observation.images.front"
    native_joint_features = [f"{name}.pos" for name in SO101_JOINT_NAMES]
    # Exercise the actual training contract producer against this real saved
    # LeRobot ACT checkpoint and its processor state files. This catches drift
    # between what training emits and what the runtime accepts.
    training = {
        "task": {"id": "cpu-act-smoke", "version": "v1"},
        "protocol": {"id": "generated-checkpoint", "version": "v1"},
        "dataset_id": "local/generated-smoke",
        "dataset_revision": "synthetic-v1",
    }
    contract_spec = {
        "joint_names": list(SO101_JOINT_NAMES),
        "state_names": native_joint_features,
        "action_names": native_joint_features,
        "normalization": {
            "coordinate_space": "normalized",
            "state_min": [-100, -100, -100, -100, -100, 0],
            "state_max": [100, 100, 100, 100, 100, 100],
            "action_min": [-100, -100, -100, -100, -100, 0],
            "action_max": [100, 100, 100, 100, 100, 100],
        },
        "cameras": {
            "front": {
                "width": camera_width,
                "height": camera_height,
                "color": "RGB",
                "dtype": "uint8",
            }
        },
    }
    producer_contract = _make_policy_contract(
        training,
        {"contract": contract_spec, "dataset_fps": 1},
        "0.6.1",
        checkpoint,
        source_sha=source_sha,
    )
    contract = producer_contract
    contract_path = checkpoint / "policy_contract.json"
    contract_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

    policy = LeRobotACTPolicy(checkpoint, contract_path, device="cpu")
    assert policy._model.__class__.__module__ == "lerobot.policies.act.modeling_act"
    assert policy._model.config.pretrained_backbone_weights is None

    live_state = [30.0, 0.0, 2.0, -2.0, -4.0, 60.0]
    live_frame = np.full((camera_height, camera_width, 3), 128, dtype=np.uint8)
    tensor_inputs = {
        "observation.state": torch.tensor(live_state, dtype=torch.float32),
        camera_feature: torch.as_tensor(live_frame, dtype=torch.float32).permute(2, 0, 1) / 255.0,
    }
    processed = policy._preprocessor(tensor_inputs)
    torch.testing.assert_close(
        processed["observation.state"],
        torch.tensor([[1.0, -2.0, 1.0, 2.0, 2.0, 1.0]], dtype=torch.float32),
    )
    expected_rgb = (128.0 / 255.0 - torch.tensor([0.25, 0.5, 0.75])) / torch.tensor(
        [0.5, 0.25, 0.125]
    )
    torch.testing.assert_close(
        processed[camera_feature][0, :, 0, 0],
        expected_rgb,
    )

    policy.reset()
    action = policy.act(
        Observation(
            timestamp_s=1.0,
            joint_positions=live_state,
            joint_names=SO101_JOINT_NAMES,
            joint_units="normalized",
            images={"front": live_frame},
        )
    )
    assert action.joint_names == SO101_JOINT_NAMES
    assert action.joint_targets == pytest.approx([10, -10, 20, -20, 5, 50], abs=1e-5)
    assert all(
        math.isfinite(value) and (-100 <= value <= 100) for value in action.joint_targets[:-1]
    )
    assert math.isfinite(action.joint_targets[-1])
    assert 0 <= action.joint_targets[-1] <= 100

    _test_lerobot_torchcodec_video_decode(tmp_path)
    _test_native_cpu_training_step(tmp_path)


def _test_lerobot_torchcodec_video_decode(tmp_path: Path) -> None:
    """Exercise LeRobot's dataset video decoder on a tiny generated MP4."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("optional LeRobot video smoke requires ffmpeg")
    import numpy as np
    from lerobot.datasets.video_utils import decode_video_frames
    from lerobot.utils.import_utils import get_safe_default_video_backend

    # Assert LeRobot didn't silently fall back to PyAV if TorchCodec failed to
    # import because of an ABI mismatch. The default dataset backend must work.
    assert get_safe_default_video_backend() == "torchcodec"
    frames = np.zeros((2, 32, 32, 3), dtype=np.uint8)
    frames[0, :, :, 0] = 220
    frames[1, :, :, 1] = 190
    video_path = tmp_path / "torchcodec-smoke.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            "32x32",
            "-r",
            "2",
            "-i",
            "pipe:0",
            "-frames:v",
            "2",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            str(video_path),
        ],
        input=frames.tobytes(),
        check=True,
        capture_output=True,
    )
    decoded = decode_video_frames(
        video_path,
        timestamps=[0.1],
        tolerance_s=0.5,
        backend=None,
        return_uint8=True,
    )
    assert decoded.shape == (1, 3, 32, 32)
    assert str(decoded.dtype) == "torch.uint8"


def _test_native_cpu_training_step(tmp_path: Path) -> None:
    """Build a tiny local dataset and run the wrapper's native ACT command once."""
    np = pytest.importorskip("numpy")
    torch = pytest.importorskip("torch")

    from lerobot.configs.train import DatasetConfig, TrainPipelineConfig
    from lerobot.datasets.lerobot_dataset import LeRobotDataset
    from lerobot.policies.act.configuration_act import ACTConfig

    from laundrybench.data.recording import DATASET_IDENTITY_CONTRACT, dataset_content_identity
    from laundrybench.policies.act import SO101_JOINT_NAMES
    from laundrybench.training.act import run_training

    repo_id = "local-user/act-cpu-smoke"
    dataset_root = tmp_path / "synthetic_lerobot_dataset"
    feature_names = [f"{name}.pos" for name in SO101_JOINT_NAMES]
    dataset = LeRobotDataset.create(
        repo_id=repo_id,
        fps=15,
        features={
            "observation.state": {
                "dtype": "float32",
                "shape": (6,),
                "names": feature_names,
            },
            "action": {"dtype": "float32", "shape": (6,), "names": feature_names},
            "observation.images.front": {
                "dtype": "video",
                "shape": (32, 32, 3),
                "names": ["height", "width", "channels"],
            },
        },
        root=dataset_root,
        robot_type="so101",
        use_videos=True,
        video_backend="torchcodec",
        image_writer_processes=0,
        image_writer_threads=0,
    )
    for index in range(3):
        dataset.add_frame(
            {
                "observation.state": np.zeros(6, dtype=np.float32),
                "action": np.zeros(6, dtype=np.float32),
                "observation.images.front": np.full((32, 32, 3), index * 30, dtype=np.uint8),
                "task": "synthetic sock sorting",
            }
        )
    dataset.save_episode(parallel_encoding=False)
    dataset.finalize()

    # Match LaundryBench's layout: the run root exists for its manifest, while
    # the native trainer gets a fresh child directory. Run native validation
    # directly first, then exercise the exact command builder with CLI parsing.
    validation_root = tmp_path / "native-validation-run"
    validation_root.mkdir()
    validation_native = validation_root / "native"
    assert validation_root.is_dir() and not validation_native.exists()
    tiny_policy = ACTConfig(
        device="cpu",
        push_to_hub=False,
        pretrained_backbone_weights=None,
        chunk_size=2,
        n_action_steps=1,
        dim_model=32,
        n_heads=4,
        dim_feedforward=64,
        n_encoder_layers=1,
        n_decoder_layers=1,
        latent_dim=8,
        n_vae_encoder_layers=1,
    )
    native_config = TrainPipelineConfig(
        dataset=DatasetConfig(repo_id=repo_id, root=str(dataset_root), video_backend="torchcodec"),
        policy=tiny_policy,
        output_dir=validation_native,
        job_name="act-cpu-smoke",
        batch_size=1,
        steps=1,
        num_workers=0,
        dataloader_multiprocessing_context=None,
    )
    native_config.validate()
    assert native_config.output_dir == validation_native

    dataset_id = dataset_content_identity(dataset_root)
    info_path = dataset_root / "meta" / "info.json"
    manifest_path = tmp_path / "synthetic-recording.json"
    manifest = {
        "schema_version": 1,
        "status": "completed",
        "return_code": 0,
        "shell": False,
        "command": [
            "--robot.use_degrees=false",
            "--teleop.use_degrees=false",
            "--dataset.fps=15",
        ],
        "supervision": {"operator_confirmed": True},
        "lerobot": {"pinned_version": "0.6.1", "observed_version": "0.6.1"},
        "robot": {"use_degrees": False},
        "teleoperator": {"use_degrees": False},
        "camera": {
            "name": "front",
            "width": 32,
            "height": 32,
            "fps": 15,
            "color_mode": "RGB",
        },
        "dataset": {
            "dataset_id": dataset_id,
            "dataset_id_contract": DATASET_IDENTITY_CONTRACT,
            "repo_id_requested": repo_id,
            "repo_id_effective": repo_id,
            "root": str(dataset_root),
            "fps": 15,
            "meta_info_sha256": _sha256(info_path),
            "act_io_contract": {
                "status": "validated",
                "source": str(info_path),
                "camera_names": ["front"],
                "state": {
                    "names": feature_names,
                    "canonical_joint_names": list(SO101_JOINT_NAMES),
                },
                "action": {
                    "names": feature_names,
                    "canonical_joint_names": list(SO101_JOINT_NAMES),
                },
            },
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    run_root = tmp_path / "wrapper-generated-run"
    training_config = {
        "training": {
            "dataset_id": dataset_id,
            "dataset_repo_id": repo_id,
            "dataset_revision": dataset_id,
            "dataset_root": str(dataset_root),
            "dataset_manifest": str(manifest_path),
            "output_dir": str(run_root),
            "steps": 1,
            "batch_size": 1,
            "seed": 7,
            "device": "cpu",
            "control_hz": 15,
            "mode": "local",
        },
        "task": {"id": "synthetic_smoke", "version": "1"},
        "protocol": {"id": "synthetic_smoke", "version": "1"},
        "contract": {
            "state_names": feature_names,
            "state_units": ["normalized"] * 6,
            "action_names": feature_names,
            "action_units": ["normalized"] * 6,
            "joint_names": list(SO101_JOINT_NAMES),
            "use_degrees": False,
            "normalization": {
                "coordinate_space": "normalized",
                "state_min": [-100, -100, -100, -100, -100, 0],
                "state_max": [100, 100, 100, 100, 100, 100],
                "action_min": [-100, -100, -100, -100, -100, 0],
                "action_max": [100, 100, 100, 100, 100, 100],
            },
            "cameras": {"front": {"width": 32, "height": 32, "color": "RGB", "dtype": "uint8"}},
        },
    }
    config_path = tmp_path / "synthetic-training.yaml"
    config_path.write_text(json.dumps(training_config, indent=2) + "\n", encoding="utf-8")
    selected_python = Path(sys.executable).absolute()
    assert selected_python.is_symlink(), "smoke must exercise a selected venv Python symlink"
    env = os.environ.copy()
    env.update(
        {
            "HF_HUB_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        }
    )
    native_overrides = [
        "--policy.pretrained_backbone_weights=null",
        "--policy.chunk_size=2",
        "--policy.n_action_steps=1",
        "--policy.dim_model=32",
        "--policy.n_heads=4",
        "--policy.dim_feedforward=64",
        "--policy.n_encoder_layers=1",
        "--policy.n_decoder_layers=1",
        "--policy.latent_dim=8",
        "--policy.n_vae_encoder_layers=1",
        "--num_workers=0",
        "--dataloader_multiprocessing_context=null",
        "--log_freq=1",
    ]
    runner_calls: list[list[str]] = []

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        runner_calls.append(list(command))
        assert Path(command[0]) == selected_python
        command = list(command)
        if len(command) > 2 and command[1:3] == ["-m", "lerobot.scripts.lerobot_train"]:
            command.extend(native_overrides)
            return subprocess.run(
                command,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=300,
            )
        return subprocess.run(
            command,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    training_result = run_training(
        config_path,
        execute=True,
        lerobot_python=selected_python,
        runner=runner,
    )
    assert ["-m", "lerobot.scripts.lerobot_train"] in [call[1:3] for call in runner_calls]
    assert training_result["status"] == "completed", training_result
    assert Path(training_result["native_output_dir"]) == run_root / "native"
    assert Path(training_result["command"][0]) == selected_python
    checkpoint = Path(training_result["checkpoint_path"])
    for filename in (
        "config.json",
        "model.safetensors",
        "policy_preprocessor.json",
        "policy_postprocessor.json",
    ):
        assert (checkpoint / filename).is_file(), filename
    assert list(checkpoint.glob("policy_*_step_*.safetensors"))
    assert (run_root / "policy_contract.json").is_file()
    from laundrybench.policies.act import LeRobotACTPolicy

    LeRobotACTPolicy(checkpoint, device="cpu")
    assert not torch.cuda.is_available()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
