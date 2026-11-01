# Lab 05: LeRobot POC Gate

## Goal

Verify that the local environment can run LeRobot before wiring LaundryBench to physical SO-101 hardware.

This lab is intentionally small. It answers:

- Is the active Python new enough for current LeRobot installs?
- Is `lerobot` importable?
- Which LeRobot version is installed?
- Are basic CLI/video tools visible?

## Setup

Create a Python 3.12 environment using your preferred tool. The current LeRobot docs recommend Python 3.12 for new environments.

```bash
python3.12 -m venv .venv-lerobot
source .venv-lerobot/bin/activate
python -m pip install --upgrade pip
python -m pip install lerobot
```

On this Intel macOS machine, the full LeRobot 0.6.1 install is blocked because the required PyTorch range (`torch>=2.7,<2.12`) is not published for this platform; PyPI only offers `torch` 2.2.x here. The CLI can still be installed for environment discovery:

```bash
python -m pip install --no-deps "lerobot==0.6.1"
lerobot-info
```

Then run:

```bash
make lerobot-check PYTHON=.venv-lerobot/bin/python
```

## Expected result

The command should print JSON showing:

- `"meets_lerobot_docs_minimum": true`
- `"importable": true`
- a non-null LeRobot version
- `lerobot-info` visible either on `PATH` or next to the selected Python executable

## Current machine baseline

On 2026-09-18, the default `python3` in this workspace is Python 3.9.6. Homebrew `python@3.12` was installed, and `.venv-lerobot` now has LeRobot 0.6.1 CLI entry points installed with `--no-deps`.

Known gaps on this machine:

- `ffmpeg` is not installed.
- Full LeRobot training/runtime dependencies are not installed.
- Modern PyTorch wheels required by LeRobot 0.6.1 are unavailable for this macOS x86_64 environment.

## Next MVP step

After this gate passes, the next useful MVP is one of:

- run `lerobot-info` and save the output in an experiment note
- calibrate SO-101 through LeRobot's documented workflow
- record a tiny demonstration dataset outside LaundryBench, then add a read-only dataset inspection script here
- implement a thin LaundryBench adapter only after the LeRobot robot/policy object shape is known from the installed version
