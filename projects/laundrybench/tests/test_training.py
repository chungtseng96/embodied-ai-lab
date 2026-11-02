from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from laundrybench.data.recording import DATASET_IDENTITY_CONTRACT, dataset_content_identity
from laundrybench.policies.act import ACTContractError, load_act_contract
from laundrybench.training.act import (
    TrainingError,
    _source_identity,
    finalize_checkpoint,
    run_training,
)

PROJECT = Path(__file__).resolve().parents[1]
JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
FEATURE_NAMES = [f"{joint}.pos" for joint in JOINTS]
PREPROCESSOR_STATE = "policy_preprocessor_step_3_normalizer_processor.safetensors"
POSTPROCESSOR_STATE = "policy_postprocessor_step_0_unnormalizer_processor.safetensors"


def _config(tmp_path: Path, *, mode: str = "local") -> Path:
    root = tmp_path / "dataset"
    for directory in ("meta", "data", "videos"):
        (root / directory).mkdir(parents=True)
    metadata = {
        "repo_id": "owner/sock-smoke",
        "fps": 30,
        "features": {
            "observation.state": {"dtype": "float32", "shape": [6], "names": FEATURE_NAMES},
            "action": {"dtype": "float32", "shape": [6], "names": FEATURE_NAMES},
            "observation.images.front": {"dtype": "video", "shape": [480, 640, 3]},
        },
    }
    info_path = root / "meta" / "info.json"
    info_path.write_text(json.dumps(metadata), encoding="utf-8")
    (root / "data" / "frames.parquet").write_bytes(b"fake dataset frames")
    dataset_id = dataset_content_identity(root)
    manifest = {
        "schema_version": 1,
        "status": "completed",
        "return_code": 0,
        "shell": False,
        "command": [
            "--robot.use_degrees=false",
            "--teleop.use_degrees=false",
            "--dataset.fps=30",
        ],
        "supervision": {"operator_confirmed": True},
        "lerobot": {"pinned_version": "0.6.1", "observed_version": "0.6.1"},
        "robot": {"use_degrees": False},
        "teleoperator": {"use_degrees": False},
        "camera": {"name": "front", "width": 640, "height": 480, "fps": 30, "color_mode": "RGB"},
        "dataset": {
            "dataset_id": dataset_id,
            "dataset_id_contract": DATASET_IDENTITY_CONTRACT,
            "repo_id_requested": "owner/sock-smoke",
            "repo_id_effective": "owner/sock-smoke",
            "root": str(root),
            "fps": 30,
            "meta_info_sha256": hashlib.sha256(info_path.read_bytes()).hexdigest(),
            "act_io_contract": {
                "status": "validated",
                "source": str(info_path),
                "camera_names": ["front"],
                "state": {"names": FEATURE_NAMES, "canonical_joint_names": JOINTS},
                "action": {"names": FEATURE_NAMES, "canonical_joint_names": JOINTS},
            },
        },
    }
    manifest_path = tmp_path / "dataset.recording.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    dataset_root = "dataset"
    training = {
        "dataset_id": dataset_id,
        "dataset_repo_id": "owner/sock-smoke",
        "dataset_revision": (
            "0123456789abcdef0123456789abcdef01234567" if mode == "cloud" else dataset_id
        ),
        "dataset_root": dataset_root,
        "dataset_manifest": manifest_path.name,
        "output_dir": "out",
        "steps": 12,
        "batch_size": 2,
        "seed": 3,
        "device": "cuda",
        "control_hz": 30,
        "mode": mode,
    }
    if mode == "cloud":
        training.update(
            allow_private_upload=True,
            cloud={
                "target": "a10g-small",
                "model_repo_id": "owner/private-act",
                "private": True,
            },
        )
    contract = {
        "state_names": FEATURE_NAMES,
        "state_units": ["normalized"] * 6,
        "action_names": FEATURE_NAMES,
        "action_units": ["normalized"] * 6,
        "joint_names": JOINTS,
        "use_degrees": False,
        "normalization": {
            "coordinate_space": "normalized",
            "state_min": [-100, -100, -100, -100, -100, 0],
            "state_max": [100, 100, 100, 100, 100, 100],
            "action_min": [-100, -100, -100, -100, -100, 0],
            "action_max": [100, 100, 100, 100, 100, 100],
        },
        "cameras": {"front": {"width": 640, "height": 480, "color": "RGB", "dtype": "uint8"}},
    }
    document = {
        "training": training,
        "contract": contract,
        "task": {"id": "sock_sorting_v1", "version": "1"},
        "protocol": {"id": "sock_sort_collection", "version": "1"},
    }
    path = tmp_path / "training.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def _runner(
    *,
    checkpoint: bool,
    returncode: int = 0,
    stdout: str = "",
    cloud_snapshot: Path | None = None,
    cloud_private: bool = True,
    model_repo_visibility: str = "new_private",
):
    def invoke(command, **kwargs):
        if "-c" in command:
            if "snapshot_download" in command[2]:
                assert cloud_snapshot is not None
                snapshot = {
                    "path": str(Path(command[-2])),
                    "repo_id": command[-4],
                    "revision": command[-3],
                    "private": cloud_private,
                    "model_repo_id": command[-1],
                    "model_repo_visibility": model_repo_visibility,
                }
                shutil.copytree(cloud_snapshot, Path(command[-2]))
                return subprocess.CompletedProcess(command, 0, json.dumps(snapshot), "")
            return subprocess.CompletedProcess(command, 0, "0.6.1\n", "")
        if checkpoint:
            output = Path(
                next(arg.split("=", 1)[1] for arg in command if arg.startswith("--output_dir="))
            )
            pretrained = output / "checkpoints" / "000012" / "pretrained_model"
            pretrained.mkdir(parents=True)
            (pretrained / "config.json").write_text('{"type":"act"}', encoding="utf-8")
            (pretrained / "model.safetensors").write_bytes(b"fake-weights")
            (
                pretrained / "policy_preprocessor_step_3_normalizer_processor.safetensors"
            ).write_bytes(b"state-mean-std")
            (
                pretrained / "policy_postprocessor_step_0_unnormalizer_processor.safetensors"
            ).write_bytes(b"state-unnormalizer")
            (pretrained / "policy_preprocessor.json").write_text(
                json.dumps(
                    {
                        "steps": [
                            {
                                "registry_name": "normalizer_processor",
                                "state_file": PREPROCESSOR_STATE,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (pretrained / "policy_postprocessor.json").write_text(
                json.dumps(
                    {
                        "steps": [
                            {
                                "registry_name": "unnormalizer_processor",
                                "state_file": POSTPROCESSOR_STATE,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(command, returncode, stdout, "fake stderr")

    return invoke


def _cloud_runner(config: Path, **kwargs):
    document = yaml.safe_load(config.read_text(encoding="utf-8"))
    root = Path(document["training"]["dataset_root"])
    snapshot = root if root.is_absolute() else config.parent / root
    kwargs.setdefault("cloud_snapshot", snapshot)
    return _runner(**kwargs)


def test_help_works_without_dataset_or_lerobot() -> None:
    result = subprocess.run(
        [sys.executable, str(PROJECT / "scripts" / "train.py"), "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--execute" in result.stdout


def test_source_identity_accepts_explicit_container_build_sha_without_git(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_sha = "abcdef0123456789abcdef0123456789abcdef01"
    monkeypatch.setenv("LAUNDRYBENCH_SOURCE_SHA", build_sha)
    monkeypatch.setattr(
        "laundrybench.training.act.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 128, "", "not a checkout"),
    )
    source_sha, source_tree_sha, source_origin = _source_identity()
    assert source_sha == build_sha
    assert len(source_tree_sha) == 64
    assert source_origin == "build_argument_operator_asserted"


def test_dry_run_builds_native_act_command_without_creating_output(tmp_path: Path) -> None:
    path = _config(tmp_path)
    result = run_training(path)
    assert result["status"] == "planned"
    assert "--policy.type=act" in result["command"]
    assert not any(arg.startswith("--dataset.revision=") for arg in result["command"])
    assert "--policy.push_to_hub=false" in result["command"]
    assert not Path(result["output_dir"]).exists()
    assert result["command"][
        next(
            index
            for index, item in enumerate(result["command"])
            if item.startswith("--output_dir=")
        )
    ].endswith("/out/native")


def test_training_preserves_selected_venv_python_symlink(tmp_path: Path) -> None:
    path = _config(tmp_path)
    python_link = tmp_path / "venv" / "bin" / "python"
    python_link.parent.mkdir(parents=True)
    python_link.symlink_to(sys.executable)
    result = run_training(path, lerobot_python=python_link)
    assert result["command"][0] == str(python_link.absolute())


def test_identical_dataset_copy_is_portable_but_mutated_copy_is_rejected(tmp_path: Path) -> None:
    path = _config(tmp_path)
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    source = path.parent / document["training"]["dataset_root"]
    copied = tmp_path / "copied-dataset"
    shutil.copytree(source, copied)
    document["training"]["dataset_root"] = str(copied)
    document["training"]["output_dir"] = str(tmp_path / "copy-out")
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    assert run_training(path)["status"] == "planned"

    with (copied / "data" / "frames.parquet").open("ab") as data_file:
        data_file.write(b"changed")
    with pytest.raises(TrainingError, match="content does not match"):
        run_training(path)


def test_local_run_requires_native_checkpoint_and_writes_rollout_contract(tmp_path: Path) -> None:
    path = _config(tmp_path)
    result = run_training(
        path, execute=True, lerobot_python=Path(sys.executable), runner=_runner(checkpoint=True)
    )
    assert result["status"] == "completed"
    checkpoint = Path(result["checkpoint_path"])
    contract_path = checkpoint / "policy_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    weight_sha = hashlib.sha256((checkpoint / "model.safetensors").read_bytes()).hexdigest()
    assert contract["checkpoint"]["sha256"] == weight_sha
    assert set(contract["checkpoint"]["processor_sha256"]) == {
        "policy_preprocessor.json",
        "policy_postprocessor.json",
    }
    assert set(contract["checkpoint"]["processor_state_sha256"]) == {
        PREPROCESSOR_STATE,
        POSTPROCESSOR_STATE,
    }
    assert contract["joint_names"] == JOINTS
    assert contract["dataset"]["fps"] == 30
    assert contract["normalization"]["coordinate_space"] == "normalized"
    assert Path(result["native_output_dir"]).is_dir()
    assert not (Path(result["native_output_dir"]) / "preexisting-marker").exists()
    assert load_act_contract(contract_path, checkpoint) == contract
    state_file = checkpoint / PREPROCESSOR_STATE
    state_file.write_bytes(b"tampered-normalizer")
    with pytest.raises(ACTContractError, match="state|processor"):
        load_act_contract(contract_path, checkpoint)
    assert Path(result["output_dir"] + "/policy_contract.json").is_file()


def test_success_exit_without_complete_native_artifacts_is_failed(tmp_path: Path) -> None:
    result = run_training(
        _config(tmp_path),
        execute=True,
        lerobot_python=Path(sys.executable),
        runner=_runner(checkpoint=False),
    )
    assert result["status"] == "failed"
    assert "no completed checkpoint" in result["error"]


def test_cloud_requires_private_config_and_records_submission_not_completion(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, mode="cloud")
    result = run_training(
        config,
        execute=True,
        lerobot_python=Path(sys.executable),
        runner=_cloud_runner(config, checkpoint=False, stdout="Job ID: 123456\n"),
    )
    assert result["status"] == "submitted"
    assert result["job_id"] == "123456"
    assert "checkpoint_path" not in result
    assert "--job.target=a10g-small" in result["command"]
    assert "--policy.private=true" in result["command"]
    assert "--policy.push_to_hub=true" in result["command"]
    assert "--policy.push_to_hub=false" not in result["command"]
    assert "--dataset.revision=0123456789abcdef0123456789abcdef01234567" in result["command"]
    assert not (Path(result["output_dir"]) / "policy_contract.json").exists()
    assert result["remote_dataset"]["verification"] == (
        "selected_lerobot_python_snapshot_and_content_hash"
    )
    assert result["remote_dataset"]["revision"] == ("0123456789abcdef0123456789abcdef01234567")
    assert result["remote_dataset"]["model_repo_visibility"] == "new_private"


def test_cloud_rejects_unprivate_repo_or_wrong_remote_content_before_job_submission(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, mode="cloud")
    remote_copy = tmp_path / "remote-copy"
    shutil.copytree(tmp_path / "dataset", remote_copy)
    with (remote_copy / "data" / "frames.parquet").open("ab") as data_file:
        data_file.write(b"changed remotely")
    with pytest.raises(TrainingError, match="does not match the validated local recording"):
        run_training(
            config,
            execute=True,
            lerobot_python=Path(sys.executable),
            runner=_cloud_runner(config, checkpoint=False, cloud_snapshot=remote_copy),
        )
    assert not (tmp_path / "out").exists()

    with pytest.raises(TrainingError, match="private status did not match"):
        run_training(
            config,
            execute=True,
            lerobot_python=Path(sys.executable),
            runner=_cloud_runner(config, checkpoint=False, model_repo_visibility="existing_public"),
        )


def test_cloud_checkpoint_can_be_finalized_after_native_completion_is_confirmed(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, mode="cloud")
    submission = run_training(
        config,
        execute=True,
        lerobot_python=Path(sys.executable),
        runner=_cloud_runner(config, checkpoint=False, stdout="Job ID: 123456\n"),
    )
    checkpoint = tmp_path / "downloaded" / "checkpoints" / "000012" / "pretrained_model"
    checkpoint.mkdir(parents=True)
    (checkpoint / "config.json").write_text('{"type":"act"}', encoding="utf-8")
    (checkpoint / "model.safetensors").write_bytes(b"downloaded weights")
    pre_state = "policy_preprocessor_step_3_normalizer_processor.safetensors"
    post_state = "policy_postprocessor_step_0_unnormalizer_processor.safetensors"
    (checkpoint / pre_state).write_bytes(b"normalizer state")
    (checkpoint / post_state).write_bytes(b"unnormalizer state")
    (checkpoint / "policy_preprocessor.json").write_text(
        json.dumps({"steps": [{"registry_name": "normalizer_processor", "state_file": pre_state}]}),
        encoding="utf-8",
    )
    (checkpoint / "policy_postprocessor.json").write_text(
        json.dumps(
            {"steps": [{"registry_name": "unnormalizer_processor", "state_file": post_state}]}
        ),
        encoding="utf-8",
    )

    finalized = finalize_checkpoint(
        config,
        checkpoint,
        confirm_remote_complete=True,
        remote_model_revision="0123456789abcdef0123456789abcdef01234567",
    )
    assert finalized["status"] == "contract_finalized"
    assert finalized["job_id"] == submission["job_id"]
    contract = json.loads((checkpoint / "policy_contract.json").read_text(encoding="utf-8"))
    record = json.loads((checkpoint / "laundrybench_finalize.json").read_text(encoding="utf-8"))
    assert contract["checkpoint"]["path"] == "."
    assert (
        contract["checkpoint"]["config_sha256"]
        == hashlib.sha256((checkpoint / "config.json").read_bytes()).hexdigest()
    )
    assert record["model_repo_revision_asserted"] == "0123456789abcdef0123456789abcdef01234567"
    assert record["download_revision_verification"] == "operator_asserted_not_queried"
    assert load_act_contract(checkpoint / "policy_contract.json", checkpoint) == contract
    training_record = json.loads(
        (Path(submission["output_dir"]) / "laundrybench_training.json").read_text(encoding="utf-8")
    )
    assert training_record["status"] == "submitted"


def test_checkpoint_finalizer_requires_explicit_remote_completion(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, mode="cloud")
    with pytest.raises(TrainingError, match="confirm the HF Job is complete"):
        finalize_checkpoint(
            config,
            tmp_path / "missing",
            confirm_remote_complete=False,
            remote_model_revision="0123456789abcdef0123456789abcdef01234567",
        )


def test_cloud_interrupt_records_detached_with_unknown_remote_status(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, mode="cloud")
    cloud_snapshot = config.parent / "dataset"

    def interrupt(command, **kwargs):
        if "-c" in command:
            if "snapshot_download" in command[2]:
                snapshot = {
                    "path": str(Path(command[-2])),
                    "repo_id": command[-4],
                    "revision": command[-3],
                    "private": True,
                    "model_repo_id": command[-1],
                    "model_repo_visibility": "new_private",
                }
                shutil.copytree(cloud_snapshot, Path(command[-2]))
                return subprocess.CompletedProcess(command, 0, json.dumps(snapshot), "")
            return subprocess.CompletedProcess(command, 0, "0.6.1\n", "")
        raise KeyboardInterrupt

    result = run_training(
        config,
        execute=True,
        lerobot_python=Path(sys.executable),
        runner=interrupt,
    )
    assert result["status"] == "detached"
    assert result["remote_status"] == "unknown"
    assert "may still be running" in result["note"]
    saved = json.loads(
        (Path(result["output_dir"]) / "laundrybench_training.json").read_text(encoding="utf-8")
    )
    assert saved["status"] == "detached"


def test_rejects_dataset_contract_mismatch_and_existing_output(tmp_path: Path) -> None:
    path = _config(tmp_path)
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    document["contract"]["cameras"]["side"] = document["contract"]["cameras"].pop("front")
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(TrainingError, match="match the training contract"):
        run_training(path)

    path = _config(tmp_path / "second")
    output = tmp_path / "second" / "out"
    output.mkdir()
    with pytest.raises(TrainingError, match="refusing to overwrite"):
        run_training(path)


def test_rejects_wrong_lerobot_version_before_making_output(tmp_path: Path) -> None:
    def wrong_version(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, "0.7.0\n", "")

    config = _config(tmp_path)
    with pytest.raises(TrainingError, match="0.6.1 is required"):
        run_training(
            config, execute=True, lerobot_python=Path(sys.executable), runner=wrong_version
        )
    assert not (tmp_path / "out").exists()
