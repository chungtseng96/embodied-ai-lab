# V1 Architecture

See the [evaluation-platform direction](evaluation-platform.md) for the broader roadmap and
[as-built diagram](diagrams/laundrybench-v1-as-built.svg) for the implemented mock V1.

The first system is intentionally small: one repository, one physical task, clear software boundaries.

```text
Camera + robot state
        ↓
     Policy
        ↓
   Robot action
        ↓
    SO-101
        ↓
video + joint logs + outcome
        ↓
   Evaluation
        ↓
 failure analysis
        ↓
 data/model/config change
```

## V1 principles

- Keep the physical task narrow
- Keep the software model-agnostic
- Reuse LeRobot for hardware integration and policy execution
- Own the experiment workflow, evaluation, observability, and failure analysis
- Avoid unnecessary services until the project needs them

## Detailed diagrams

Component and run-workflow diagrams live in [`diagrams/`](diagrams/README.md).
