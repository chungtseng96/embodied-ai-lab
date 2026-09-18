# Agent instructions

## Project purpose

Embodied AI Lab is a portfolio repository for building and evaluating a small
robot-learning system around an SO-101 arm. LaundryBench is the flagship
project. The repository should show engineering judgment across hardware
integration, data collection, policy execution, evaluation, observability,
and reproducible experiments.

Treat the repository as an engineering project that happens to use AI agents.
Keep the canonical workflow in versioned Python modules, CLI scripts,
configuration files, tests, logs, and experiment records. A notebook may be
useful for exploration, but no important result should require a notebook to
reproduce it.

## Before changing code

- Read the relevant `AGENTS.md` files from the repository root down to the
  files being changed.
- Inspect `git status --short` and preserve existing user changes.
- Read the relevant design or experiment document before changing an
  architecture boundary.
- Prefer a small, testable change over a broad framework addition.

## Repository map

- `projects/laundrybench/`: the installable Python project and its tests.
- `projects/laundrybench/src/laundrybench/`: robot, policy, data,
  evaluation, and observability boundaries.
- `projects/laundrybench/scripts/`: deterministic CLI entry points and
  environment checks.
- `projects/laundrybench/configs/`: checked-in YAML configuration.
- `projects/laundrybench/experiments/`: experiment plans, evidence, and
  failure analysis.
- `labs/`: small learning exercises that may precede production-facing
  adapters.
- `docs/architecture/`: system design and architectural decisions.
- `docs/plans/`: readiness and execution plans.
- `skills/`: repository-local agent workflows. Read the relevant
  skill before performing a repeated workflow.

## Required validation

For Python changes in LaundryBench, run with the default Python (this matches
CI, which uses stock Python 3.11 without LeRobot):

```bash
make check
```

For LeRobot environment changes, also run the check through the LeRobot
virtual environment, which is the only command that needs it:

```bash
make lerobot-check PYTHON=.venv-lerobot/bin/python
```

Use `make host-check PYTHON=.venv-lerobot/bin/python` to report laptop
prerequisites. That command reports optional gaps; it does not install tools or
claim that a physical robot is ready.

## Engineering rules

- Keep LeRobot responsible for low-level robot, camera, dataset, and policy
  mechanics. Add LaundryBench adapters at the project boundary instead of
  copying LeRobot internals.
- Keep hardware, cloud training, and local development concerns explicit in
  configuration and documentation.
- Record meaningful model, data, hardware, and configuration changes in an
  experiment document.
- Never describe mock results as physical robot results.
- Do not commit credentials, tokens, calibration secrets, datasets, model
  checkpoints, or generated videos.
- Prefer deterministic commands with explicit inputs and output directories.
- Add or update a test when behavior changes. Do not add tests that merely
  mirror implementation details.

## Hardware boundary

Hardware commands can move a real arm. Default to inspection, `--help`, port
detection, configuration review, and dry-run behavior. Before running a
movement, calibration, recording, or rollout command, confirm the exact
hardware target and the requested operation in the current task. Keep an
operator present and use the LeRobot safety guidance.

## Agent workflow

For a normal change:

1. State the intended behavior and the files that implement it.
2. Make the smallest coherent patch.
3. Run the narrowest meaningful checks, then broaden only if failures or risk
   justify it.
4. Report changed files, validation, and any environment limitation.

For hardware bring-up, use `skills/so101-bringup/SKILL.md`. For code,
configuration, tests, or experiment artifacts, use
`skills/laundrybench-engineering/SKILL.md`.
