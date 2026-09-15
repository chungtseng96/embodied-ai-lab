from __future__ import annotations

from laundrybench.types import Action, Observation


class MockPolicy:
    """Simple policy used only to exercise the software loop."""

    name = "mock-policy"

    def act(self, observation: Observation) -> Action:
        step = int(observation.metadata.get("step", 0))
        target = min(1.0, 0.2 * (step + 1))
        return Action(
            joint_targets=[target] * 6,
            metadata={"source": self.name},
        )
