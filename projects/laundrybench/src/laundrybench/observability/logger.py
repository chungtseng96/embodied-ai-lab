from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path

from laundrybench.types import EpisodeResult


class JsonlEpisodeLogger:
    """Append-only local episode log for early experiments."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, result: EpisodeResult) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            payload = json.dumps(
                asdict(result),
                sort_keys=True,
                default=lambda o: o.value if isinstance(o, Enum) else str(o),
            )
            handle.write(payload + "\n")
