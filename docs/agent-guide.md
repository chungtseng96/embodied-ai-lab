# LaundryBench agent start map

**Date:** 2026-11-01
**Status:** Living document

Start with the root [`AGENTS.md`](../AGENTS.md), then
[`projects/laundrybench/AGENTS.md`](../projects/laundrybench/AGENTS.md) for
project changes. For implementation work, read
[`skills/laundrybench-engineering/SKILL.md`](../skills/laundrybench-engineering/SKILL.md).
For the established ticket workflow and reviewer brief, see
[`skills/factory/README.md`](../skills/factory/README.md). Hardware work must
also follow [`skills/so101-bringup/SKILL.md`](../skills/so101-bringup/SKILL.md)
and the physical safety guidance. These files are the rules; this page is a
map to code, tests, and evidence.

## Route by change

| Change | Implementation route | Test route |
| --- | --- | --- |
| Mock robot or core contracts | `projects/laundrybench/src/laundrybench/{robot,policies,evaluation,observability}/`; config in `configs/` | Matching `projects/laundrybench/tests/test_*.py`; mock evaluation entrypoint `scripts/evaluate.py` |
| Recording | `scripts/record.py`, `src/laundrybench/data/recording.py`, `configs/recording.example.yaml` | `tests/test_recording.py`; physical workflow in `docs/architecture/recording-workflow.md` |
| ACT training | `scripts/train.py`, `src/laundrybench/training/act.py`, `configs/training.example.yaml` | `tests/test_training.py`; `docs/architecture/training-workflow.md` |
| ACT policy and rollout | `scripts/run_policy.py`, `src/laundrybench/policies/act.py`, `src/laundrybench/evaluation/physical.py`, `configs/rollout.example.yaml` | `tests/test_act_policy.py`, `tests/test_physical_rollout.py`; `docs/architecture/act-rollout.md` |
| Capture and evidence | `src/laundrybench/evaluation/capture.py`, `src/laundrybench/evaluation/media.py`, `scripts/import_media.py` | `tests/test_capture.py`, `tests/test_media.py`; `docs/architecture/physical-evidence.md` |
| Results UI and API | `frontend/src/` for browser behavior; `src/laundrybench/web/` for API/server; `scripts/serve.py` and `scripts/report.py` | `frontend/src/*.test.tsx` / `api.test.ts`; backend `tests/test_web*.py`, `tests/test_report.py`; `docs/architecture/results-application.md` |

Check the relevant existing test and architecture doc before changing a
boundary. Keep the mock path runnable. Synthetic tests and fixtures do not
establish camera, robot, GPU, or task-performance behavior.

## Checks from the repository root

```bash
python3 -m venv .venv  # fresh worktree; use its own environment
make install
make check
make frontend-install  # once, or after frontend dependency changes
make frontend-check
```

`make check` is the stock Python project check used by CI: pytest, Ruff, and
script smoke checks. `make frontend-check` runs frontend tests and build.
Keep the editable install inside this worktree's environment so a check cannot
silently import LaundryBench from another checkout.
CI also runs `make web-demo`; it is defined in
[CI workflow](../.github/workflows/ci.yml).

Before a live session, select the actual LeRobot environment:

```bash
make host-check PYTHON=.venv-lerobot/bin/python
make lerobot-check PYTHON=.venv-lerobot/bin/python
```

The second command reports JSON and exits nonzero for required environment
failures, including broken ACT/video imports. It makes no device connections
and does not establish calibration, camera timing, or arm readiness. Then
follow the [home playbook](playbooks/so101-home-feedback-loop.md).

The optional actual LeRobot CPU integration smoke is separate from stock CI.
Use a dedicated environment with LeRobot `0.6.1`, CPU PyTorch `2.7.1`,
torchvision `0.22.1`, TorchCodec `0.5.0`, and FFmpeg. The pinned versions and
installation/check command are recorded in
[`.github/workflows/lerobot-compat.yml`](../.github/workflows/lerobot-compat.yml).
With that environment selected as `.venv-lerobot`, run from the repo root:

```bash
PYTHONPATH="$PWD/projects/laundrybench/src" .venv-lerobot/bin/python -m pytest projects/laundrybench/tests/optional/test_lerobot_act_smoke.py -q
```

This smoke builds a generated checkpoint and runs one CPU ACT training step
with synthetic data. It checks the real installed LeRobot software path; it
does not use a physical arm, camera, recorded demonstrations, Hub, or GPU. Do
not report it as physical validation or evidence of task success. Hardware
acceptance remains operator-run and unverified until recorded under the
physical evidence contract.

## Worktree, ownership, and handoff

- Use a fresh worktree for an independent ticket or reviewer context. One
  implementer owns a declared file set; do not have parallel agents edit the
  same files. Preserve existing worktree changes and inspect `git status
  --short` before edits.
- Before review, hand off the actual base and head SHAs, touched files, exact
  commands and results, environment, and any dirty paths. Identify the exact
  tested SHA: if the tested worktree was dirty, say so and list those paths.
  The reviewer should inspect the actual diff against the task/spec and run
  relevant checks in a fresh context; the review is advisory.
- Record remaining work and environment limits, including missing optional
  dependencies or unavailable hardware. Keep private transcripts, tokens,
  datasets, checkpoints, and videos out of the repository. Use the existing
  [loop-state template](templates/loop-state.md) and
  [PR template](../.github/pull_request_template.md); do not create a parallel
  status framework.

## Case study: PR #35

[PR #35](https://github.com/chungtseng96/embodied-ai-lab/pull/35) landed the
recording, ACT training, and physical rollout software in commit
[`3583e2a`](https://github.com/chungtseng96/embodied-ai-lab/commit/3583e2a9cc0a638614a6123f699f595ed8734ec6).
The diff and regression tests make useful review examples:

- A selected virtualenv Python may be a symlink. The training wrapper keeps
  the selected interpreter path; regression coverage is
  [`test_training_preserves_selected_venv_python_symlink`](../projects/laundrybench/tests/test_training.py).
- LeRobot 0.6.1 requires a fresh native output directory. LaundryBench
  allocates a `native/` child under its run directory and checks final
  checkpoint contents; see
  [`test_training.py`](../projects/laundrybench/tests/test_training.py) and
  [`training/act.py`](../projects/laundrybench/src/laundrybench/training/act.py).
- A checkpoint's normalizer state is part of its policy identity. The
  contract binds and validates processor-state files as well as weights and
  processor JSON; the regression tampers with a state file and expects
  rejection in `test_local_run_requires_native_checkpoint_and_writes_rollout_contract`
  in [`test_training.py`](../projects/laundrybench/tests/test_training.py).
- Cloud training needs an immutable Hub dataset revision tied to local
  dataset identity. The wrapper requires the full commit SHA and validates
  lineage; the cloud submission/finalization coverage is in
  [`test_training.py`](../projects/laundrybench/tests/test_training.py), and
  the contract is explained in [`training-workflow.md`](architecture/training-workflow.md).

The [PR checks page](https://github.com/chungtseng96/embodied-ai-lab/pull/35/checks)
and the repository's [CI workflow](../.github/workflows/ci.yml) are the
appropriate CI evidence. The local checkout does not assert a CI result or
physical acceptance. The compatibility workflow is an optional software
smoke, not a robot test. Agent review remains advisory; human judgment and
operator acceptance own the final decisions.
