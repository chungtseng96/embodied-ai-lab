import json

from laundrybench.observability.logger import JsonlEpisodeLogger
from laundrybench.types import EpisodeResult, FailureCategory


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
