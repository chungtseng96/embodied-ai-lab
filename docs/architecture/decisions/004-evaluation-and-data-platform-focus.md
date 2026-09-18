# ADR 004 — Go Deep on Evaluation and Failure-Driven Data Improvement

## Status

Accepted

## Context

LaundryBench needs one complete physical robot-learning loop before the project
can support deeper experimentation. The project also needs a clear area of
ownership that demonstrates software-engineering judgment rather than only
integrating an existing policy.

The main candidates were:

- implement or improve the policy itself
- build a large simulation or synthetic-data system
- build the evaluation, observability, and data-iteration platform around a
  real task

## Decision

LaundryBench will first establish a thin end-to-end vertical slice, then go
deep on a **policy-agnostic evaluation and failure-driven data platform**.

The platform will make it possible to:

```text
evaluate
   ↓
diagnose failure
   ↓
collect targeted data
   ↓
train or adapt a policy
   ↓
re-evaluate under the same conditions
```

LaundryBench will own:

- task and condition definitions
- experiment manifests and run lineage
- step-level episode traces and artifact references
- evaluation protocols and metrics
- human failure labels and failure taxonomy
- dataset and sensor-quality gates
- comparison reports and policy-promotion evidence
- targeted-data iteration workflow

LaundryBench will reuse:

- LeRobot hardware and dataset tooling
- existing policy implementations, starting with ACT
- existing training and inference workflows where practical
- simulation environments as supporting backends when useful

## Deliberate non-goals

- Do not implement a new policy architecture as the primary project.
- Do not build a general-purpose robotics cloud or microservice platform yet.
- Do not make a large synthetic dataset or simulator the first deep track.
- Do not claim that mock or simulation results represent physical robot
  performance.

## Consequences

### Positive

- The project remains grounded in a real physical task.
- Evaluation work feeds directly into training-data decisions.
- The platform can compare ACT, SmolVLA, scripted policies, and future policies
  without rewriting the experiment loop.
- The project demonstrates API design, data modeling, reproducibility,
  observability, testing, and failure analysis.
- Simulation can accelerate development without becoming a separate product.

### Costs

- The first useful result may be an imperfect policy rather than a novel model.
- Human labeling and evaluation protocol design require discipline.
- A good platform needs richer traces and metadata than the current final-result
  JSONL logger provides.

## Revisit this decision when

Reconsider a deeper simulation or policy-research track only after:

1. a physical baseline has been evaluated with a fixed protocol;
2. at least one failure-driven iteration has been completed; and
3. the current evaluation and artifact model can represent the new experiment.

## Related documents

- [LaundryBench Evaluation Platform Architecture](../evaluation-platform.md)
- [V1 Architecture](../v1-architecture.md)
- [ADR 002 — Use LeRobot as the Robotics Foundation](002-why-lerobot.md)
- [ADR 003 — Keep the Policy Boundary Model-Agnostic](003-policy-abstraction.md)
