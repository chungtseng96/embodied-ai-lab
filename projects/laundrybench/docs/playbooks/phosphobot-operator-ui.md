# Phosphobot operator UI

**Status:** installed locally; physical connection remains operator-validated

Phosphobot is the convenient operator surface for this home setup. It is not a
native macOS desktop application: the Homebrew binary runs a local service and
the control panel opens in a browser. LaundryBench keeps its versioned
LeRobot/Rerun commands as the reproducible experiment path and uses this UI to
reduce operator friction during bring-up, calibration, teleoperation, and
recording.

## Start it

From the repository root:

```bash
make operator-ui
```

This uses the locally installed `phosphobot` binary with these defaults:

- bind to `127.0.0.1:8020` only;
- scan OpenCV camera indexes `0` and `1` only;
- disable CAN and RealSense discovery for this SO-101 setup;
- disable Phosphobot telemetry;
- open the dashboard at <http://127.0.0.1:8020>.

The equivalent dry-run, which does not start a service or touch hardware, is:

```bash
python3 projects/laundrybench/scripts/run_operator_ui.py --dry-run
```

The Homebrew installation can be recreated with:

```bash
brew tap phospho-app/phosphobot
brew install phosphobot
```

## Current hardware mapping

When both arms are attached, Phosphobot auto-discovers the SO-101-class
Feetech buses. In its Control → Leader arm page, select:

- leader: `/dev/cu.usbmodem5B901027261` (`laundrybench_leader`);
- follower: `/dev/cu.usbmodem5B790803161` (`laundrybench_follower`).

The device paths can change after reconnecting. Confirm the displayed serial
path and arm role before pressing Start Control. Keep the workspace clear, keep
the physical stop accessible, and begin with small movements. Connecting or
viewing status is not a motion test; Start Control is.

The UI's Calibration page stores Phosphobot calibration under its own app
directory. It does not replace the LeRobot files used by LaundryBench:

```text
~/.cache/huggingface/lerobot/calibration/robots/so_follower/
~/.cache/huggingface/lerobot/calibration/teleoperators/so_leader/
```

Do not treat a Phosphobot calibration as proof that the LaundryBench LeRobot
calibration or ACT contract is valid. Record any UI calibration separately and
rerun the canonical LeRobot checks before recording or evaluating data.

## Cameras

The launcher intentionally searches only indexes `0` and `1`, matching the
validated setup:

- index `1`: mounted `icSpring` front/policy camera;
- index `0`: overhead HD Pro Webcam C920 third-person camera.

The launcher bounds discovery to indexes `0` and `1`, which matched the two
external cameras during the validated e2e run. Phosphobot's generic macOS
scanner does not filter devices by name, so this bound is not a substitute for
checking the thumbnails. With the built-in FaceTime or iPhone camera present,
macOS can reorder indexes after reconnects. Verify that index `1` is `icSpring`
and index `0` is the C920 before using them; do not widen discovery blindly or
select the iPhone. The canonical LaundryBench teleoperation config remains the
source of truth for the named `front`/`third_person` streams and the software
rotation of the overhead view.

## Boundary with LaundryBench evaluation

Use Phosphobot for the operator-facing connection, camera preview, calibration
workflow, and supervised leader/follower control. Use LaundryBench's checked-in
configs and scripts for:

- contract-bound demonstration recording;
- dataset identity and ACT training inputs;
- policy rollout and evaluation evidence;
- Rerun traces and the review frontend.

Do not call a dashboard connection, preview, or synthetic Phosphobot session a
physical task evaluation. A physical acceptance record still needs the exact
ports, IDs, cameras, command, logs, dataset/checkpoint, and human-reviewed
outcome described in the SO-101 home feedback-loop guide.
