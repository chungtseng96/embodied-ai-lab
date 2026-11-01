# LeRobot Cheatsheet

## Mental model

LeRobot is the robotics framework layer we reuse so LaundryBench can focus on the learning/evaluation loop.

```text
LaundryBench
    ↓
LeRobot abstractions
    ↓
SO-101 + camera + datasets + policy tooling
```

## What we expect to use it for

- SO-101 hardware integration
- calibration / teleoperation workflows
- episode recording
- dataset format/tooling
- baseline policy training and inference

## Current POC gate

The first testing POC is an environment check, not a robot-control script:

```bash
make lerobot-check PYTHON=/path/to/python3.12
```

As of the current LeRobot docs checked on 2026-09-18, new installs should use Python 3.12. Install LeRobot inside that environment:

```bash
python -m pip install lerobot
lerobot-info
```

On Intel macOS, the full LeRobot install may be blocked by modern PyTorch wheel availability. For CLI-only discovery, this works:

```bash
python -m pip install --no-deps "lerobot==0.6.1"
lerobot-info
```

The repo intentionally keeps `lerobot` out of LaundryBench's core dependencies until we wire a real hardware, dataset, or policy adapter. The POC gate verifies:

- Python version
- whether `lerobot` is importable
- installed `lerobot` version
- whether `ffmpeg` and `lerobot-info` are visible on `PATH`

## What LaundryBench owns

- task definition
- experiment config
- evaluation protocol
- outcome labels / failure taxonomy
- comparison and reporting
- model/data iteration logic

## Reminder

Do not wrap LeRobot just for the sake of abstraction. Add adapters only where we need a stable LaundryBench boundary or want to compare implementations.
