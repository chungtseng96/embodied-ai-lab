# Embodied AI Lab

A hands-on learning and portfolio repository for building practical understanding of embodied AI and robot-learning systems.

## Current flagship project

**LaundryBench** — teach an SO-101 robot to identify, pick up, and sort simple laundry items, then build the surrounding data, evaluation, observability, and iteration loop.

## Repo goals

- Learn robotics concepts through small, concrete labs
- Build reusable software around robot learning and evaluation
- Keep architecture model-agnostic where possible
- Document experiments, failures, and design decisions
- Demonstrate transferable AI/ML platform engineering skills in robotics

## Structure

```text
embodied-ai-lab/
├── docs/
│   ├── fundamentals/
│   ├── cheatsheets/
│   ├── architecture/
│   └── journal/
├── labs/
├── projects/
│   └── laundrybench/
├── resources/
├── pyproject.toml
└── Makefile
```

## Learning path

- [x] Robot anatomy and joints
- [x] Joint space vs Cartesian space
- [x] Coordinate frames
- [x] Forward vs inverse kinematics
- [ ] Degrees of freedom and end-effector pose
- [ ] Trajectories and control loops
- [ ] Imitation learning
- [ ] Robot policies
- [ ] Vision-language-action models
- [ ] Evaluation and failure analysis

## Project status

Hardware ordered. While waiting for delivery, the focus is on fundamentals and building a software skeleton that can later swap mocked inputs for the real robot.
