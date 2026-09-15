# Start Here

This repository is both a learning notebook and a working embodied-AI lab.

## Current objective

Build **LaundryBench V1**: use an SO-101 robot to identify, pick up, and sort simple laundry items while building the surrounding software for data collection, policy execution, evaluation, observability, and iteration.

## Recommended order

1. Read `README.md` for the big picture.
2. Use `docs/fundamentals/` to build robotics vocabulary.
3. Use `docs/cheatsheets/robotics.md` as the quick reference.
4. Work through `labs/` as the hardware arrives.
5. Build the real project in `projects/laundrybench/`.
6. Record every meaningful model/data/config change as an experiment.

## Working principle

Keep the physical task small and the software loop real:

```text
observe -> act -> log -> evaluate -> diagnose -> change -> compare
```

## Current status

- SO-101 leader/follower hardware ordered
- External USB camera ordered
- Fundamental robotics concepts in progress
- Software skeleton uses mock robot/policy interfaces until hardware integration begins
