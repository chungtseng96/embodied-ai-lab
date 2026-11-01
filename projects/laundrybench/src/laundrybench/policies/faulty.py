from __future__ import annotations

from laundrybench.types import Action, Observation


class FaultyMockPolicy:
    """Mock policy with an injected fault, used only to exercise the evidence pipeline.

    Behaves like ``MockPolicy`` until ``fault_step``, then emits non-finite (NaN)
    joint targets on every later step so the quality gate's ``nan_action`` check
    and the failure taxonomy are exercised end to end. Not a physical result.
    """

    name = "faulty-mock-policy"

    def __init__(self, fault_step: int = 2) -> None:
        self.fault_step = fault_step
        self.reset_calls = 0

    def reset(self) -> None:
        self.reset_calls += 1

    def act(self, observation: Observation) -> Action:
        step = int(observation.metadata.get("step", 0))
        if step >= self.fault_step:
            target = float("nan")
        else:
            target = min(1.0, 0.2 * (step + 1))
        return Action(
            joint_targets=[target] * 6,
            metadata={"source": self.name},
        )
