from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

import pytest

from laundrybench.data.recording import (
    RecordingConfigError,
    canonicalize_so101_joint_names,
    dataset_content_identity,
    load_recording_config,
    validate_calibration_files,
)

ROOT = Path(__file__).parents[1]
SCRIPT_PATH = ROOT / "scripts" / "record.py"
SPEC = importlib.util.spec_from_file_location("record_cli", SCRIPT_PATH)
assert SPEC and SPEC.loader
record_cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(record_cli)


def _config_file(
    tmp_path: Path, *, bad_port: bool = False, camera_fps: int = 15, dataset_fps: int = 15
) -> Path:
    lerobot_home = tmp_path / "lerobot-home"
    follower_cal = lerobot_home / "calibration/robots/so_follower/follower-id.json"
    leader_cal = lerobot_home / "calibration/teleoperators/so_leader/leader-id.json"
    follower_cal.parent.mkdir(parents=True, exist_ok=True)
    leader_cal.parent.mkdir(parents=True, exist_ok=True)
    follower_cal.write_text('{"joints": {"shoulder": {}}}', encoding="utf-8")
    leader_cal.write_text('{"joints": {"shoulder": {}}}', encoding="utf-8")
    source = f"""recording:
  follower_port: /dev/ttyACM0
  follower_id: follower-id
  follower_calibration_file: {follower_cal}
  leader_port: {"/dev/ttyACM0" if bad_port else "/dev/ttyACM1"}
  leader_id: leader-id
  leader_calibration_file: {leader_cal}
  camera:
    name: front
    index_or_path: 0
    width: 640
    height: 480
    fps: {camera_fps}
  dataset:
    repo_id: lab/sock-smoke
    fps: {dataset_fps}
    root: {tmp_path / "dataset"}
    manifest_path: {tmp_path / "recording.json"}
  episodes: 2
  episode_time_s: 30
  reset_time_s: 30
  task: Pick up the sock and place it in the basket.
  lerobot:
    python: {sys.executable}
    home: {lerobot_home}
    version: 0.6.1
"""
    path = tmp_path / "recording.yaml"
    path.write_text(source, encoding="utf-8")
    return path


