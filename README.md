# Embodied AI Lab

A hands-on learning and portfolio repository for building practical understanding of embodied AI and robot-learning systems.

## Flagship project: LaundryBench

Teach an SO-101 robot to identify, pick up, and sort simple laundry items, then build the surrounding software for data collection, policy execution, evaluation, observability, and iteration.

The deep engineering focus is a **policy-agnostic evaluation and
failure-driven data platform**. LaundryBench will use one working policy to
make the loop physical, while owning the protocols, traces, quality checks,
failure analysis, comparison reports, and targeted-data workflow around it.

See the [evaluation platform architecture](docs/architecture/evaluation-platform.md)
and [ADR 004](docs/architecture/decisions/004-evaluation-and-data-platform-focus.md)
for the decision and initial design.

The portfolio goal is not just **"make the robot move."** It is to demonstrate the full improvement loop:

```text
robot experience
      ↓
 data / episodes
      ↓
 train or adapt policy
      ↓
 deploy to robot
      ↓
 evaluate behavior
      ↓
 inspect failures
      ↓
 targeted change
      └──────────────→ repeat
```

## Repository map

```text
embodied-ai-lab/
├── START-HERE.md
├── ROADMAP.md
├── docs/
│   ├── fundamentals/       # concepts being learned
│   ├── cheatsheets/        # fast interview/debug references
│   ├── architecture/       # system design + ADRs
│   ├── journal/            # learning log
│   └── templates/          # reusable notes/experiments
├── labs/                   # small concept -> code -> hardware exercises
├── projects/
│   └── laundrybench/
│       ├── configs/
│       ├── experiments/
│       ├── scripts/
│       ├── src/laundrybench/
│       └── tests/
├── resources/              # papers, repos, videos, companies
└── Makefile
```

## Learning path

- [x] Robot anatomy and joints
- [x] Joint space vs Cartesian space
- [x] Coordinate frames
- [x] Forward vs inverse kinematics
- [ ] End-effector pose and orientation
- [ ] Trajectories and control loops
- [ ] Imitation learning
- [ ] Robot policies
- [ ] Vision-language-action models
- [ ] Closed-loop evaluation and failure analysis

## Current status

- SO-101 leader/follower hardware ordered
- External USB camera ordered
- Mock robot/policy architecture in place
- Evaluation runner, metrics, and structured logging in place
- Evaluation-platform direction and initial architecture documented
- Physical LeRobot integration intentionally waits for hardware bring-up

## Quick start: mock software loop

```bash
make install
make test
make demo
```

The mock implementation exists only to exercise the software boundaries before the physical robot arrives. Mock results are **not** robot performance claims.

## Design principles

1. Keep the first physical task narrow.
2. Keep software boundaries reusable.
3. Reuse LeRobot instead of rebuilding hardware/model plumbing unnecessarily.
4. Treat experiments and failures as first-class artifacts.
5. Go deep on evaluation and data improvement; reuse policy and hardware
   plumbing where practical.
6. Never present synthetic/mock results as physical robot results.
