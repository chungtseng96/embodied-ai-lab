# EXP-003 — Physical feedback-loop acceptance

**Date:** 2026-11-02  
**Status:** Planned; software contracts implemented, physical acceptance pending  
**Hardware:** physical (planned; no attempts performed)  
**Owner:** Chung-Tseng Wang

## Question

Can one calibrated SO-101 setup complete recording, ACT training, bounded policy
rollout, evidence review, and a targeted second iteration using versioned commands?

## Hypothesis

Explicit dataset and checkpoint contracts plus captured rollout evidence will
make a supervised attempt reproducible and its manual outcome reviewable. This
tests the feedback-loop plumbing; it does not predict a trained success rate.

## Inputs and identity

Use the [home playbook](../../docs/playbooks/so101-home-feedback-loop.md).
Copy the recording, training, and rollout example configs; retain the completed
recording manifest, portable dataset content identity, training manifest, and
checkpoint contract. Record the exact source commit and selected LeRobot 0.6.1
environment. Keep datasets, calibration files, model weights, and videos out of git.

## Acceptance protocol

1. Inspect ports, calibrated IDs, camera view, and the printed recording plan.
   With an operator present, record a small private smoke dataset.
2. Validate its metadata and content identity, then train an ACT checkpoint on
   an explicitly selected GPU host. For HF Jobs, verify remote completion and
   finalize the downloaded checkpoint before attempting rollout.
3. Inspect rollout dry-run and checkpoint compatibility. Run one supervised,
   bounded episode with a clear stop path and manually reset the scene.
4. Open that exact run in the frontend. Confirm playable camera evidence,
   matching trace timing, and requested versus sent commands. Capture failures
   must retain diagnostics and must not be presented as synchronized evidence.
5. Label the outcome and failure category in the frontend. Confirm the reviewed
   metric includes it and provisional episodes remain excluded.
6. Collect demonstrations targeting the observed failure, train a second
   checkpoint, repeat the same protocol, and compare reviewed outcomes.

## Results

Physical attempts: **0**. No dataset, trained-policy quality, success rate, or
hardware timing result is claimed. Software tests use synthetic observations,
mock devices, a locally generated ACT checkpoint, and a single CPU optimizer
step on a synthetic dataset; those checks establish compatibility, not task
performance. Append actual run IDs and evidence
locations only after the supervised protocol is performed.
