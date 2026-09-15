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
├── robot/          # hardware boundary + mock robot
├── policies/       # policy boundary + mock policy
├── data/           # dataset/episode helpers
├── evaluation/     # closed-loop runner + metrics
├── observability/  # structured logging
└── types.py        # shared observation/action/result types
```

## Run the mock loop

From the repo root:

```bash
make install
make test
make demo
```

The mock robot is only a development stand-in. It lets us test experiment/evaluation plumbing before hardware arrives; its success rate has no physical meaning.

## Planned physical integration

1. Bring up SO-101 using LeRobot.
2. Implement a real `Robot` adapter.
3. Verify joint-state and camera data.
4. Record demonstrations.
5. Add the first real policy adapter.
6. Run `EXP-001` using a fixed physical evaluation protocol.
7. Choose one failure mode from evidence and run `EXP-002`.

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
