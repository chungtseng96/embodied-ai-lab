# Supervised LaundryBench ACT rollout

`scripts/run_policy.py` joins a local LeRobot ACT checkpoint to the LaundryBench
physical episode lifecycle. The default invocation is a dry run: it validates
the YAML, checkpoint files, saved processors, training contract and camera
dimensions without importing Torch, loading ACT, or connecting to the robot.
Physical execution requires both `--execute` and `--supervised`.
Before connecting the follower, execution checks the saved contract and
processor digests, local checkpoint, finite runtime, dataset/control cadence,
camera dimensions, output parent, `ffmpeg`, and NumPy.

## Reproduce a bounded rollout

Create a private copy of `projects/laundrybench/configs/rollout.example.yaml`
and set the local checkpoint, contract, dataset revision, task/protocol IDs,
existing follower port and calibration ID, camera profile, output path, and
runtime limits. The example is capped at ten episodes, 30 Hz, and 120 seconds
per episode; use a smaller initial protocol. A positive LeRobot
`max_relative_target` is required. It limits each command's position delta and
is capped at five normalized position units per command (`1.0` is one
normalized SO-101 unit, not one degree, because this adapter sets
`use_degrees=false`). It does not provide a velocity, collision, or
emergency-stop guarantee.

```bash
python projects/laundrybench/scripts/run_policy.py --help
python projects/laundrybench/scripts/run_policy.py --config /path/to/rollout.yaml
python projects/laundrybench/scripts/run_policy.py \
  --config /path/to/rollout.yaml --execute --supervised
```

The operator remains at the arm with a clear work area and physical stop
access. The runner never calibrates or homes the arm. The SO-101 adapter uses
`connect(calibrate=False)`, returns normalized joint coordinates with
canonical joint order, applies the configured per-command relative target
limit, and disconnects in every episode cleanup path. Disconnecting may release
torque; follow the hardware's physical safety procedure.

## Checkpoint contract

The local checkpoint must contain `config.json`, `model.safetensors`,
`policy_preprocessor.json`, `policy_postprocessor.json`, and
`policy_contract.json`. Contract schema 1 is emitted by the training worker and
binds SHA-256 digests for the ACT config, model weights, and both processors to
task/protocol and dataset revision, LeRobot
version, feature keys/shapes/dtypes, ordered six-joint state/action features,
camera RGB dimensions, and normalized coordinate bounds. The processor digests
include every referenced normalizer/unnormalizer state tensor file, with safe
in-checkpoint paths and no unbound extra state files. Joint feature names remain
as emitted in the contract. The adapter accepts only
the exact ordered LeRobot `shoulder_pan.pos` through `gripper.pos` list or the
exact canonical bare-name list and maps either to LaundryBench's canonical
order. The adapter refuses
unknown schema fields, missing artifacts, mismatched dimensions, or any model
feature set that disagrees with the contract. It does not infer joint order,
camera names, color order, or units from array length or file naming.

The ACT adapter is lazy: the module can be imported without Torch or LeRobot.
The implementation targets LeRobot 0.6.1's
`lerobot.policies.act.modeling_act.ACTPolicy.from_pretrained`,
`lerobot.policies.make_pre_post_processors`, `policy.reset()`,
`policy.select_action(batch)`, and saved policy processor files. It requires
the exact installed LeRobot version 0.6.1 and loads from a local directory
only. The upstream v0.6.1 release is signed at commit `7e241bd`; its ACT
processor builds batching, normalization and device placement pipelines. The
adapter converts each declared RGB HWC uint8 frame to explicit CHW float in
`[0,1]`, batches and normalizes it through the checkpoint's saved processor,
then postprocesses the action through the checkpoint's matching saved
postprocessor. Source: [LeRobot v0.6.1 release](https://github.com/huggingface/lerobot/releases/tag/v0.6.1),
[ACT policy processor](https://github.com/huggingface/lerobot/blob/v0.6.1/src/lerobot/policies/act/processor_act.py),
and [policy deployment docs](https://huggingface.co/docs/lerobot/v0.6.1/inference).

The output must be one finite action in the declared normalized SO-101 ranges:
body joints `[-100, 100]`, gripper `[0, 100]`. Invalid, non-finite, wrong-order,
or out-of-range outputs fail before `robot.apply()`.

## Physical evidence and review

Each rollout writes a LaundryBench run with `manifest.yaml`, `episodes.jsonl`,
`traces/steps.jsonl`, `traces/commands.jsonl`, `quality.json`, and
`experiment.json`. `commands.jsonl` stores requested targets separately from
the SO-101 adapter's sent targets, which may have been clipped by its per-command
relative bound. Camera streams use the fresh pre-action observations passed to
ACT at the dataset/control FPS. The runner refreshes observations after pacing
before each later policy call. Timestamps are host observation times, not
synchronized camera exposure times. Cadence gaps beyond the evidence tolerance
abort the capture. The dataset FPS and rollout `control_hz` must match exactly;
the runner does not silently resample action chunks. Context includes
the raw config hash, effective robot/camera/runtime configuration, task and
protocol IDs, dataset identity/revision, LeRobot version, checkpoint identity,
and checkpoint digest. The output directory must not already exist.

Physical task success cannot be inferred from joint/camera observations by this
adapter. Every episode is stored with `success: false`, `failure_category:
unspecified`, and no review label. These are provisional records; the UI's
human review labels determine reviewed-only metrics. A clean process exit or
completed motion is not evidence of task success.
Ctrl+C and SIGTERM enter cleanup: active capture is aborted and the robot is
stopped/disconnected. The operator retains physical emergency-stop access.

## Verification boundary

Offline fake policy/robot tests verify strict contract checks, HWC-to-CHW
conversion, batching through the injected processor, output joint order,
reset, failure propagation and guaranteed robot stop. They do not verify the
installed package environment, checkpoint quality, camera freshness, timing
synchronization, calibration, physical motion or laundry task success. No
physical robot, camera, training job, GPU inference, or checkpoint was run to
implement this adapter. Complete the supervised bring-up and physical
acceptance gates in `projects/laundrybench/docs/playbooks/so101-home-feedback-loop.md` before
describing a run as physically validated.
