# Roadmap

## Phase 0 — Foundations

- [x] Define V1 benchmark: laundry sorting
- [x] Order SO-101 leader/follower hardware
- [x] Order external USB camera
- [x] Learn joint space vs Cartesian space
- [x] Learn coordinate frames
- [x] Learn forward vs inverse kinematics
- [ ] Learn end-effector pose and orientation
- [ ] Learn trajectories and control loops
- [ ] Learn imitation learning and robot policies

## Phase 1 — Mock software loop

- [x] Define model-agnostic robot and policy interfaces
- [x] Add mock robot/policy
- [x] Add evaluation runner and metrics
- [x] Add structured episode logging
- [ ] Add step-level episode traces
- [ ] Add simple local report generation

## Phase 1.5 — Evaluation platform vertical slice

- [ ] Define experiment and condition manifest
- [ ] Define episode/artifact contract
- [ ] Add baseline-versus-candidate comparison
- [ ] Add initial failure taxonomy
- [ ] Add dataset and sensor-quality checks
- [ ] Add deterministic failure-injection tests
- [ ] Document local artifact layout and reproducibility rules

## Phase 2 — Hardware bring-up

- [ ] Assemble/connect SO-101
- [ ] Calibrate leader and follower
- [ ] Read joint state
- [ ] Move one joint safely
- [ ] Capture camera frames
- [ ] Teleoperate leader -> follower

## Phase 3 — LaundryBench baseline

- [ ] Record first demonstrations
- [ ] Train first baseline policy through LeRobot
- [ ] Run fixed evaluation protocol
- [ ] Log failures by category
- [ ] Publish baseline results

## Phase 4 — Improvement loop

- [ ] Choose one dominant failure mode
- [ ] Add targeted demonstrations or a model/config change
- [ ] Re-run the same evaluation
- [ ] Compare baseline vs candidate
- [ ] Document result honestly, including negative results

## Future

- SmolVLA / VLA comparison
- Simulation backend and sim-to-real experiments
- More clothing categories
- Clutter and overlap
- Second camera
- Dual-arm manipulation
- Folding
- Simulation and synthetic data
