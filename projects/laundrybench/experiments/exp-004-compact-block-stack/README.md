# EXP-004 — Compact block stacking

**Date:** 2026-11-13  
**Status:** Planned  
**Hardware:** physical  
**Owner:** Chung-Tseng Wang

## Question

Can a compact two-block stacking task validate LaundryBench's demonstration,
ACT training, bounded rollout, and evidence-review workflow when there is not
enough workspace for the planned sock-sorting task?

This is an integration and manipulation benchmark. It is not a substitute for
the eventual sock-sorting task and its results must not be reported as sock-
sorting performance.

## Hypothesis

A visually simple, short-range pick-and-place task will make it possible to
collect dynamic demonstrations in the current workspace and expose grasp,
placement, camera, and policy-contract failures before expanding to a larger
task.

## Baseline

- policy/model: supervised leader teleoperation for data collection; no trained checkpoint yet
- dataset: planned private local `compact_block_stack_v1` dataset; not yet recorded
- code/config version: exact repository commit and LeRobot `0.6.1` environment recorded in the run manifest
- evaluation conditions: tabletop scene, two lightweight blocks, arm-mounted `front` camera for policy input, overhead `third_person` camera for operator evidence only

## Change

Use the following task and protocol identities in the copied recording,
training, and rollout configs:

- task ID: `compact_block_stack_v1`
- protocol ID: `compact_block_stack_collection`
- task text: “Pick up one block from the marked start zone and place it on the base block.”

Start with two large or lightweight blocks, a fixed base position, and a
marked start zone. Do not begin with a full Jenga tower or small medication
items. Keep this dataset separate from the future `sock_sorting_v1` dataset.

The arm-mounted front camera remains the only policy camera. The overhead
camera is operator evidence only and must not be added to the current
one-camera ACT contract. Do not use the built-in FaceTime or iPhone cameras.

## Evaluation protocol

### Phase 0 — recording and contract smoke

1. Place the base and one block in marked positions on a clear tabletop.
2. Confirm the calibrated leader/follower roles, camera profile, and physical stop path.
3. Stop any active LeLab teleoperation before starting the LaundryBench recorder; the recorder must own the serial ports and policy camera.
4. Copy `configs/recording.example.yaml` to a private local config and replace all ports, IDs, calibration paths, camera values, absolute dataset paths, and task text.
5. Run the recording dry-run and inspect the printed command before connecting hardware:

   ```bash
   .venv-lerobot/bin/python \
     projects/laundrybench/scripts/record.py \
     --config /tmp/recording.block-stack.yaml
   ```

6. With an operator present at the follower, record two to five short episodes:

   ```bash
   .venv-lerobot/bin/python \
     projects/laundrybench/scripts/record.py \
     --config /tmp/recording.block-stack.yaml \
     --execute --supervised
   ```

The phase passes only when the recording manifest is completed, the dataset
contains valid metadata and videos, the front-camera frames are playable, and
the six-joint state/action contract matches the selected LeRobot version.

### Phase 1 — initial demonstration set

Collect approximately 20–30 consistent successful demonstrations with the
same task text and camera contract. Keep the first demonstrations nearly
identical; introduce small block-position and orientation variations only
after the fixed-layout motion is repeatable. Discard episodes with camera
loss, invalid resets, accidental contact, or operator intervention rather
than treating them as successful examples.

Fingerprint the completed local dataset before training:

```bash
.venv-lerobot/bin/python \
  projects/laundrybench/scripts/train.py \
  --fingerprint-dataset /absolute/path/to/compact_block_stack_v1
```

### Phase 2 — policy validation

1. Copy `configs/training.example.yaml` and bind it to the completed dataset,
   its manifest, task/protocol IDs, exact FPS, and a new output directory.
2. Run the training plan without execution. Train on a Linux/NVIDIA host or
   through the configured private HF Jobs path; the Intel Mac is not the
   intended ACT training host.
3. Require a local checkpoint with `policy_contract.json` and matching saved
   processor files before rollout.
4. Copy `configs/rollout.example.yaml` and configure one episode, a short
   timeout, the same front-camera contract, and a conservative normalized
   `max_relative_target` such as `0.25`.
5. Run the rollout dry-run:

   ```bash
   .venv-lerobot/bin/python \
     projects/laundrybench/scripts/run_policy.py \
     --config /tmp/rollout.block-stack.yaml
   ```

6. With the operator at the arm and an accessible physical stop, run one
   supervised physical episode:

   ```bash
   .venv-lerobot/bin/python \
     projects/laundrybench/scripts/run_policy.py \
     --config /tmp/rollout.block-stack.yaml \
     --execute --supervised
   ```

7. Inspect the captured camera media, traces, commands, and diagnostics in
   the LaundryBench UI. Label the outcome manually; a clean process exit is
   not task-success evidence.

### Success definition

An episode is successful only when the policy releases the block, the block
remains fully supported on the base for at least two seconds, the base stays
inside its marked area, and no human intervention is required.

### Held-out conditions

After the fixed-layout policy is stable, evaluate small changes to block
position and orientation. Expand to a three-block tower only after the
two-block task passes under the same review protocol.

### Intervention policy

The operator must stop immediately for unexpected motion, camera loss,
collision risk, unstable stacking, or a contract/configuration mismatch.
Every physical episode remains provisional until its evidence is inspected
and its outcome and failure category are saved in the UI.

## Results

| Metric | Baseline | Candidate |
|---|---:|---:|
| Success rate | | |
| Median completion time | | |
| Human interventions | | |

## Failure breakdown

Pending physical demonstrations. Classify failures separately as grasp,
placement/alignment, block stability, camera/evidence quality, policy timing,
or operator intervention.

## Evidence

- code/config commit: pending; record the exact commit in the run manifest
- command run: pending
- output excerpt (raw, not paraphrased): pending
- episode log path: outside git, under the experiment output directory
- negative check: no physical task success, trained-policy quality, or sock-sorting result is claimed until the corresponding run is reviewed

## Conclusion

Pending. This document records the planned compact benchmark only; no
demonstrations, training run, or physical policy rollout are logged here.

## What to try next

- If two-block stacking passes, collect varied demonstrations and evaluate a
  three-block stack.
- If stacking fails, select the dominant reviewed failure and collect targeted
  demonstrations before changing the model or hardware.
- Return to `sock_sorting_v1` once the workspace and evidence loop support it.
