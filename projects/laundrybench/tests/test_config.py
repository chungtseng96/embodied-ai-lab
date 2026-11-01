import pytest
from conftest import REPO_CONFIGS, copy_configs

from laundrybench.config import ConfigError, load_config


def test_load_repo_configs() -> None:
    cfg = load_config(REPO_CONFIGS)
    assert cfg.task.name == "sock_sorting_v1"
    assert cfg.evaluation.control_hz == 30
    assert cfg.robot.max_episode_seconds == 30


def test_unknown_key_raises(tmp_path) -> None:
    copy_configs(REPO_CONFIGS, tmp_path)
    (tmp_path / "task.yaml").write_text("task:\n  name: x\n  bogus: 1\n")
    with pytest.raises(ConfigError, match="unknown key 'bogus'"):
        load_config(tmp_path)


def test_missing_file_raises(tmp_path) -> None:
    copy_configs(REPO_CONFIGS, tmp_path)
    (tmp_path / "camera.yaml").unlink()
    with pytest.raises(ConfigError, match="missing config file"):
        load_config(tmp_path)
