# LaundryBench V1 design review (fix-review loop state)

**Date:** 2026-10-31
**Reviewed:** `docs/architecture/*`, `docs/plans/so101-readiness.md`, `ROADMAP.md`,
`projects/laundrybench/` (source, configs, scripts, tests) at commit `48a04d9`.
**Baseline:** `make check PYTHON=.venv/bin/python` passes (5 tests, ruff clean)
with Python 3.11. The default `python3` on this Mac is 3.9 and fails.

**How to use this file:** this is the state file for the fix-review loop. Read
it first every run. Work one finding at a time, update its status with
evidence (test name, commit), then stop after the run budget. Fixes are
specified in
[`2026-10-31-laundrybench-v1-implementation.md`](2026-10-31-laundrybench-v1-implementation.md).

## Verdict

The architecture direction is right: thin adapters over LeRobot, a
model-agnostic `Policy`, experiments as first-class artifacts, CLI over
notebooks. The problems are all at the **contract level**. The interfaces are
too thin to carry a real policy or a real arm, the checked-in configs are not
read by any code, and the evaluation protocol in the docs is not the one the
runner implements. All of these are cheap to fix now with mocks and expensive
to discover with an arm on the table.

## Findings

Severity: **H** = will block or corrupt the first physical experiment,
**M** = causes drift or rework, **L** = friction.

| ID | Sev | Finding | Fix task | Status |
| --- | --- | --- | --- | --- |
| F1 | H | `Robot.task_success()` puts the success oracle on the robot. A physical SO-101 cannot know a sock is in a basket, and `evaluation.yaml` says `require_manual_success_label: true`. The runner's control flow depends on this per step. | Task 1 (JWA-5) | open |
| F2 | H | `Policy` has no `reset()`. ACT (action chunking, temporal ensembling) and SmolVLA keep per-episode state; LeRobot policies expose `reset()`. Without it, episode N+1 starts with episode N's action queue. | Task 2 (JWA-6) | open |
| F3 | H | No safe shutdown path. `Robot` has no `stop()`/`close()`, `run_episode` has no `try/finally`, so a policy exception mid-episode leaves the arm executing its last target and the serial port open. `robot.yaml` declares safety settings that no code reads. | Task 2 (JWA-6) | open |
| F4 | H | Episode loop is step-counted, not time-bounded. `max_steps: 20` versus `timeout_seconds: 30` and `max_episode_seconds: 30`. A 30 Hz policy for 30 s is 900 steps. No `control_hz`, so the mock loop spins unthrottled and the real loop would too. | Task 3 (JWA-7) | open |
| F5 | H | No failure taxonomy. `EpisodeResult.failure_category` is a free string, `summarize()` does not count categories, yet Phase 4 of the roadmap is "choose one dominant failure mode". The improvement loop has no data to run on. | Task 4 (JWA-8) | open |
| F6 | M | Configs are documentation, not inputs. `pyyaml` is a dependency but nothing loads `configs/*.yaml`; `evaluate.py` hardcodes `MockRobot(seed=7)`. No schema, no validation, so a typo in a YAML key is silent. | Task 5 (JWA-9) | open |
| F7 | M | No run manifest. Episode IDs are random UUIDs with no link to experiment, config, git revision, seed, or dataset. The design doc requires all of these for a reproducible run. | Task 6 (JWA-10) | open |
| F8 | M | Observability logs only the final `EpisodeResult`. The V1 diagram promises "video + joint logs + outcome". Without per-step observation/action records, post-hoc failure analysis is impossible. | Task 8 (JWA-12) | open |
| F9 | M | `Observation` cannot carry a camera frame (`image_ref: str`) and `joint_positions: list[float]` has no joint names or units. LeRobot SO-101 can report degrees or a normalized range depending on config; a units mismatch is a silent bug class. | Task 7 (JWA-11) | open |
| F10 | M | Metric names drift between `evaluation.yaml` (`completion_time_seconds`, `human_intervention_rate`, `failure_category_counts`) and `metrics.py` (`median_duration_s`, `interventions` as a count, no category counts). | Task 4 (JWA-8) | open |
| F11 | L | Three overlapping plans with different phase numbering: `ROADMAP.md` (Phases 0-4), `so101-readiness.md` (Phases 0-6), `projects/laundrybench/README.md` "Planned physical integration" (steps 1-7). No single source of truth for "what is next". | Task 9 (JWA-13) | open |
| F12 | L | `make check` fails out of the box because `PYTHON ?= python3` resolves to Python 3.9 here while `pyproject.toml` requires 3.11 and LeRobot needs 3.12. The trap is documented in `labs/05` but not removed. | Task 9 (JWA-13) | open |
| F13 | L | `scripts/record.py`, `train.py`, `run_policy.py` are stubs and there is no Dockerfile, although the design doc centers Docker. Acceptable before hardware, but the plan must state which of these can be built now (Dockerfile, `train.py` CLI wrapper) and which wait for the arm. | Deferred (JWA-14 to JWA-18) | open |

## Reconciliation with the tldraw diagrams

The two diagrams in [`docs/architecture/diagrams/`](../architecture/diagrams/README.md)
are the fuller design. The plan currently covers the runner, judge, step
recorder, manifest, taxonomy, and config loading. Still to reconcile:

| ID | Delta between plan and diagram | Proposed resolution |
| --- | --- | --- |
| D1 | Diagram keeps `success` on the Robot adapter but asks "WHO DECIDES on real arm?" | Keep F1: move it to `SuccessJudge`; update the diagram. |
| D2 | Taxonomy names differ (diagram: `missed_grasp`, `grasp_lost`, `wrong_object`, `dropped`, `timeout`, ...) | Adopt the diagram's names in Task 4. |
| D3 | Artifact layout: diagram uses `outputs/exp-001-baseline/{manifest.yaml, summary.json, episodes.jsonl, quality.json, report.html, media/, traces/}`; plan uses `outputs/<run_id>/manifest.json` | Adopt the diagram's layout in Task 6; key runs by experiment ID. |
| D4 | Quality gate (frozen camera, NaN actions, bad timestamps, missing labels) has no task | Add Phase B task: `quality.py` + `quality.json`. |
| D5 | Report (per-condition, CIs, baseline vs candidate, `report.html`) has no task | Add Phase B task: `summary.json` + static `report.html`. |
| D6 | Vertical slice steps 5 and 6 (compare two mock policies, inject and classify one failure) have no task | Add Phase B tasks. |
| D7 | Operator terminal view during a run and Rerun replay are not in the plan | Terminal view is a small Phase B task; Rerun replay stays deferred to hardware. |

Status: proposed, awaiting confirmation before the plan is edited.

## What is sound and should not change

- LeRobot owns hardware, datasets, and policy mechanics; LaundryBench adapts at
  the boundary (ADR 002, ADR 003).
- `Protocol`-based `Robot` and `Policy` interfaces with mocks in-tree.
- Experiments as directories with a fixed template; EXP-001 protocol is fixed
  before any result exists.
- CLI scripts plus checked-in YAML as the canonical workflow; notebooks are
  non-authoritative.
- Agent contract (`AGENTS.md`, `skills/`) and CI that runs on stock Python
  without LeRobot.

## Loop rules

- One finding per iteration. Evidence before status change: the named test
  passes under `make check PYTHON=.venv/bin/python`.
- Status values: `open`, `in progress`, `fixed (<commit>)`, `deferred (<why>)`,
  `needs human (<question>)`.
- Decisions only a human can make go in **Needs human** below, and the loop
  moves on.
- Stop when every finding is `fixed` or `deferred`, or after 3 findings in one
  run.

## Needs human

- None yet.
