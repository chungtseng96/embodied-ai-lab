# SO-101 adapter contract

`laundrybench.robot.so101.SO101LeRobotRobot` implements LaundryBench's
`reset / observe / apply / stop` interface over a LeRobot SO-101 follower.
Initial device connection uses the explicit `create_so101_robot(...)` factory;
`reset()` reconnects a stopped session as described below. Importing this
module has no LeRobot dependency and performs no hardware I/O.
An injected follower must already be connected, calibrated and normalized.

## Mapping and units

- Observation keys are the six canonical joint names suffixed by `.pos`.
  Configured camera names select image entries directly, without copying or
  encoding frames. Missing camera/joint keys and non-finite joint readings fail.
- The factory explicitly selects `use_degrees=False`, independent of upstream
  defaults. Five body joints use normalized `[-100, 100]`; the gripper uses
  `[0, 100]`. These are calibrated coordinates, not radians or physical angles.
- Actions must have six finite numeric values and the exact canonical joint
  order. The adapter rejects out-of-range values; it never silently clips them.
- A positive `max_relative_target` is mandatory. LeRobot may further limit each
  commanded joint's displacement from its current position. This is a
  per-command position bound, not a velocity or collision-safety guarantee.
  `last_sent_action` retains LeRobot's returned, possibly clipped command.
  The existing runner's step trace records the requested action, not this
  returned command; executed-command evidence still needs explicit wiring.
- `Observation.timestamp_s` is host wall-clock time after acquisition, not
  hardware-synchronized joint/camera exposure time. Camera/state synchronization
  and freshness are not established by this adapter.

## Episode lifecycle

The factory accepts explicit follower port, robot ID, named camera indices or
paths, resolution/FPS and relative position limit. It calls
`connect(calibrate=False)` and rejects a follower without valid calibration.
Calibration must be performed separately with the supervised bring-up workflow.

`reset()` clears software episode counters; it does not home the arm or send a
position target. After `stop()`, the next `reset()` explicitly reconnects through
LeRobot with calibration disabled and checks calibration again. This supports
the existing evaluation runner's repeated `reset -> episode -> stop` lifecycle.
LeRobot connection can configure motor registers and torque; reconnection is a
hardware operation even though the adapter sends no motion target there.
The operator resets the physical scene and must supervise the session.

`stop()` disconnects once and propagates failures; a failed disconnect can be
retried. The factory selects `disable_torque_on_disconnect=True`: disconnecting
can release the arm. This is **not an emergency stop or a guaranteed position
hold**. Secure/support the arm and use the vendor's physical safety procedure.
On connection errors, the adapter attempts a disconnect and preserves the
original error with any cleanup failure attached as a note. Partial upstream
connection failures may require operator cleanup; no successful teardown is
claimed from that best-effort attempt.

## Compatibility and verification

The lazy factory tries the current `lerobot.robots.so_follower` SO101 aliases,
then the legacy `lerobot.robots.so101_follower` module only if the current module
itself is missing. Missing transitive dependencies are not hidden by fallback.
Cameras use `lerobot.cameras.opencv.OpenCVCameraConfig` with RGB defaults.

Reviewed official upstream source, 2026-11-01:

- [SO follower implementation](https://github.com/huggingface/lerobot/blob/326484d77d2ac90379e84222dfad21fe4acf1f71/src/lerobot/robots/so_follower/so_follower.py)
- [Follower config](https://github.com/huggingface/lerobot/blob/326484d77d2ac90379e84222dfad21fe4acf1f71/src/lerobot/robots/so_follower/config_so_follower.py)
- [OpenCV camera config](https://github.com/huggingface/lerobot/blob/326484d77d2ac90379e84222dfad21fe4acf1f71/src/lerobot/cameras/opencv/configuration_opencv.py)

Offline fake-follower tests cover mapping, lifecycle across two runner episodes,
validation before side effects, clipping evidence, cleanup, and modern/legacy
factory import shapes. They establish our adapter contract, **not compatibility
with an installed LeRobot build or physical hardware readiness**. The exact
edge-host LeRobot version, calibration and camera behavior must be verified on
the supervised host before a physical rollout. No hardware commands were run
as part of implementing this adapter.
