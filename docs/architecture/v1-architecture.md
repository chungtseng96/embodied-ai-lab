# V1 Architecture

**Date:** 2026-09-15
**Status:** Living document
**Owner:** James Wang

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
