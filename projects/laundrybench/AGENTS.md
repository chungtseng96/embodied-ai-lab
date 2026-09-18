# LaundryBench — agent guide

Deep guide for the only code in this repo. Root `AGENTS.md` covers commands and conventions;
this file covers the code. `CONTEXT.md` next to it covers vocabulary and invariants.

## Shape of the code

```text
src/laundrybench/
├── types.py              Observation, Action, EpisodeResult (dataclasses, slots=True)
├── robot/base.py         Robot Protocol: reset / observe / apply / task_success
├── robot/mock.py         MockRobot: 6 joints, succeeds after N steps with p=0.8
├── policies/base.py      Policy Protocol: name + act(observation) -> Action
├── policies/mock.py      MockPolicy: ramps all joints toward 1.0
├── evaluation/runner.py  run_episode(robot, policy, max_steps) -> EpisodeResult
├── evaluation/metrics.py summarize(results) -> dict
├── observability/logger.py  JsonlEpisodeLogger: append-only JSONL
└── data/                 empty package, reserved for dataset helpers
scripts/evaluate.py       the only working entrypoint (mock loop)
scripts/{record,train,run_policy}.py   stubs that raise SystemExit
configs/*.yaml            intent only, nothing reads them yet
tests/test_{runner,metrics,logger}.py
experiments/exp-NNN-slug/README.md
```

**Tiebreaker:** if any doc disagrees with `robot/base.py` or `policies/base.py`, the code wins.
`robot/mock.py` and `policies/mock.py` are the reference implementations of those Protocols.

## Pinned versions

Source of truth is `pyproject.toml` and `.github/workflows/ci.yml`. Update this table in the same
change when a pin moves; the "key constraint" column is what an agent must not get wrong.

| Dependency | Version | Key constraint |
|------------|---------|----------------|
| Python | >= 3.11 (CI runs 3.11) | `dataclass(slots=True)` and `X \| None` syntax are used; do not target older Pythons |
| pyyaml | >= 6.0 | only runtime dependency; nothing loads the YAML yet |
| pytest | >= 8.0 | plain pytest, no plugins or fixtures |
| ruff | >= 0.6 | line length 100; the only linter and formatter |
| LeRobot / torch | not yet a dependency | add as an optional extra with an exact pin and a row here before importing it |

## Adding a real Robot or Policy

1. New module under `robot/` or `policies/` that satisfies the Protocol in `base.py`.
   Protocols are structural; do not subclass, just match the methods.
2. Keep vendor imports (LeRobot, torch, serial) inside that module. Nothing else may import them.
3. Translate vendor-specific state into `Observation` / `Action` at the boundary. If a field does
   not fit, use `metadata`, then decide in an ADR whether it should become a first-class field.
4. Add a test that runs `run_episode` against it with `MockPolicy` or `MockRobot` on the other
   side, so the boundary is exercised in isolation.
5. Update `CONTEXT.md` (glossary / parked) and this file if the contract or layout changed.

## Don'ts

Things that look reasonable here but are wrong.

- **Don't make `run_episode` know about a specific robot or policy.** It takes Protocols.
- **Don't add hardware or ML dependencies to `pyproject.toml` `dependencies`.** Only `pyyaml` is
  there today. Vendor deps go in an optional extra when they arrive.
- **Don't write a config loader "while you're in there."** `configs/*.yaml` are unloaded on
  purpose until a script needs one. See ADR 003 and the roadmap.
- **Don't flesh out the stub scripts.** `record.py`, `train.py`, `run_policy.py` raise on purpose.
- **Don't treat `MockRobot` success as signal.** `task_success()` is `random() < 0.8` after N
  steps. Tests may assert on structure and failure paths, never on success rate.
- **Don't fill in experiment Results before the physical run.** EXP-001 and EXP-002 are
  `Status: Planned` and say so explicitly.
- **Don't add a `Hardware` field to `EpisodeResult` silently.** Use `metadata` until an ADR
  promotes it.

## Verifying a change

```bash
make check                          # from repo root; lint + test, same as CI
cd projects/laundrybench && .venv/bin/python -m pytest tests/test_runner.py -q   # one file
```

Evidence for a PR is the `GATE PASS` line plus the pytest summary (`N passed`). If you added a
failure path, say which test failed first before the fix.

## When something goes wrong

- **`No module named ruff` / `pytest`** — system `python3` is not the project venv. Run
  `PYTHON=.venv/bin/python make check`, or `make install` into a venv.
- **`ModuleNotFoundError: laundrybench`** — package not installed in editable mode. `make install`.
- **`run_episode` returns `failure_category="timeout_or_task_failure"` every time** — with
  `MockRobot`, `success_after_steps` is >= `max_steps`. That is the intended failure path.
- **Test asserting `success is True` is flaky** — expected; success is random. Assert on
  structure or use `success_after_steps=1` with a seed and accept it can still fail. Better: do
  not assert success with the mock at all.
- **Stub script exits with a message** — that is the stub working. Nothing is broken.

## Maintenance

If you change the Protocols in `base.py`, `types.py`, the package layout, or the scripts'
behavior, update the tree above, `CONTEXT.md`, and `README.md` in the same change.
