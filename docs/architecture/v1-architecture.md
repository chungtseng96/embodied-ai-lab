# V1 Architecture

The detailed design for the evaluation layer lives in
[LaundryBench Evaluation Platform Architecture](evaluation-platform.md).

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
 targeted data/model/config change
```

## V1 principles

- Keep the physical task narrow
- Keep the software model-agnostic
- Reuse LeRobot for hardware integration and policy execution
- Go deep on evaluation, observability, data quality, and failure-driven
  iteration
- Use one working policy as the integration baseline rather than making policy
  research the primary project
- Treat simulation as a supporting backend until a specific sim-to-real
  question justifies deeper investment
- Avoid unnecessary services until the project needs them
