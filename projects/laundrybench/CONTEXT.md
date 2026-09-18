# CONTEXT — LaundryBench domain model

**Date:** 2026-09-18
**Status:** Living document
**Owner:** Chung-Tseng Wang

Human-maintained glossary, invariants, and open questions for `projects/laundrybench/`. Hold
these before changing anything here. Update it when a decision changes; link, don't duplicate.

## Glossary

- **Episode** — one complete attempt at the task, from `robot.reset()` to success or
  `max_steps`. Produces exactly one `EpisodeResult`.
- **Step** — one observe → act → apply cycle inside an episode.
- **Observation** — what the policy sees at one step: `timestamp_s`, `joint_positions`,
  optional `image_ref`, free-form `metadata`.
- **Action** — the policy's output for the robot: `joint_targets` plus `metadata`. Joint space,
  not Cartesian, in V1.
- **Policy** — anything with a `name` and `act(observation) -> Action`. Model-agnostic on purpose
  (ADR 003). ACT, Diffusion Policy, SmolVLA are all policies behind this boundary.
- **Robot** — anything satisfying `reset / observe / apply / task_success`. `MockRobot` now,
  SO-101 via LeRobot later (ADR 001, ADR 002).
- **Intervention** — a human touched the robot or scene during an episode. Recorded on
  `EpisodeResult.intervention`. An intervened episode is not a success.
- **Failure category** — a short string on failed episodes. Only
  `timeout_or_task_failure` exists today; real categories come from EXP-001 evidence, not in
  advance (EXP-002 guardrail).
- **Success definition** — from `configs/task.yaml`: sock ends inside the sock basket and no
  intervention occurred. Manual label required (`require_manual_success_label: true`).
- **Baseline vs candidate** — EXP-001 establishes the baseline; every later experiment changes
  one primary variable and compares against it using the same evaluation protocol.
- **Mock** — a stand-in that exercises the software boundary. Has no physical meaning.

## Invariants (violate = the portfolio claim is false)

1. **Mock results are never presented as robot results.** In docs, experiments, PR text, or
   summaries. `MockRobot.task_success()` is `random() < 0.8`.
2. **The policy boundary stays model-agnostic.** Vendor code lives in adapters only.
3. **Experiments are first-class and honest.** Every experiment records question, hypothesis,
   baseline, one change, protocol, results, failure breakdown, and next step. Negative results
   are written up the same as positive ones.
4. **Same protocol for baseline and candidate.** Changing the evaluation protocol is itself an
   experiment, not a tweak.
5. **Safety first on hardware.** `configs/robot.yaml` says `require_manual_supervision: true`
   and `max_episode_seconds: 30`. No autonomous motion without a human at the e-stop.

## Decisions (index, details in `docs/architecture/decisions/`)

| ADR | Decision |
|-----|----------|
| 001 | SO-101 leader/follower as the V1 arm |
| 002 | Reuse LeRobot for hardware and policy plumbing |
| 003 | Keep the `Policy` boundary model-agnostic |

## Known gaps / parked (do not guess)

- **Hardware has not arrived.** SO-101 and the USB camera are ordered. Labs 01–04 and the
  `record` / `train` / `run_policy` scripts are stubs until bring-up.
- **No LeRobot adapter exists.** `Robot` for SO-101 is unwritten. Its port names, calibration
  flow, and observation shape are unknown until the hardware is on the desk.
- **`configs/*.yaml` are not loaded by code.** They record intent. A loader is deliberately
  absent until a script needs one.
- **Failure categories are undefined.** Only the placeholder `timeout_or_task_failure` exists.
  Do not invent a taxonomy; EXP-001 evidence defines it.
- **`data/` is empty.** Dataset format (LeRobot dataset vs custom) is undecided.
- **Camera observation is a string ref.** `Observation.image_ref` is `str | None`; whether V1
  passes frames in-memory or by path is undecided.
- **No report generation yet.** `make demo` prints a JSON summary; the roadmap's "simple local
  report generation" is unstarted.
