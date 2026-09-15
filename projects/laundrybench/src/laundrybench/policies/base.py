from __future__ import annotations

from typing import Protocol

from laundrybench.types import Action, Observation


class Policy(Protocol):
    """Model-agnostic boundary for robot policies."""

    name: str

    def act(self, observation: Observation) -> Action:
        ...
