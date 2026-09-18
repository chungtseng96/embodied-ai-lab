# SO-101 readiness plan

**Date:** 2026-09-17
**Status:** In progress
**Owner:** James Wang

**Objective:** be able to calibrate, record, train, evaluate, and run a first
controlled rollout as soon as the SO-101 arrives, without depending on a
notebook.

**Working rule:** every meaningful step has a command, configuration, test or
preflight check, and an artifact that an agent or another engineer can inspect.

## Plan

| Phase | Outcome | Deliverables | Acceptance signal |
| --- | --- | --- | --- |
| 0. Laptop baseline | Know what the Mac can and cannot do | Docker/uv/LeRobot/HF host check | `make host-check` reports explicit status |
| 1. Agent-ready repo | Agents can work consistently | `AGENTS.md`, local skills, commands, experiment conventions | Agent can find instructions and run checks |
| 2. Robot edge workflow | Hardware actions are explicit and repeatable | port/camera discovery, calibration, record/replay checklist | A smoke command is documented without guessing ports |
| 3. Dataset contract | First data is usable for training | task config, camera config, episode naming, inspection command | A smoke dataset has metadata and a review note |
| 4. Cloud training | Training is reproducible off the Mac | Docker image, training script, cloud config, artifact policy | One CLI command launches a small ACT run |
| 5. Evaluation | Results are evidence rather than a demo | fixed protocol, metrics, logs, failure labels | Same checkpoint can be evaluated twice |
| 6. Deployment | A checkpoint can run beside the arm | rollout config, safety checklist, operator notes | A bounded rollout has a recorded outcome |

## Phase 0: laptop baseline

Already present:

- Homebrew Python 3.12.14;
- `.venv-lerobot`;
- LeRobot 0.6.1 CLI installed with `--no-deps`;
- Docker Desktop application and Docker client;
- repository test and lint commands.

Known gaps to resolve or explicitly defer:

- Docker Desktop is installed and its `desktop-linux` daemon is healthy;
- `uv` is installed in `~/.local/bin`;
- the `hf` CLI is installed in an isolated uv tool environment but is not
  authenticated;
- LeLab installation is currently blocked on Intel macOS because its pinned
  LeRobot/PyTorch range has no matching x86_64 macOS wheels;
- the default Docker context may still point at `/var/run/docker.sock` and
  should use `desktop-linux`;
- `ffmpeg` is not installed, though LeRobot documents an Intel-macOS PyAV
  fallback for video handling;
- the partial Intel-macOS LeRobot environment is not the cloud training
  environment.

Run the report with:

```bash
make host-check PYTHON=.venv-lerobot/bin/python
```

## Phase 1: agent-ready repository

The initial repository contract is implemented in:

- [`AGENTS.md`](../../AGENTS.md);
- [`projects/laundrybench/AGENTS.md`](../../projects/laundrybench/AGENTS.md);
- [LaundryBench engineering skill](../../skills/laundrybench-engineering/SKILL.md);
- [SO-101 bring-up skill](../../skills/so101-bringup/SKILL.md);
- [development environment design](../architecture/robot-learning-development-environment.md).

The next refinement is to add the cloud image and a config validator after the
first supported Linux installation is available. Do not hide that work behind
a notebook.

## Phase 2: hardware bring-up

Before moving the arm:

1. inventory the leader, follower, USB cables, power, and camera;
2. run serial-port discovery;
3. run camera discovery and save test frames;
4. verify the leader/follower mapping and IDs;
5. calibrate using the current LeRobot SO-101 instructions;
6. save calibration outside git;
7. perform a short supervised teleoperation check;
8. record a tiny dataset with one task and a small episode count;
9. inspect the dataset before a larger collection.

The first dataset should be a smoke test, not the final training corpus. Its
purpose is to prove the complete path from sensors to artifacts.

## Phase 3: dataset contract

The first real task remains:

```text
identify one sock -> pick it up -> move to the sock basket -> release
```

Record the following with every dataset or experiment:

- task description;
- robot and camera IDs;
- camera resolution and frame rate;
- software revision;
- LeRobot version;
- episode count and exclusions;
- dataset ID or local path;
- operator notes and visible failure modes.

## Phase 4: cloud training

The first cloud milestone is a small ACT training run with a fixed step count.
It should be launched by a CLI script against a checked-in config, inside a
Linux GPU runtime. The run must save logs and a checkpoint identifier. A
managed Hugging Face Job is acceptable for the first run; a Dockerized GPU VM
is the longer-term portfolio target.

## Phase 5: evaluation and Phase 6: deployment

Do not change the task and the evaluation protocol at the same time. Fix the
initial protocol, run a bounded number of episodes, capture structured
outcomes, and select one failure mode for the next experiment. A deployment
run must state whether it is a replay, a policy rollout, or a human-assisted
test.

## Definition of ready

When the arm arrives, the only unknowns should be hardware-specific values such
as serial ports, device IDs, and camera indices. The software workflow should
already provide:

- one command to check the host;
- one documented procedure to discover ports and cameras;
- one calibration procedure;
- one smoke recording procedure;
- one dataset inspection procedure;
- one cloud training command;
- one evaluation command;
- one rollout checklist;
- one experiment note template.
