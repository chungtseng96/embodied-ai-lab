# Agent instructions

## Project purpose

Embodied AI Lab develops robotics systems for manipulation, policy evaluation,
and reproducible experimentation. LaundryBench is the first project, built
around an SO-101 arm. Each project owns its code, dependencies, configuration,
tests, experiments, architecture, and operating documentation.

Treat the repository as an engineering project that happens to use AI agents.
Keep the canonical workflow in versioned Python modules, CLI scripts,
configuration files, tests, logs, and experiment records. A notebook may be
useful for exploration, but no important result should require a notebook to
reproduce it.

## Work tracking

- Issues and priorities live in Linear:
  <https://linear.app/jwang-embodied-ai-lab/team/JWA/active> (team key `JWA`).
  Check it before starting work and reference the issue key in branch names
  and commit messages when one exists.
- Execution detail for the current engineering push lives in
  `projects/laundrybench/docs/plans/2026-10-31-laundrybench-v1-implementation.md`; design findings
  and their status live in `projects/laundrybench/docs/plans/2026-10-31-laundrybench-design-review.md`.
- GitHub remote is the personal account `chungtseng96`, not a work account.
  Git pushes use a repo-local credential helper for that account. The `gh`
  CLI's active login may be a different account, so run `gh` commands for
  this repo as `GH_TOKEN="$(gh auth token --user chungtseng96)" gh ...`.

## Before changing code

- Read the relevant `AGENTS.md` files from the repository root down to the
  files being changed.
- Inspect `git status --short` and preserve existing user changes.
- Read the relevant design or experiment document before changing an
  architecture boundary.
- Prefer a small, testable change over a broad framework addition.

Documentation navigation is in [`docs/README.md`](docs/README.md).
Use the PR template to report evidence and distinguish mock checks from physical validation.
New agents can start with [`docs/agent-guide.md`](docs/agent-guide.md) for task
routing, exact check commands, worktree ownership, and handoff evidence. It
points back to these instructions and the relevant skills; it does not replace
them.

## Repository map

- `projects/laundrybench/`: the installable Python project and its tests.
- `projects/laundrybench/src/laundrybench/`: robot, policy, data,
  evaluation, and observability boundaries.
- `projects/laundrybench/scripts/`: deterministic CLI entry points and
  environment checks.
- `projects/laundrybench/configs/`: checked-in YAML configuration.
- `projects/laundrybench/experiments/`: experiment plans, evidence, and
  failure analysis.
- `projects/laundrybench/docs/`: project architecture, decisions, and playbooks.
- `docs/`: shared engineering guidance and templates.
- `projects/README.md`: project catalog and ownership conventions.
- `skills/`: repository-local agent workflows. Read the relevant
  skill before performing a repeated workflow.

## Required validation

`make check` runs lint, tests, and script smoke checks; CI uses the same command.

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
