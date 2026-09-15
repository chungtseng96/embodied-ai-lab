import json

from laundrybench.observability.logger import JsonlEpisodeLogger
from laundrybench.types import EpisodeResult


def test_jsonl_logger_writes_episode(tmp_path) -> None:
    path = tmp_path / "episodes.jsonl"
    logger = JsonlEpisodeLogger(path)
    logger.log(EpisodeResult("episode-1", True, 1.25))

    payload = json.loads(path.read_text(encoding="utf-8").strip())
    assert payload["episode_id"] == "episode-1"
    assert payload["success"] is True
