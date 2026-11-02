# LaundryBench milestones

## Implemented software

- Model-agnostic robot and policy interfaces with deterministic mock backends.
- Evaluation runner, structured traces, failure taxonomy, metrics, and reports.
- Results application with persistent human-review labels and contextual comparisons.
- SO-101 adapter with offline contract coverage.
- Demonstration recording, dataset-bound ACT training, and bounded supervised rollout.
- Camera evidence capture and checkpoint provenance validation.
- Python, frontend, and browser acceptance workflows in CI.

Offline checks establish software behavior. Hardware acceptance and task performance
require operator-run evidence.

## Next gate: physical baseline

- Verify ports, calibration, joint state, camera freshness, and stop/reconnect behavior.
- Record a demonstration dataset with a fixed scene and task protocol.
- Train an ACT baseline and preserve dataset/checkpoint identity.
- Run supervised evaluations on held-out placements.
- Review every episode and publish results with failure categories and limitations.

Use the [operator playbook](docs/playbooks/so101-home-feedback-loop.md) and record
results in [the physical feedback-loop experiment](experiments/exp-003-physical-feedback-loop/README.md).

## Next gate: measured improvement

- Select a dominant failure mode from reviewed physical episodes.
- Add targeted demonstrations or change one configuration variable.
- Evaluate the candidate under the same protocol as the baseline.
- Preserve both runs and report improvements, regressions, and uncertainty.

## Later candidates

Additional policy adapters, clothing categories, clutter conditions, cameras,
simulation, and bimanual manipulation are candidates after the baseline and first
measured improvement. They are not current capability claims.

Detailed engineering history: [implementation plan](docs/plans/2026-10-31-laundrybench-v1-implementation.md)
and [design review](docs/plans/2026-10-31-laundrybench-design-review.md).
