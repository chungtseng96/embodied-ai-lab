# LaundryBench Development Environment

**Status:** Implemented hybrid profiles; physical acceptance pending

**Date:** 2026-11-03

## Decision summary

LaundryBench will use a hybrid development environment:

- the laptop is the development, testing, documentation, and orchestration
  host;
- on Intel macOS, a pinned native edge profile performs serial, camera,
  recording, and supervised rollout work beside the arm;
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

The initial development host is an Intel Mac. Full LeRobot/PyTorch training
requires a compatible Linux or Apple-Silicon runtime; a CLI installation alone
does not establish training readiness. Docker and device compatibility must be
checked on the selected host. Mock development must remain independent of
physical hardware.

The workflow must expose dependency management, interfaces, experiment control,
and deployment boundaries through versioned commands and configuration.

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
gate uses the checked-in native edge profile instead of pretending that the
Linux/Apple-Silicon TorchCodec stack is available. The profile pins Python
packages in `requirements/edge-macos-x86_64.lock.txt`, installs LeRobot 0.6.1
without its incompatible platform metadata, and verifies the supported PyAV
video backend plus ACT imports. It is for hardware I/O and CPU-side data
inspection; it is not the training image.

Create or recreate the profile with:

```bash
python3 projects/laundrybench/scripts/bootstrap_edge_env.py \
  --venv /absolute/path/to/laundrybench-lerobot-edge
EDGE_PYTHON=/absolute/path/to/laundrybench-lerobot-edge/bin/python
make host-check PYTHON="$EDGE_PYTHON"
make lerobot-check PYTHON="$EDGE_PYTHON"
```

The bootstrap is idempotent for an existing virtual environment and does not
touch calibration, datasets, checkpoints, or the host's system Python. The
Intel profile cannot pass `uv pip check` against LeRobot's upstream Linux/
Apple-Silicon dependency declarations; `check_lerobot.py` is the authoritative
profile-aware readiness check. LeLab and Rerun are optional and are not part of
the Intel edge contract. A standalone `ffmpeg` executable is also optional on
Intel macOS because the edge profile uses PyAV; it remains required by the
Linux/NVIDIA training profile.

### Robot edge host

The edge host should run a supported Linux/Python environment with the full
LeRobot hardware extras. It stays physically close to the arm and camera. Its
responsibilities are calibration, teleoperation, recording, replay, and
rollout. It should use explicit robot and camera configuration and should not
silently select a serial port.

The native Intel profile is a laptop fallback for the same edge responsibilities
when the physical devices are attached to macOS. For a long-lived home setup,
prefer a Linux edge host so the hardware and the training/runtime dependency
family can use the same supported platform.

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

Build the training image from the selected source revision on a Linux/NVIDIA
host (Docker Desktop on Intel macOS is only a local build/smoke-test option):

```bash
docker build \
  --file projects/laundrybench/Dockerfile.train \
  --build-arg LAUNDRYBENCH_SOURCE_SHA="$(git rev-parse HEAD)" \
  --tag laundrybench-train:$(git rev-parse --short HEAD) \
  projects/laundrybench
```

The image owns exact ACT training dependencies; it must not be used as the
USB/camera device owner. Keep the edge process native to the machine where the
arm and cameras are connected.

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

Notebooks are allowed for temporary analysis and visualization. They are not the source of truth for:

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

### Rebootable environment contract

The edge and training environments are reproducible at different boundaries:

| Boundary | Reproducibility artifact | Owns |
| --- | --- | --- |
| Intel macOS edge | `bootstrap_edge_env.py` plus the exact lock file | serial, cameras, native recording, CPU-side rollout checks |
| Linux/NVIDIA training | `Dockerfile.train` plus source SHA and experiment config | ACT training and checkpoint production |

Rebooting the laptop means rerunning the edge bootstrap and then the read-only
host/LeRobot checks. Rebooting a training worker means rebuilding the image
from the same source SHA. Calibration files, device paths, datasets, and model
weights remain external state and must be identified in the experiment record;
they are not baked into either artifact.

## Readiness gate for the arm

The project is ready for delivery when the following are true:

- the repository is clean enough to identify new work and all agent guidance
  is present;
- local tests and lint pass;
- the host preflight reports the known laptop gaps explicitly;
- the selected edge profile can be recreated from the checked-in lock file;
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
