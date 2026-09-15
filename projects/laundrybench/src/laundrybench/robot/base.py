from __future__ import annotations

from typing import Protocol

from laundrybench.types import Action, Observation


class Robot(Protocol):
    """Minimal robot boundary used by the evaluation loop."""

    def reset(self) -> None:
        ...

    def observe(self) -> Observation:
        ...

    def apply(self, action: Action) -> None:
        ...

    def task_success(self) -> bool:
        ...
