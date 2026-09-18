# LaundryBench Robot-Learning Development Environment

**Status:** Proposed

**Date:** 2026-09-17

## Decision summary

LaundryBench will use a hybrid development environment:

- the laptop is the development, testing, documentation, and orchestration
  host;
- a local Linux-capable robot computer performs hardware bring-up, camera
  capture, teleoperation, and policy rollout beside the SO-101;
- a cloud Linux NVIDIA GPU runs training and larger evaluations;
- Docker defines the reproducible cloud runtime;
- LeRobot owns low-level hardware, dataset, and policy mechanics;
- LaundryBench owns task adapters, experiment configuration, evaluation,
  metrics, and evidence;
- the CLI and checked-in scripts are the canonical workflow;
- LeLab is an optional graphical operator surface for hardware bring-up, not
  the only way to reproduce an experiment.

This design keeps the project useful on an Intel Mac while making the complete
training path reproducible on Linux GPU infrastructure. It also makes the
engineering work visible in a code review: commands, configs, tests, images,
logs, and experiment records are all versioned or linked.

## Context

The SO-101 has not yet arrived. The current laptop is an Intel Mac with a
working Python 3.12 virtual environment containing the LeRobot 0.6.1 CLI, but
the full LeRobot/PyTorch training stack is not a practical local target. The
machine has Docker Desktop installed and a working `desktop-linux` daemon when
that context is selected. The project also needs to remain useful before the
physical robot is available.

The portfolio goal is to demonstrate production-oriented embodied-AI
engineering. A notebook-only workflow would hide dependency management,
interfaces, reproducibility, experiment control, and deployment boundaries.

## System shape

```text
                         Git repository
                  code / configs / tests / docs
                         /       |       \\
                        /        |        \\
                       v         v         v
              laptop CI     cloud GPU    experiment records
             mock + lint    Docker job    metrics / logs / links
                                      \\
                                       v
                              trained checkpoint
                                       |
                                       v
        local robot computer <── model/config ──> SO-101 + cameras
          calibrate / record / rollout / observe
```

The physical robot is intentionally not a cloud dependency. A cloud job cannot
reliably own a USB serial device and camera beside the arm. The edge side
collects and executes; the cloud side trains and evaluates where GPU compute
is available.

## Responsibilities

| Area | System of record | Typical output |
| --- | --- | --- |
| Robot control and calibration | LeRobot | calibration state, device metadata |
| Camera and episode recording | LeRobot | LeRobotDataset episodes |
| Task definition and experiment protocol | LaundryBench | YAML config and experiment note |
| Policy adapter and evaluation | LaundryBench | metrics, structured logs, failure labels |
| Training runtime | Dockerized LeRobot environment | checkpoint and training logs |
| Artifact storage | Hugging Face Hub or controlled object storage | dataset/checkpoint IDs |
| Operator convenience | LeLab | repeatable UI actions backed by artifacts |
| Agent collaboration | `AGENTS.md` and `skills/` | consistent repository changes |

## Development environments

### Laptop

The laptop must support:

- Git and the repository's Python test/lint workflow;
- Python 3.12 for LeRobot-compatible tooling;
- Docker client and Docker Desktop for image build and local smoke tests;
- `uv` for isolated CLI tools such as LeLab;
- optional LeLab for hardware bring-up experiments;
- Hugging Face authentication only when a dataset or checkpoint is being
  uploaded or downloaded.

The laptop does not need to provide CUDA training. On Intel macOS, the POC
gate may report missing optional video or ML dependencies without pretending
that a partial `--no-deps` installation is a full runtime. LeLab is useful when
its dependency set can be installed; on this Intel Mac its current pinned
LeRobot/PyTorch range has no matching x86_64 macOS wheels, so the terminal
workflow remains the reliable local path.

### Robot edge host

The edge host should run a supported Linux/Python environment with the full
LeRobot hardware extras. It stays physically close to the arm and camera. Its
responsibilities are calibration, teleoperation, recording, replay, and
rollout. It should use explicit robot and camera configuration and should not
silently select a serial port.

