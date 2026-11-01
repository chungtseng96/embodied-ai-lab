from __future__ import annotations

import random
from typing import Protocol

from laundrybench.types import FailureCategory, Observation


class SuccessJudge(Protocol):
    """Decides whether a task attempt has succeeded.

    The robot adapter is a pure I/O boundary; it cannot observe task outcome.
    Success is judged separately from the post-action observation (ADR 004).
    """

    failure_category: FailureCategory
    """Label recorded when an episode times out and is not a success."""

    def is_success(self, observation: Observation) -> bool:
        """Called after every step; True ends the episode as a success."""
        ...

    def on_timeout(self, observation: Observation) -> bool:
        """Final verdict when the step budget or time runs out."""
        ...


class MockSuccessJudge:
    """Seeded stand-in judge for the mock loop. Not a physical outcome.

    ``failure_category`` is the label the runner records when an episode times out.
    """

    def __init__(
        self,
        seed: int = 0,
        success_after_steps: int = 4,
        success_probability: float = 0.8,
        failure_category: FailureCategory = FailureCategory.MISSED_GRASP,
    ) -> None:
        self.failure_category = failure_category
        self._rng = random.Random(seed)
        self._success_after_steps = success_after_steps
        self._success_probability = success_probability

    def is_success(self, observation: Observation) -> bool:
        if observation.metadata["step"] < self._success_after_steps:
            return False
        return self._rng.random() < self._success_probability

    def on_timeout(self, observation: Observation) -> bool:
        return False
