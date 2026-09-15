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

## What the project should demonstrate

- Robot data collection
- Policy execution
- Experiment tracking
- Evaluation
- Failure analysis
- Model/data iteration
- Clear software boundaries that allow future policy swaps

## Planned progression

1. Sock vs non-sock
2. Multiple socks/colors/styles
3. Multiple clothing categories
4. Cluttered laundry pile
5. Flatten/orient garments
6. Folding with two arms