### Cloud GPU

The cloud environment should be a Linux NVIDIA host or a managed Linux GPU
job. The runtime will be built from a repository Dockerfile and invoked by a
script with a checked-in experiment config. A successful run must produce:

- the exact source revision;
- the experiment config;
- dataset identifier and version;
- policy and dependency versions;
- random seed and device;
- training logs and checkpoint identifier;
- evaluation metrics and known limitations.

## Agent-first repository contract

The repository treats an AI coding agent as a contributor with a constrained,
reviewable workflow:

- `AGENTS.md` defines project purpose, boundaries, commands, hardware limits,
  and evidence requirements;
- nested `AGENTS.md` files add context at the project boundary;
- `skills/` contains focused workflows for engineering changes and SO-101
  bring-up;
- `make test`, `make lint`, `make lerobot-check`, and `make host-check` are
  deterministic entry points;
- experiment documents preserve why a change was made and what happened;
- tests and linting run before an agent reports a code change complete;
- hardware actions require explicit target and operator context;
- credentials, calibration state, datasets, checkpoints, and videos remain
  outside version control.

The agent contract is deliberately short. It tells an agent how to find the
right context and how to produce evidence without replacing normal engineering
judgment.

## Canonical workflow

```text
prepare host
    -> validate LeRobot environment
    -> detect hardware and cameras
    -> calibrate leader/follower
    -> teleoperate and record smoke dataset
    -> inspect and publish dataset
    -> launch scripted cloud training job
    -> evaluate checkpoint against fixed protocol
    -> deploy locally for rollout
    -> label failures and update one targeted hypothesis
```

Each arrow should eventually have a versioned command, configuration, and
observable artifact. LeLab may make the operator step easier, but the project
should retain enough metadata to reconstruct what happened.

## Notebook policy

Notebooks are allowed for temporary exploration, visualization, or learning
notes. They are not the source of truth for:

- environment setup;
- dataset recording;
- model training;
- policy evaluation;
- deployment;
- reported metrics.

Any useful notebook result must be promoted into a script, test, config, or
experiment record before it becomes part of the project's evidence.

## Decisions and tradeoffs

### Docker plus cloud instead of Docker alone

Docker provides reproducibility, but Docker Desktop on this Intel Mac is not a
substitute for a Linux NVIDIA training host. The cloud GPU supplies the
accelerator; the image supplies the repeatable environment. The same image can
be smoke-tested locally without claiming local GPU parity.

### CLI plus LeLab

The CLI is the canonical automation interface because it is scriptable,
reviewable, and suitable for CI or cloud jobs. LeLab is valuable at the moment
of physical bring-up because it reduces operator friction for calibration,
teleoperation, recording, replay, and upload. The two interfaces should use
the same LeRobot artifacts and experiment metadata.

### Separate edge and training environments

Robot control has different latency, device, and safety requirements from
training. Keeping them separate makes failures easier to diagnose and avoids
coupling a physical USB device to a remote GPU process.

## Readiness gate for the arm

The project is ready for delivery when the following are true:

- the repository is clean enough to identify new work and all agent guidance
  is present;
- local tests and lint pass;
- the host preflight reports the known laptop gaps explicitly;
- LeRobot installation and version are recorded;
- a hardware setup checklist names the expected ports, IDs, and cameras;
- a smoke-test dataset and experiment-note template exist;
- the cloud training command has a documented input/output contract;
- no notebook is required for any first-day workflow;
- the operator knows which actions can move the arm and where to stop.

## References

- [LeRobot installation](https://huggingface.co/docs/lerobot/main/en/installation)
- [LeRobot cheat sheet](https://huggingface.co/docs/lerobot/main/cheat-sheet)
- [LeLab guide](https://huggingface.co/docs/lerobot/main/lelab)
- [LeRobot imitation learning workflow](https://huggingface.co/docs/lerobot/il_robots)
- [Docker GPU support](https://docs.docker.com/engine/containers/gpu/)