def _info(root: Path) -> None:
    metadata = root / "meta"
    metadata.mkdir(parents=True)
    (metadata / "info.json").write_text(
        json.dumps(
            {
                "fps": 15,
                "robot_type": "so101_follower",
                "codebase_version": "v2.1",
                "features": {
                    "observation.state": {
                        "dtype": "float32",
                        "shape": [6],
                        "names": [
                            "shoulder_pan.pos",
                            "shoulder_lift.pos",
                            "elbow_flex.pos",
                            "wrist_flex.pos",
                            "wrist_roll.pos",
                            "gripper.pos",
                        ],
                        "units": ["normalized"] * 6,
                    },
                    "action": {
                        "dtype": "float32",
                        "shape": [6],
                        "names": [
                            "shoulder_pan.pos",
                            "shoulder_lift.pos",
                            "elbow_flex.pos",
                            "wrist_flex.pos",
                            "wrist_roll.pos",
                            "gripper.pos",
                        ],
                        "units": ["normalized"] * 6,
                    },
                    "observation.images.front": {
                        "dtype": "video",
                        "shape": [480, 640, 3],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    data = root / "data"
    videos = root / "videos"
    data.mkdir()
    videos.mkdir()
    (data / "chunk-000.parquet").write_bytes(b"fixture parquet bytes")
    (videos / "observation.images.front" / "chunk-000.mp4").parent.mkdir(parents=True)
    (videos / "observation.images.front" / "chunk-000.mp4").write_bytes(b"fixture video bytes")


def test_dataset_identity_survives_copy_and_changes_when_content_changes(tmp_path: Path) -> None:
    source = tmp_path / "source-root"
    _info(source)
    copy = tmp_path / "copy-root"
    shutil.copytree(source, copy)
    source_identity = dataset_content_identity(source)
    assert source_identity.startswith("local-sha256:")
    assert dataset_content_identity(copy) == source_identity
    (copy / "data" / "chunk-000.parquet").write_bytes(b"mutated bytes")
    assert dataset_content_identity(copy) != source_identity


def test_config_requires_distinct_ports_and_ids(tmp_path: Path) -> None:
    with pytest.raises(RecordingConfigError, match="port and leader_port must be distinct"):
        load_recording_config(_config_file(tmp_path, bad_port=True))


def test_camera_acquisition_rate_must_meet_dataset_recording_rate(tmp_path: Path) -> None:
    with pytest.raises(RecordingConfigError, match="camera.fps must be at least dataset.fps"):
        load_recording_config(_config_file(tmp_path, camera_fps=15, dataset_fps=30))


def test_joint_names_accept_only_exact_so101_aliases() -> None:
    native_names = [
        "shoulder_pan.pos",
        "shoulder_lift.pos",
        "elbow_flex.pos",
        "wrist_flex.pos",
        "wrist_roll.pos",
        "gripper.pos",
    ]
    assert canonicalize_so101_joint_names(native_names, "action") == [
        "shoulder_pan",
        "shoulder_lift",
        "elbow_flex",
        "wrist_flex",
        "wrist_roll",
        "gripper",
    ]
    with pytest.raises(RecordingConfigError, match="unknown SO-101 joint name"):
        canonicalize_so101_joint_names([*native_names[:-1], "wrist_yaw.pos"], "action")
    with pytest.raises(RecordingConfigError, match="duplicate or incomplete"):
        canonicalize_so101_joint_names([*native_names[:-1], "wrist_roll"], "action")


def test_config_rejects_unknown_keys_and_example_is_concrete(tmp_path: Path) -> None:
    config_path = _config_file(tmp_path)
    config_path.write_text(config_path.read_text() + "  surprise: true\n", encoding="utf-8")
    with pytest.raises(RecordingConfigError, match="unknown key 'surprise'"):
        load_recording_config(config_path)


def test_checked_in_example_config_parses() -> None:
    config = load_recording_config(ROOT / "configs" / "recording.example.yaml")
    assert config.lerobot_version == "0.6.1"
    assert config.camera_name == "front"
    assert config.dataset_fps == 15


@pytest.mark.skipif(
    os.name != "posix", reason="virtualenv executable symlink regression is POSIX-specific"
)
def test_lerobot_python_venv_symlink_is_preserved_and_used_by_command(tmp_path: Path) -> None:
    environment = tmp_path / "lerobot-env"
    venv.EnvBuilder(with_pip=False, symlinks=True).create(environment)
    python_path = environment / "bin" / "python"
    assert python_path.is_symlink()

    config_path = _config_file(tmp_path)
    config_text = config_path.read_text(encoding="utf-8")
    config_path.write_text(
        config_text.replace(f"python: {sys.executable}", f"python: {python_path}"),
        encoding="utf-8",
    )
    config = load_recording_config(config_path)
    assert config.lerobot_python == python_path.absolute()
    assert config.lerobot_python.is_symlink()

    probe = subprocess.run(
        [str(config.lerobot_python), "-c", "import sys; print(sys.prefix)"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert Path(probe.stdout.strip()) == environment
    assert record_cli.build_command(config)[0] == str(python_path.absolute())


def test_command_is_explicit_shell_free_argv_with_upload_disabled(tmp_path: Path) -> None:
    config = load_recording_config(_config_file(tmp_path))
    argv = record_cli.build_command(config)
    assert argv[:3] == [str(config.lerobot_python), "-m", "lerobot.scripts.lerobot_record"]
    assert "--robot.port=/dev/ttyACM0" in argv
    assert "--teleop.port=/dev/ttyACM1" in argv
    assert "--robot.use_degrees=false" in argv
    assert "--teleop.use_degrees=false" in argv
    assert "--robot.id=follower-id" in argv
    assert "--teleop.id=leader-id" in argv
    assert any(item.startswith('--robot.cameras={"front":') for item in argv)
    camera_arg = next(item for item in argv if item.startswith("--robot.cameras="))
    assert '"color_mode":"rgb"' in camera_arg
    assert f"--dataset.root={config.dataset_root}" in argv
    assert "--dataset.push_to_hub=false" in argv
    assert "--dataset.fps=15" in argv
    assert "--resume=false" in argv
    assert "--dataset.fps=15" in argv
    assert all(isinstance(item, str) for item in argv)


def test_calibration_paths_must_match_ids_and_be_readable(tmp_path: Path) -> None:
    config = load_recording_config(_config_file(tmp_path))
    validate_calibration_files(config)
    config.follower_calibration_file.write_text("{}", encoding="utf-8")
    with pytest.raises(RecordingConfigError, match="nonempty JSON object"):
        validate_calibration_files(config)


def test_script_help_does_not_require_lerobot() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--execute" in result.stdout and "--supervised" in result.stdout


def test_dry_run_writes_planned_manifest_without_version_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = _config_file(tmp_path)
    monkeypatch.chdir(ROOT)
    assert record_cli.main(["--config", str(config_path)]) == 0
    output = json.loads(capsys.readouterr().out)
    manifest_path = Path(output["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert output["mode"] == "dry-run"
    assert manifest["status"] == "planned"
    assert manifest["dataset"]["upload_enabled"] is False
    assert manifest["lerobot"]["observed_version"] is None


def test_execute_uses_verified_environment_and_records_fixture_metadata(tmp_path: Path) -> None:
    config = load_recording_config(_config_file(tmp_path))
    command = record_cli.build_command(config)
    manifest = record_cli.make_manifest(config, command)

    class FakeProcess:
        pid = 123

        def __init__(self) -> None:
            _info(config.dataset_root)

        def wait(self, timeout: float | None = None) -> int:
            return 0

        def poll(self) -> int:
            return 0

    calls = []

    def fake_popen(args: list[str], **kwargs: object) -> FakeProcess:
        calls.append((args, kwargs))
        return FakeProcess()

    result = record_cli.execute_recording(
        config,
        command,
        manifest,
        version_probe=lambda _: ("0.6.1", True),
        popen_factory=fake_popen,
    )
    saved = json.loads(config.manifest_path.read_text(encoding="utf-8"))
    assert result == 0
    assert saved["status"] == "completed"
    assert saved["robot"]["id"] == "follower-id"
    assert saved["teleoperator"]["id"] == "leader-id"
    assert saved["dataset"]["root"] == str(config.dataset_root)
    assert saved["dataset"]["dataset_id"] == dataset_content_identity(config.dataset_root)
    assert saved["dataset"]["act_io_contract"]["state"]["units"] == ["normalized"] * 6
    assert saved["dataset"]["act_io_contract"]["state"]["names"] == [
        "shoulder_pan.pos",
        "shoulder_lift.pos",
        "elbow_flex.pos",
        "wrist_flex.pos",
        "wrist_roll.pos",
        "gripper.pos",
    ]
    assert saved["dataset"]["act_io_contract"]["state"]["canonical_joint_names"] == [
        "shoulder_pan",
        "shoulder_lift",
        "elbow_flex",
        "wrist_flex",
        "wrist_roll",
        "gripper",
    ]
    assert saved["dataset"]["act_io_contract"]["camera_names"] == ["front"]
    assert len(saved["dataset"]["meta_info_sha256"]) == 64
    assert saved["robot"]["use_degrees"] is False
    assert saved["teleoperator"]["use_degrees"] is False
    assert saved["camera"]["color_mode"] == "RGB"
    assert calls[0][0] == command
    assert calls[0][1]["shell"] is False


def test_execute_refuses_wrong_lerobot_version_before_launch(tmp_path: Path) -> None:
    config = load_recording_config(_config_file(tmp_path))
    manifest = record_cli.make_manifest(config, record_cli.build_command(config))

    def must_not_launch(*args: object, **kwargs: object) -> None:
        raise AssertionError("recorder launched despite version mismatch")

    result = record_cli.execute_recording(
        config,
        record_cli.build_command(config),
        manifest,
        version_probe=lambda _: ("0.7.0", True),
        popen_factory=must_not_launch,
    )
    saved = json.loads(config.manifest_path.read_text(encoding="utf-8"))
    assert result == 1
    assert saved["status"] == "failed"
    assert "does not match pinned 0.6.1" in saved["error"]


def test_nonzero_exit_is_failed_and_not_a_physical_success(tmp_path: Path) -> None:
    config = load_recording_config(_config_file(tmp_path))
    manifest = record_cli.make_manifest(config, record_cli.build_command(config))

    class FakeProcess:
        def wait(self, timeout: float | None = None) -> int:
            return 17

    result = record_cli.execute_recording(
        config,
        record_cli.build_command(config),
        manifest,
        version_probe=lambda _: ("0.6.1", True),
        popen_factory=lambda *args, **kwargs: FakeProcess(),
    )
    saved = json.loads(config.manifest_path.read_text(encoding="utf-8"))
    assert result == 17
    assert saved["status"] == "failed"
    assert saved["return_code"] == 17


def test_completed_run_hashes_info_even_when_info_json_is_invalid(tmp_path: Path) -> None:
    config = load_recording_config(_config_file(tmp_path))
    manifest = record_cli.make_manifest(config, record_cli.build_command(config))

    class FakeProcess:
        def wait(self, timeout: float | None = None) -> int:
            _info(config.dataset_root)
            (config.dataset_root / "meta" / "info.json").write_bytes(b"not-json")
            return 0

    result = record_cli.execute_recording(
        config,
        record_cli.build_command(config),
        manifest,
        version_probe=lambda _: ("0.6.1", True),
        popen_factory=lambda *args, **kwargs: FakeProcess(),
    )
    saved = json.loads(config.manifest_path.read_text(encoding="utf-8"))
    assert result == 0
    assert saved["status"] == "completed"
    assert saved["dataset"]["dataset_id"] == dataset_content_identity(config.dataset_root)
    assert saved["dataset"]["meta_info_sha256"] is not None
    assert saved["dataset"]["act_io_contract"] is None
    assert "invalid" in saved["dataset"]["metadata_validation_error"]
