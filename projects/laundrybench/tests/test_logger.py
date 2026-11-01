import json

from laundrybench.observability.logger import JsonlEpisodeLogger, JsonlStepLogger
from laundrybench.types import Action, EpisodeResult, FailureCategory, Observation


def test_jsonl_logger_writes_episode(tmp_path) -> None:
    path = tmp_path / "episodes.jsonl"
    logger = JsonlEpisodeLogger(path)
    logger.log(EpisodeResult("episode-1", True, 1.25))

    payload = json.loads(path.read_text(encoding="utf-8").strip())
    assert payload["episode_id"] == "episode-1"
    assert payload["success"] is True


def test_jsonl_logger_serializes_failure_category_as_string(tmp_path) -> None:
    logger = JsonlEpisodeLogger(tmp_path / "e.jsonl")
    logger.log(EpisodeResult("x", False, 1.0, failure_category=FailureCategory.TIMEOUT))
    payload = json.loads((tmp_path / "e.jsonl").read_text().strip())
    assert payload["failure_category"] == "timeout"


def test_step_logger_writes_one_line_per_step_without_frames(tmp_path) -> None:
    logger = JsonlStepLogger(tmp_path / "steps.jsonl")
    obs = Observation(1.0, [0.0] * 6, images={"front": object()})
    logger.log("ep", 0, obs, Action(joint_targets=[0.1] * 6))
    payload = json.loads((tmp_path / "steps.jsonl").read_text().strip())
    assert payload["image_keys"] == ["front"]
    assert "images" not in payload
    assert payload["joint_targets"] == [0.1] * 6
