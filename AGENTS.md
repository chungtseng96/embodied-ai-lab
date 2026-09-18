# AGENTS.md

Read this first. It is a router: enough to orient in 60 seconds, then links out.
`CLAUDE.md` is a symlink to this file. Keep this file under ~100 lines.

## What this repo is

A solo learning record plus a working embodied-AI lab. The flagship project is **LaundryBench**:
teach an SO-101 arm to sort laundry, and build the data → train → deploy → evaluate → diagnose
loop around it. Hardware has not arrived yet; the software loop runs on mocks. Treat it as an
engineering project that happens to use AI agents: the canonical workflow lives in versioned
Python, CLI scripts, configs, tests, logs, and experiment records. No result may depend on a
notebook to reproduce.

## Layout

```text
docs/           fundamentals, cheatsheets, architecture + ADRs, journal, templates, plans
                See docs/README.md for "which doc do I read for X".
labs/           small concept -> code -> hardware exercises (blocked on hardware)
notes/          paper notes and learning plans
projects/laundrybench/   the only code. Read projects/laundrybench/AGENTS.md before editing it.
skills/         repo-local agent workflows (also reachable as .claude/skills/)
resources/      papers, repos, videos, companies
```

## Before changing code

- Read the `AGENTS.md` files from the root down to the files you are changing.
- Run `git status --short` and preserve existing user changes.
- Read the relevant design, ADR, or experiment doc before touching an architecture boundary.
- Prefer a small, testable change over a framework addition.

## Commands (run from repo root)

```bash
make install        # pip install -e ".[dev]" inside projects/laundrybench
make check          # lint + test + script smoke. Exactly what CI runs. Prints GATE PASS / GATE FAIL.
make lint | test | smoke | demo
make host-check     # report laptop prerequisites (Docker, uv, ffmpeg, hf, LeRobot CLI). Never fails.
make lerobot-check PYTHON=.venv-lerobot/bin/python   # only for LeRobot env changes; needs Python 3.12 + lerobot
```

`PYTHON` defaults to `python3` and matches CI (stock 3.11, no LeRobot). A `PYTHON` with a slash
is resolved to an absolute path, so `PYTHON=projects/laundrybench/.venv/bin/python make check`
works from the root when the system Python lacks ruff/pytest.

## Tests

`projects/laundrybench/tests/test_*.py`, pytest, no fixtures or plugins. Tests use `MockRobot`
and `MockPolicy` only. There is no hardware test path yet.

## Conventions

- Commit subjects: `<area>: <imperative summary>` under 72 chars. Areas in use:
  `docs`, `labs`, `experiments`, `config`, `test`, `chore`, `ci`, `feat`, `fix`.
- New docs start with `**Date:** / **Status:** / **Owner:**`.
- Experiments live in `projects/laundrybench/experiments/exp-NNN-slug/README.md`, follow
  `docs/templates/experiment.md`, and state `**Hardware:** mock | physical`.
- Add or update a test when behavior changes. Do not add tests that mirror implementation.
- Never commit credentials, calibration files, datasets, checkpoints, or videos.
- Scratch files go in `.claude/scratch/` (gitignored). Never commit `outputs/`.

## Key gotchas

- **Mock results are not robot results.** `MockRobot.task_success()` is a coin flip. Never
  report a mock success rate as a finding, in docs, experiments, or PR text.
- **Hardware commands can move a real arm.** Default to `--help`, port detection, config review,
  and dry runs. Before any movement, calibration, recording, or rollout command, confirm the
  exact hardware target and operation in the current task and keep an operator at the e-stop.
  Follow `skills/so101-bringup/SKILL.md`.
- **`record` / `train` / `run_policy` scripts are intentional stubs.** They raise `SystemExit`.
  Do not "implement" them before SO-101 bring-up.
- **LeRobot owns low-level robot, camera, dataset, and policy mechanics.** LaundryBench adds
  adapters at the boundary (ADR 002, ADR 003). Do not copy LeRobot internals or import LeRobot
  into the core package to make a placeholder work.
- **`configs/*.yaml` are not loaded by any code yet.** They document intent.
- **ADRs are immutable.** To change a decision, add a new ADR that amends the old one.

## Further reading

- `START-HERE.md` and `ROADMAP.md` — reading order and phases
- `projects/laundrybench/AGENTS.md` — code-level guide, Don'ts, troubleshooting, pinned versions
- `projects/laundrybench/CONTEXT.md` — glossary, invariants, parked questions
- `docs/plans/so101-readiness.md` and `docs/architecture/robot-learning-development-environment.md`
  — read before adding hardware or training code
- `skills/laundrybench-engineering/SKILL.md` — workflow for code, config, tests, experiments
- `docs/plans/2026-09-18-adopt-agent-patterns.md` — where these conventions came from
