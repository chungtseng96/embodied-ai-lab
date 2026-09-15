# Getting Started — 2026-09-15

## Goal

Build enough robotics fluency to transition from AI/ML platform engineering into embodied AI / robot-learning infrastructure.

## Current hardware plan

- SO-101 leader/follower setup ordered
- External USB camera ordered
- Laptop will run the local software and inference where practical
- Cloud GPU can be used for training when needed

## Current mental model

```text
camera + robot state -> policy -> robot actions -> physical world
                           ^              |
                           |              v
                    training/eval <- logs + outcomes
```

## Concepts covered so far

- joints and degrees of freedom
- joint space vs Cartesian space
- coordinate frames
- forward and inverse kinematics

## Next

- end-effector pose and orientation
- trajectories and control loops
- how demonstrations become robot-learning datasets
- how ACT and VLA policies differ
