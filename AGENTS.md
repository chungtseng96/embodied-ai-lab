# AGENTS.md

Read this first. It is a router: enough to orient in 60 seconds, then links out.
`CLAUDE.md` is a symlink to this file. Keep this file under ~80 lines.

## What this repo is

A solo learning notebook plus a working embodied-AI lab. The flagship project is
**LaundryBench**: teach an SO-101 arm to sort laundry, and build the data → train → deploy →
evaluate → diagnose loop around it. Hardware has not arrived yet; the software loop runs on mocks.

## Layout

```text
docs/           fundamentals, cheatsheets, architecture + ADRs, journal, templates, plans
                See docs/README.md for "which doc do I read for X".
labs/           small concept -> code -> hardware exercises (blocked on hardware)
notes/          paper notes and learning plans
projects/laundrybench/   the only code. See projects/laundrybench/AGENTS.md before editing it.
resources/      papers, repos, videos, companies
```

## Commands (run from repo root)

```bash
make install    # pip install -e ".[dev]" inside projects/laundrybench
make check      # lint + test, exactly what CI runs. Prints GATE PASS / GATE FAIL.
make lint       # ruff only
make test       # pytest only
make demo       # 10 mock episodes -> projects/laundrybench/outputs/mock-episodes.jsonl
```

`PYTHON` defaults to `python3` and is resolved after `cd projects/laundrybench`. If the system
Python lacks ruff/pytest, create `projects/laundrybench/.venv` and point
at it: `PYTHON=.venv/bin/python make check`.

## Tests

`projects/laundrybench/tests/test_*.py`, pytest, no fixtures or plugins. Tests use `MockRobot`
and `MockPolicy` only. There is no hardware test path yet.

## Conventions

- Commit subjects: `<area>: <imperative summary>` under 72 chars. Areas in use:
  `docs`, `labs`, `experiments`, `config`, `test`, `chore`, `ci`, `feat`, `fix`.
- New docs start with a status header: `**Date:** / **Status:** / **Owner:**`.
- Experiments live in `projects/laundrybench/experiments/exp-NNN-slug/README.md` and follow
  `docs/templates/experiment.md`. Every experiment states `Hardware: mock | physical`.
- Scratch files go in `.claude/scratch/` (gitignored). Never commit `outputs/`.

## Key gotchas

- **Mock results are not robot results.** `MockRobot.task_success()` is a coin flip. Never
  report a mock success rate as a finding, in docs, experiments, or PR text.
- **Labs and the `record` / `train` / `run_policy` scripts are intentional stubs.** They raise
  `SystemExit` on purpose. Do not "implement" them before SO-101 bring-up.
- **The policy boundary is model-agnostic by decision** (ADR 003). ACT / SmolVLA / LeRobot
  specifics belong in adapters, never in `evaluation/`, `observability/`, or `types.py`.
- **`configs/*.yaml` are not loaded by any code yet.** They document intent; do not assume a
  loader exists.
- **ADRs are immutable.** To change a decision, add a new ADR that amends the old one.

## Further reading

- `START-HERE.md` — recommended reading order for a human
- `ROADMAP.md` — phases and what is done
- `projects/laundrybench/AGENTS.md` — code-level guide, Don'ts, troubleshooting
- `projects/laundrybench/CONTEXT.md` — glossary, invariants, parked questions
- `docs/plans/2026-09-18-adopt-agent-patterns.md` — where these conventions came from
