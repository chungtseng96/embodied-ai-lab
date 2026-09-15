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

## What LaundryBench owns

- task definition
- experiment config
- evaluation protocol
- outcome labels / failure taxonomy
- comparison and reporting
- model/data iteration logic

## Reminder

Do not wrap LeRobot just for the sake of abstraction. Add adapters only where we need a stable LaundryBench boundary or want to compare implementations.
