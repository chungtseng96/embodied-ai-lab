---
name: so101-bringup
description: Prepare and validate SO-101 hardware bring-up, calibration, recording, and rollout workflows through LeRobot.
---

# SO-101 bring-up

Use this skill when the task concerns the physical SO-101, serial ports,
cameras, calibration, teleoperation, recording, replay, or rollout.

## Preparation order

1. Confirm the host and Python environment with `make host-check` and
   `make lerobot-check`.
2. Read the current LeRobot SO-101 documentation and inspect command help
   before connecting or moving hardware.
3. Detect serial ports and cameras without moving the arm.
4. Confirm the leader/follower identity, port, robot ID, camera mapping, and
   task configuration.
5. Calibrate each device using the documented LeRobot flow and preserve local
   calibration files outside the repository.
6. Teleoperate briefly with the operator present before recording a dataset.
7. Record a small, clearly labeled smoke-test dataset before a full collection
   run.
8. Inspect the dataset and record the command, configuration, software
   versions, and outcome in an experiment note.

## Safety and evidence

- Treat every movement command as a real-world side effect.
- Default to read-only discovery and command help until the task explicitly
  authorizes movement or recording.
- Stop if a port, device identity, camera mapping, or workspace is ambiguous.
- Keep emergency stop access clear and use conservative initial motion limits.
- Do not claim success from a CLI exit code alone; capture the dataset,
  episode count, logs, and a physical outcome.

## Canonical tools

Use LeRobot CLI commands for reproducible workflows. LeLab is an optional
operator UI for calibration, teleoperation, recording, training, replay, and
upload; document any UI-only action with the equivalent experiment metadata
when the action matters to a result.
