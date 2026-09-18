# Embodied AI Lab

A hands-on learning and portfolio repository for building practical understanding of embodied AI and robot-learning systems.

## Flagship project: LaundryBench

Teach an SO-101 robot to identify, pick up, and sort simple laundry items, then build the surrounding software for data collection, policy execution, evaluation, observability, and iteration.

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
├── AGENTS.md               # entry point for AI agents (CLAUDE.md links here)
├── ROADMAP.md
├── docs/
│   ├── README.md           # which doc to read for what
│   ├── fundamentals/       # concepts being learned
│   ├── cheatsheets/        # fast interview/debug references
│   ├── architecture/       # system design + ADRs
│   ├── journal/            # learning log
│   ├── plans/              # dated design / work plans
│   └── templates/          # reusable notes/experiments
├── labs/                   # small concept -> code -> hardware exercises
├── projects/
│   └── laundrybench/
│       ├── AGENTS.md       # code-level agent guide
│       ├── CONTEXT.md      # glossary, invariants, parked questions
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
5. Never present synthetic/mock results as physical robot results.
