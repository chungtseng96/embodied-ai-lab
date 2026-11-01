# LaundryBench agent instructions

This directory is the installable Python project. Keep its public boundaries
small and explicit:

- `src/laundrybench/robot/` owns the robot interface and adapters.
- `src/laundrybench/policies/` owns policy interfaces and adapters.
- `src/laundrybench/data/` owns episode and dataset-facing helpers.
- `src/laundrybench/evaluation/` owns closed-loop runs and metrics.
- `src/laundrybench/observability/` owns structured logs and evidence.
- `scripts/` owns human- and agent-invocable commands.
- `configs/` owns declarative experiment inputs.
- `tests/` verifies behavior at the project boundary.

Use the repository root instructions for the validation commands. A change in
this project should remain runnable with the mock robot unless it explicitly
introduces a physical LeRobot adapter.

Do not import LeRobot into the core package just to make a placeholder work.
Keep the dependency optional until a real adapter has a tested contract.
