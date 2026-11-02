# Embodied AI Lab

A hands-on learning and portfolio repository for building practical understanding of embodied AI and robot-learning systems.

## Flagship project: LaundryBench

Teach an SO-101 robot to identify, pick up, and sort simple laundry items, then build the surrounding software for data collection, policy execution, evaluation, observability, and iteration.

The portfolio goal is not just **"make the robot move."** It is to demonstrate the full improvement loop:

```text
robot experience
      ↓
 data / episodes
      ↓
 train or adapt policy
      ↓
 deploy to robot
      ↓
 evaluate behavior
      ↓
 inspect failures
      ↓
 targeted change
      └──────────────→ repeat
```

The engineering focus is a policy-agnostic evaluation and failure-driven data platform.
See the [platform direction](docs/architecture/evaluation-platform.md) and
[ADR 005](docs/architecture/decisions/005-evaluation-and-data-platform-focus.md).
The mock loop validates software contracts; physical results require real robot evaluation.

## Repository map

```text
embodied-ai-lab/
├── START-HERE.md
├── ROADMAP.md
├── docs/
│   ├── fundamentals/       # concepts being learned
│   ├── cheatsheets/        # fast interview/debug references
│   ├── architecture/       # system design + ADRs
│   ├── journal/            # learning log
│   └── templates/          # reusable notes/experiments
├── labs/                   # small concept -> code -> hardware exercises
├── projects/
│   └── laundrybench/
│       ├── configs/
│       ├── experiments/
│       ├── scripts/
│       ├── src/laundrybench/
│       └── tests/
├── resources/              # papers, repos, videos, companies
└── Makefile
```

## Learning path

- [x] Robot anatomy and joints
- [x] Joint space vs Cartesian space
- [x] Coordinate frames
- [x] Forward vs inverse kinematics
- [ ] End-effector pose and orientation
- [ ] Trajectories and control loops
- [ ] Imitation learning
- [ ] Robot policies
- [ ] Vision-language-action models
- [ ] Closed-loop evaluation and failure analysis

## Current status

- SO-101 bring-up guide is for an already calibrated arm; physical hardware acceptance is host-specific and pending
- LaundryBench record/train/ACT rollout wrappers and camera evidence path are implemented; no physical end-to-end run or task-success claim has been validated
- Mock robot/policy architecture in place
- Evaluation runner, metrics, and structured logging in place
- React results application and persistent manual review labels available
- Run-context sidecars and compatibility-aware comparisons are implemented; reviewer keyboard controls and browser acceptance are in PR #32
- Browser acceptance runs in GitHub Actions; see [PR #32 checks](https://github.com/chungtseng96/embodied-ai-lab/pull/32/checks) for the latest result
- SO-101 adapter, normalized ACT contract, supervised rollout and live camera evidence capture implemented with offline/synthetic tests; calibrated-device compatibility and task performance remain unverified

## Quick start: mock software loop

### Results and manual-labeling application

The React/TypeScript frontend browses real run artifacts, compares experiments,
shows episode traces and saves manual outcome labels through a local Python API.
Labels survive reloads and update displayed metrics while preserving original
episode records. It has no robot movement controls.

After installing Python 3.11+ and Node.js 22+, run:

```bash
python3 -m venv .venv
make install
make frontend-install
make frontend-check
make web-demo
make web
```

Open `http://127.0.0.1:8765`. `web-demo` creates two clearly marked synthetic runs
without replacing existing runs or labels. To review your own data, point
`projects/laundrybench/scripts/serve.py --outputs-root PATH --frontend-dir
projects/laundrybench/frontend/dist` at the directory containing experiment
folders. Run one writer server per outputs directory.

The [operator guide](docs/architecture/results-application.md) explains review,
label storage, keyboard shortcuts and development. Record task, protocol,
dataset, checkpoint and configuration context in an `experiment.json` sidecar
with [`set_run_metadata.py`](projects/laundrybench/scripts/set_run_metadata.py);
the [experiment-context guide](docs/architecture/experiment-context.md) explains
the schema and compatibility rules. The [browser acceptance guide](docs/architecture/browser-acceptance.md)
documents the real-backend Playwright suite and CI workflow. The [SO-101 adapter](docs/architecture/so101-adapter.md)
is implemented and tested offline; hardware calibration, recording, ACT training
and physical rollout verification remain separate milestones.

`make check` needs Python 3.11+. Create the virtual environment once; `make`
then uses `.venv/bin/python` by default:

```bash
python3.11 -m venv .venv && .venv/bin/python -m pip install -e "projects/laundrybench[dev]"
make check
make demo
```

The mock implementation exercises software contracts and enables repeatable synthetic UI review. Mock results are **not** robot performance claims.

## Physical feedback pipeline: inspect before executing

The physical pipeline is implemented behind explicit configs and flags. Start with the [SO-101 home feedback loop playbook](docs/playbooks/so101-home-feedback-loop.md), which separates the runnable synthetic UI loop from physical acceptance and gives the record → train → bounded rollout → review workflow. Copy and replace the device-specific examples before using them. After activating the LaundryBench environment from the quick start, run these CLI help commands from `projects/laundrybench`; they do not connect hardware:

```bash
cd projects/laundrybench
python scripts/record.py --help
python scripts/train.py --help
python scripts/run_policy.py --help
```

Physical recording requires `--execute --supervised` in a foreground terminal and uses distinct calibrated follower and leader roles. Training requires a completed dataset/recording manifest and an explicit train execute flag; rollout has a contract-checking dry run and requires `--execute --supervised` for hardware. Hardware acceptance, actual ACT training, camera timing and laundry task success remain unverified here. See the [recording](docs/architecture/recording-workflow.md), [training](docs/architecture/training-workflow.md), and [rollout](docs/architecture/act-rollout.md) details.

## Engineering workflow

The project uses a script- and configuration-driven workflow designed for
local development, a nearby robot computer, and cloud GPU training. Read the
[robot-learning development environment](docs/architecture/robot-learning-development-environment.md)
and the [SO-101 readiness plan](docs/plans/so101-readiness.md) before adding
hardware or training code. Repository and agent conventions live in
[`AGENTS.md`](AGENTS.md) and `skills/`.

## Design principles

1. Keep the first physical task narrow.
2. Keep software boundaries reusable.
3. Reuse LeRobot instead of rebuilding hardware/model plumbing unnecessarily.
4. Treat experiments and failures as first-class artifacts.
5. Never present synthetic/mock results as physical robot results.
