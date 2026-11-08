# EXP-003 — Physical feedback-loop acceptance

**Date:** 2026-11-02  
**Status:** Two-camera live teleoperation and software-rotated verification completed; neutral/direction/range/stop/reconnect validation, demonstration dataset, training, and policy rollout pending
**Hardware:** physical SO-101 follower/leader pair, mounted icSpring camera, and overhead HD Pro Webcam C920
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
environment. On Intel macOS, record the native edge lock-file revision and
`video_backend: pyav`; record the Linux/NVIDIA image source SHA for ACT
training. Keep datasets, calibration files, model weights, and videos out of git.

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

### 2026-11-03 — local hardware smoke

One supervised eight-second recording completed with return code `0` using
LeRobot `0.6.1` from the native Intel macOS edge environment. The exact local
run artifacts were written outside git to
`/tmp/laundrybench-so101-e2e-smoke-dataset` and
`/tmp/laundrybench-so101-e2e-smoke.recording.json`.

- follower: `/dev/cu.usbmodem5B790803161`, ID `laundrybench_follower`
- leader: `/dev/cu.usbmodem5B901027261`, ID `laundrybench_leader`
- camera: external `icSpring` device, OpenCV index `0`, acquisition
  `640x480 @ 30 FPS`, dataset `15 FPS`
- dataset: one episode, 120 state/action rows, 120 decoded camera frames,
  camera feature `observation.images.front` with shape `[480, 640, 3]`
- local dataset identity:
  `local-sha256:65a52d721737ebb0fc04d02a98ece9072bbbb63d3f3488774ab68774ed0f88f6`

This validates physical arm connection, calibrated teleoperation wiring,
camera acquisition, video encoding/decoding, dataset writing, and the ACT I/O
metadata contract. The leader action remained constant during this short
smoke, while follower state converged; no task success, trained-policy quality,
or policy rollout result is claimed. Training and the bounded rollout remain
the next acceptance steps.

### 2026-11-06 — mounted-camera end-to-end capture

After mounting the external `icSpring` camera to the arm, a fresh supervised
recording completed with return code `0` using the same calibrated SO-101 pair
and LeRobot `0.6.1`. The exact local run artifacts were written outside git to
`/tmp/laundrybench-mounted-camera-visible-e2e-dataset` and
`/tmp/laundrybench-mounted-camera-visible-e2e.recording.json`.

- follower: `/dev/cu.usbmodem5B790803161`, ID `laundrybench_follower`
- leader: `/dev/cu.usbmodem5B901027261`, ID `laundrybench_leader`
- camera: OpenCV index `0`, `640x480 @ 30 FPS` acquisition, dataset `15 FPS`
- dataset: one episode, 221 finite state/action rows, 221 decoded camera
  frames, camera feature `observation.images.front` with shape
  `[480, 640, 3]`
- local dataset identity:
  `local-sha256:316b214c5c6ff0e595950fd82c0f9c73e2452debca8e03d98a6c1aa6b7c05ada`
- frame inspection confirmed the mounted camera sees the gripper and work
  surface; the ACT I/O metadata contract passed

This validates the mounted-camera physical capture path, synchronized dataset
writing, and the fixed-pose follower loop. The leader action was stationary in
this run (the follower state only settled toward that target), so dynamic
leader teleoperation, task completion, training, and policy rollout are not
claimed by this evidence.

### 2026-11-07 — two-camera live teleoperation and Rerun observability

A bounded 60-second supervised LeRobot teleoperation session completed at
15 Hz with both physical arms and two USB cameras connected. The run used the
same calibrated device IDs and LeRobot `0.6.1`; the final session disconnected
the leader, cameras, and follower cleanly with no recorded runtime error.

- follower: `/dev/cu.usbmodem5B790803161`, ID `laundrybench_follower`
- leader: `/dev/cu.usbmodem5B901027261`, ID `laundrybench_leader`
- `front`: mounted `icSpring` camera, OpenCV index `1`, `640x480 @ 30 FPS`
- `third_person`: overhead `HD Pro Webcam C920`, OpenCV index `0`,
  `640x480 @ 30 FPS`; the captured pre-rotation view was inverted, and the
  versioned teleoperation config pins software rotation `180` for the follow-up
  upright Rerun run documented below
- display: Rerun, `observation.front` plus `observation.third_person`, with
  observation/action plots visible
- excluded devices: built-in FaceTime camera and iPhone camera
- evidence: operator screenshot and live process output retained outside git;
  no generated media or process log is committed

This validates the live leader/follower and two-camera observability path. It
does not claim task completion, dataset capture, ACT training, or policy
rollout. The third-person stream is operator-only and is not added to the
current one-camera dataset contract. Existing follower/leader calibration files
were reused; camera mounting and software image rotation are not, by
themselves, reasons to recalibrate.

### 2026-11-07 — software-rotated two-camera verification

A follow-up bounded 60-second supervised LeRobot teleoperation session used
the versioned software rotation with the same calibrated SO-101 pair and both
USB cameras. The iPhone and built-in FaceTime camera were not used. The Rerun
recording lasted `59.93` seconds.

- `observation.front` showed the live arm-mounted view.
- `observation.third_person` showed the overhead C920 with rotation `180`;
  the table text was upright/readable and the arm and leader were visible.
- Observation and action traces changed during the session.
- The leader and camera streams disconnected at the bounded-session end with
  no traceback, runtime error, or overload output; a subsequent read-only
  follower probe reached all six motors and closed the port without torque
  writes.
- The follower probe reported model `777` for all six motors, torque enable,
  load, current, and status `0`, and temperatures from `32` to `33` °C.

This closes the camera-orientation acceptance item. It does not claim task
completion, dataset quality, ACT training, or policy rollout. The next hardware
gate is a neutral-pose, direction, range, and stop/reconnect check before
recording two dynamic front-camera demonstrations.
