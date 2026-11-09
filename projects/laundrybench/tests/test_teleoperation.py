from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from laundrybench.data.recording import RecordingConfigError
from laundrybench.data.teleoperation import (
    load_teleoperation_config,
    validate_teleoperation_calibration_files,
)

ROOT = Path(__file__).parents[1]
SCRIPT_PATH = ROOT / "scripts" / "teleoperate.py"
SPEC = importlib.util.spec_from_file_location("teleoperate_cli", SCRIPT_PATH)
assert SPEC and SPEC.loader
teleoperate_cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(teleoperate_cli)


def _config_file(tmp_path: Path, *, rotation: int = 180, camera_fps: int = 30) -> Path:
    lerobot_home = tmp_path / "lerobot-home"
    follower_cal = lerobot_home / "calibration/robots/so_follower/follower-id.json"
    leader_cal = lerobot_home / "calibration/teleoperators/so_leader/leader-id.json"
    follower_cal.parent.mkdir(parents=True, exist_ok=True)
    leader_cal.parent.mkdir(parents=True, exist_ok=True)
    follower_cal.write_text('{"joints": {"shoulder": {}}}', encoding="utf-8")
    leader_cal.write_text('{"joints": {"shoulder": {}}}', encoding="utf-8")
    source = f"""teleoperation:
  follower_port: /dev/ttyACM0
  follower_id: follower-id
  follower_calibration_file: {follower_cal}
  leader_port: /dev/ttyACM1
  leader_id: leader-id
  leader_calibration_file: {leader_cal}
  cameras:
    front:
      index_or_path: 1
      width: 640
      height: 480
      fps: {camera_fps}
      rotation: 0
    third_person:
      index_or_path: 0
      width: 640
      height: 480
      fps: {camera_fps}
      rotation: {rotation}
  fps: 15
  duration_s: 60
  display_data: true
  display_mode: rerun
  lerobot:
    python: {sys.executable}
    home: {lerobot_home}
    version: 0.6.1
"""
    path = tmp_path / "teleoperation.yaml"
    path.write_text(source, encoding="utf-8")
    return path


def test_checked_in_example_config_parses_with_software_rotation() -> None:
    config = load_teleoperation_config(ROOT / "configs" / "teleoperation.example.yaml")
    assert config.control_fps == 15
    assert config.cameras["front"].rotation == 0
    assert config.cameras["third_person"].rotation == 180


def test_camera_rotation_is_restricted_to_opencv_quarter_turns(tmp_path: Path) -> None:
    with pytest.raises(RecordingConfigError, match="must be one of: 0, 90, 180, 270"):
        load_teleoperation_config(_config_file(tmp_path, rotation=45))


def test_camera_acquisition_rate_must_meet_control_rate(tmp_path: Path) -> None:
    with pytest.raises(RecordingConfigError, match="fps must be at least"):
        load_teleoperation_config(_config_file(tmp_path, camera_fps=10))


def test_command_is_explicit_and_contains_rotated_third_person_camera(tmp_path: Path) -> None:
    config = load_teleoperation_config(_config_file(tmp_path))
    argv = teleoperate_cli.build_command(config)
    assert argv[:3] == [str(config.lerobot_python), "-m", "lerobot.scripts.lerobot_teleoperate"]
    assert "--robot.port=/dev/ttyACM0" in argv
    assert "--teleop.port=/dev/ttyACM1" in argv
    assert "--display_data=true" in argv
    assert "--display_mode=rerun" in argv
    assert "--teleop_time_s=60" in argv
    camera_arg = next(item for item in argv if item.startswith("--robot.cameras="))
    cameras = json.loads(camera_arg.split("=", 1)[1])
    assert cameras["front"]["rotation"] == 0
    assert cameras["third_person"]["rotation"] == 180
    assert cameras["third_person"]["index_or_path"] == 0
    assert all(isinstance(item, str) for item in argv)


def test_calibration_paths_must_match_ids_and_be_readable(tmp_path: Path) -> None:
    config = load_teleoperation_config(_config_file(tmp_path))
    validate_teleoperation_calibration_files(config)
    config.leader_calibration_file.write_text("{}", encoding="utf-8")
    with pytest.raises(RecordingConfigError, match="nonempty JSON object"):
        validate_teleoperation_calibration_files(config)


def test_execute_verifies_environment_and_starts_shell_free_process(tmp_path: Path) -> None:
    config = load_teleoperation_config(_config_file(tmp_path))
    command = teleoperate_cli.build_command(config)
    calls: list[tuple[list[str], dict[str, object]]] = []

    class FakeProcess:
        def wait(self) -> int:
            return 0

    def fake_popen(args: list[str], **kwargs: object) -> FakeProcess:
        calls.append((args, kwargs))
        return FakeProcess()

    assert (
        teleoperate_cli.execute_teleoperation(
            config,
            command,
            version_probe=lambda _: ("0.6.1", True),
            popen_factory=fake_popen,
        )
        == 0
    )
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == command
    assert kwargs["shell"] is False
    assert kwargs["start_new_session"] is True
    environment = kwargs["env"]
    assert isinstance(environment, dict)
    assert environment["HF_LEROBOT_HOME"] == str(config.lerobot_home)
    assert str(config.lerobot_python.parent) in environment["PATH"]


def test_script_help_does_not_require_lerobot() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--execute" in result.stdout and "--supervised" in result.stdout
