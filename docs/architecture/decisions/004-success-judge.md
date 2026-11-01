# ADR 004 — Judge task success outside the robot

## Decision
Task success is decided by a `SuccessJudge` (`is_success` after every step, `on_timeout` when the budget runs out), not by the `Robot`. The `Robot` protocol exposes only `reset`, `observe`, and `apply`.

## Why
A real arm cannot observe whether a laundry task succeeded; `evaluation.yaml` requires a manual success label from the operator. Keeping the verdict off the robot keeps the robot adapter a pure I/O boundary and lets the mock judge, a manual judge, and a future vision-based judge share one interface.

```text
Robot.observe() -> Policy -> Robot.apply()
        |
        v
  SuccessJudge.is_success(observation) -> end episode or continue
  SuccessJudge.on_timeout(observation) -> final verdict
```

## Tradeoff
One more object to wire into every run. A manual judge blocks on the operator, which is intended: an unlabeled episode must not be recorded as a success.
