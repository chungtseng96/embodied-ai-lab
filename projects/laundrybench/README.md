# LaundryBench

LaundryBench is the first project in Embodied AI Lab: a laundry manipulation
benchmark and evaluation workbench for an SO-101 arm.

## V1 task

Start with a controlled sorting task:

```text
1 sock + 1 non-sock item
        ↓
identify sock
        ↓
pick it up
        ↓
move to sock basket
        ↓
drop
        ↓
log success/failure
```

## V1 constraints

- One SO-101 follower arm
- One fixed external camera
- Fixed table and basket locations
- Lightweight clothing only
- No overlapping garments initially
- Manual resets are acceptable

## Software architecture

```text
Observation
  ├── camera frame
  └── robot state
        ↓
      Policy
        ↓
      Action
        ↓
      Robot
        ↓
 episode outcome + telemetry
        ↓
 Evaluate / capture media / human review
        ↓
 Targeted demonstrations or config change
```

The interfaces are intentionally model-agnostic; a supervised LeRobot 0.6.1 ACT path is now implemented through recording, contract-bound training, bounded rollout, and LaundryBench evidence review. Hardware acceptance remains pending.

## Project layout

```text
src/laundrybench/
├── robot/              # hardware boundary + mock robot
│   └── so101_spec.py   # SO-101 joint names and units
├── policies/           # policy boundary + mock policy
├── data/               # dataset/episode helpers
├── evaluation/         # mock and physical closed-loop runs + metrics + capture
├── training/           # dataset-bound ACT training/provenance
├── observability/      # structured logging
│   └── manifest.py     # experiment run manifest
├── config.py           # load and validate configs/*.yaml
└── types.py            # shared observation/action/result types
```

## Run the mock loop

From the repo root:

```bash
python3.11 -m venv .venv && .venv/bin/python -m pip install -e "projects/laundrybench[dev]"
make check
make demo
```

`make` uses `.venv/bin/python` when it exists; pass `PYTHON=...` to override.

The mock robot is only a development stand-in. Its success rate has no physical meaning.

## Supervised physical pipeline

The physical path is separate from mock-first `robot.yaml` / `camera.yaml`:

- `configs/recording.example.yaml` + `scripts/record.py`: dry-run-first LeRobot dataset recording with separate calibrated follower/leader roles and a lifecycle manifest.
- `configs/training.example.yaml` + `scripts/train.py`: strict dataset/recording contract validation, local ACT training, checkpoint provenance, and explicit private Hugging Face Jobs mode.
- `configs/rollout.example.yaml` + `scripts/run_policy.py`: checkpoint/processor contract validation, bounded supervised ACT execution, LaundryBench traces and camera evidence.
- `scripts/serve.py` + `scripts/report.py`: human-review labels and reviewed-only metrics for the physical run directory.

Start with [the SO-101 home feedback loop guide](docs/playbooks/so101-home-feedback-loop.md), which explains exact setup, dry-run commands, expected artifacts, review, and troubleshooting. Inspect the safe CLI surfaces from this project directory:

```bash
python scripts/record.py --help
python scripts/train.py --help
python scripts/run_policy.py --help
```

Record and rollout require explicit `--execute --supervised`; recording also requires an interactive foreground terminal and both calibrated arm roles. Do not run the checked-in example configs against hardware without replacing their placeholders. No physical acceptance, real ACT training, or task success is implied by the software implementation or offline tests.

## Plan of record

The [V1 implementation plan](docs/plans/2026-10-31-laundrybench-v1-implementation.md) and [V1 design review](docs/plans/2026-10-31-laundrybench-design-review.md) track broader project work. The next physical gate is operator-run acceptance on the calibrated device, including camera freshness/capture timing, checkpoint inference, stop/reconnect behavior, and manually reviewed task outcomes.

## System responsibilities

- robot data collection
- clean hardware/model abstractions
- policy execution
- reproducible experiments
- evaluation and failure analysis
- observability across video, robot state, and outcomes
- disciplined model/data iteration

## Candidate task extensions

1. Sock vs non-sock
2. Multiple socks/colors/styles
3. Multiple clothing categories
4. Cluttered laundry pile
5. Flatten/orient garments
6. Folding with two arms

## Documentation and ownership

- [Documentation index](docs/README.md): architecture, operating guides, and plans.
- [Milestones](ROADMAP.md): current software capabilities and physical acceptance gates.
- `configs/`: task, robot, camera, recording, training, and rollout inputs.
- `scripts/`: CLI entry points for operators and automation.
- `frontend/`: results and episode-review application.
- `tests/` and `e2e/`: Python contracts and browser acceptance.
- `experiments/`: hypotheses, protocols, and recorded evidence.

Datasets, checkpoints, videos, and generated run directories stay outside Git.
