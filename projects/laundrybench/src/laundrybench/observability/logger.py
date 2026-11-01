from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path

from laundrybench.types import Action, EpisodeResult, Observation


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


class JsonlStepLogger:
    """Append-only per-step trace: one JSON line per observation/action pair.

    Camera frames are never serialized; only the sorted camera slot names are.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, episode_id: str, step: int, observation: Observation, action: Action) -> None:
        payload = {
            "episode_id": episode_id,
            "step": step,
            "timestamp_s": observation.timestamp_s,
            "joint_positions": list(observation.joint_positions),
            "joint_names": list(observation.joint_names),
            "joint_units": observation.joint_units,
            "image_keys": sorted(observation.images),
            "joint_targets": list(action.joint_targets),
            "action_metadata": action.metadata,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")
