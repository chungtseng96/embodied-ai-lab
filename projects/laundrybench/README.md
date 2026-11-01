# LaundryBench

LaundryBench is the flagship embodied-AI project in this repository.

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
 Evaluation / Observability
```

The interfaces are intentionally model-agnostic so ACT, SmolVLA, or future policies can be adapted behind the same boundary.

## Current code layout

```text
src/laundrybench/
├── robot/              # hardware boundary + mock robot
│   └── so101_spec.py   # SO-101 joint names and units
├── policies/           # policy boundary + mock policy
├── data/               # dataset/episode helpers
├── evaluation/         # closed-loop runner + metrics
│   └── judge.py        # episode success judge
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

The mock robot is only a development stand-in. It lets us test experiment/evaluation plumbing before hardware arrives; its success rate has no physical meaning.

## Plan of record

What comes next, including physical integration, is tracked in the [V1 implementation plan](../../docs/plans/2026-10-31-laundrybench-v1-implementation.md), which works through the findings in the [V1 design review](../../docs/plans/2026-10-31-laundrybench-design-review.md).

## What this project should demonstrate

- robot data collection
- clean hardware/model abstractions
- policy execution
- reproducible experiments
- evaluation and failure analysis
- observability across video, robot state, and outcomes
- disciplined model/data iteration

## Planned progression

1. Sock vs non-sock
2. Multiple socks/colors/styles
3. Multiple clothing categories
4. Cluttered laundry pile
5. Flatten/orient garments
6. Folding with two arms
