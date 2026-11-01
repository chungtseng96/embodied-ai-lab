# SO-101 Home Feedback Loop

**Purpose:** bring your already-calibrated SO-101 and installed LeRobot environment through a safe first home session, then run repeatable demonstrations, ACT training, rollout, evidence review, and targeted iteration without confusing native LeRobot artifacts with LaundryBench runs.

**Current capability in one sentence:** LaundryBench's mock evaluation, manual-review UI, reviewed-only metrics, comparisons, and synthetic showcase work today; direct LeRobot can record and train on hardware independently, but LaundryBench's `record.py`, `train.py`, and `run_policy.py` are fail-fast stubs and there is no ACT policy bridge or physical episode import path yet.

## Read this before the commands

There are two usable workflows, with an integration gap between them:

| Workflow | Works now | Does not mean |
|---|---|---|
| LaundryBench software loop | `make demo`, `make web-demo`, UI labels, CLI/HTML summary, mock comparisons | Physical behavior, data collection, a trained checkpoint, or robot performance |
| Native LeRobot loop | SO-101 teleoperation/recording, ACT train CLI, and policy rollout if the installed LeRobot build has compatible commands/dependencies and you supervise hardware | A LaundryBench run, manual-review record, LaundryBench metrics, or physical ACT integration |
| Joined physical LaundryBench loop | Blocked until the physical acceptance/integration gates below are implemented and verified | Do not bridge the gap by labeling a mock run as physical or attaching unrelated footage to it |

The current LaundryBench configs deliberately set `robot.implementation: mock`, null serial ports, and `camera.implementation: mock`. `scripts/evaluate.py` always instantiates `MockRobot` and `MockPolicy` (or a faulty mock). `projects/laundrybench/scripts/record.py`, `train.py`, and `run_policy.py` exit with “not wired yet.” An offline-tested SO-101 adapter exists in `src/laundrybench/robot/so101.py`, but it is not a physical evaluator or ACT policy adapter. Native LeRobot datasets and rollout evidence do not automatically become LaundryBench `manifest.yaml` / `episodes.jsonl` / `traces/steps.jsonl` runs.

## Start from the right checkout

If the repository is already checked out, use that checkout and inspect its branch and changes before updating anything:

```bash
cd "/path/to/embodied-ai-lab"
git status --short --branch
git rev-parse --short HEAD
```

Do not discard local changes. Only fast-forward an existing clean checkout when you deliberately want the remote's current branch:

```bash
git status --short
# Continue only if this output is empty and the branch is the one you intend to update.
git pull --ff-only
```

For a fresh clone, use a new path so an existing checkout is untouched:

```bash
git clone https://github.com/chungtseng96/embodied-ai-lab.git \
  "$HOME/embodied-ai-lab-home"
cd "$HOME/embodied-ai-lab-home"
```

The remaining repository commands assume the current directory is this repository root. Do not clone over an existing directory.

Do not recalibrate by default: the arms are already calibrated. Reuse the exact calibration IDs already on disk for each arm. If a tool unexpectedly offers calibration, stop and resolve the ID/environment mismatch before continuing; do not accept an unplanned recalibration prompt.

Hardware commands in this guide have an explicit **MOVES / RECORDS** marker. Read the current LeRobot command's `--help` and confirm the exact ports, IDs, camera mapping, clear workspace, physical stop access, and operator before running one. This guide contains commands but has not run any hardware action.

## First evening: the one-page checkpoint

Use this to stop at a useful checkpoint rather than assuming one evening includes cloud training and policy deployment.

- [ ] Record exact laptop OS/CPU, Python, LeRobot, PyTorch, command paths, and `--help` outputs.
- [ ] Run LaundryBench `make host-check PYTHON="$LB_PYTHON"` from its dedicated environment, `make lerobot-check PYTHON="$(command -v python)"` from the activated LeRobot environment, and the mock UI loop in an isolated temporary output directory.
- [ ] Identify which physical arm is the **leader** and which is the **follower**; map both different serial ports and calibration IDs. If you do not have the leader arm or another calibrated control device, stop before teleoperation/recording: follower-only control is not enough for the demonstrated native recording command.
- [ ] Enumerate the external camera without moving the robot; record index/path, supported resolution/FPS, and a fresh test frame. Put the camera above the table with the full object and destination visible.
- [ ] Verify LeRobot IDs match existing calibration files; verify each port is stable; verify the chosen `front` camera key, index, resolution, and FPS can be opened. Do not run calibration.
- [ ] With a clear work area and operator present, perform a brief, bounded **leader-driven teleoperation check** only after confirming roles, ports, IDs, and stop method. Stop at once if direction, tracking, or camera image is unexpected.
- [ ] If teleoperation and camera pass, record only 2-3 labeled smoke demonstrations to a new local-only dataset. Inspect each episode before deciding whether to collect more.
- [ ] Finish by writing down exact port/ID/camera/task values, versions, dataset path/ID, episode count, visible failures, and next blocker. Leave ACT cloud training and autonomous ACT rollout for a later scheduled session.

## Phase 0 — establish the two environments

Run from the repository root. Keep the LaundryBench developer environment separate from the LeRobot environment you already installed. Do not create or install into `.venv` or `.venv-lerobot`. The example below stops if its dedicated path already exists; choose a different unused path, or inspect the existing environment and explicitly update `LB_ENV` after confirming it is the LaundryBench environment. Python 3.11 or newer is required for this project setup.

```bash
# Dedicated project environment; refuse to modify an existing environment.
LB_ENV="$HOME/.venvs/laundrybench-review"
if [ -e "$LB_ENV" ]; then
  echo "Refusing to reuse existing path: $LB_ENV. Inspect it or choose a new unused LB_ENV path." >&2
  exit 1
elif ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "Python 3.11 or newer is required; python3 is $(python3 --version 2>&1). Install/select a newer python3 and rerun." >&2
  exit 1
else
  mkdir -p "$HOME/.venvs"
  python3 -m venv "$LB_ENV"
  LB_PYTHON="$LB_ENV/bin/python"
  "$LB_PYTHON" --version
  "$LB_PYTHON" -m pip install -e "projects/laundrybench[dev]"
  make host-check PYTHON="$LB_PYTHON"
  make check PYTHON="$LB_PYTHON"
  make frontend-install
  make frontend-check
fi
```

Use the activation command or Python executable for your existing LeRobot environment separately; its location is machine-specific. The readiness note records `.venv-lerobot` and LeRobot 0.6.1 for one prior host state, but that is not proof it exists on this machine. Activate the actual LeRobot environment before checking its version or using its CLIs:

```bash
source "/absolute/path/to/your/lerobot-env/bin/activate"
python - <<'PY'
import importlib.metadata, platform, sys
print("python", sys.version)
print("platform", platform.platform(), platform.machine())
print("lerobot", importlib.metadata.version("lerobot"))
try:
    import torch
    print("torch", torch.__version__)
    print("cuda available", torch.cuda.is_available())
    print("mps available", getattr(torch.backends, "mps", None) and torch.backends.mps.is_available())
except Exception as exc:
    print("torch check failed:", repr(exc))
PY

command -v lerobot-record
command -v lerobot-train
command -v lerobot-rollout
lerobot-record --help > /tmp/lerobot-record-help.txt
lerobot-train --help > /tmp/lerobot-train-help.txt
lerobot-rollout --help > /tmp/lerobot-rollout-help.txt
lerobot-find-port --help > /tmp/lerobot-find-port-help.txt
lerobot-find-cameras --help > /tmp/lerobot-find-cameras-help.txt
```

If the version or command path is missing, activate the environment where LeRobot was installed instead of installing a second version over it. If `--help` fails because an optional dependency is missing, fix the environment before connecting the arms. New LeRobot releases move optional capabilities into install extras; the official installation guide maps robot scripts to `core_scripts`, model training to `training`, cameras/video to their required extras, and SO-101 motor support to Feetech. Do not assume `pip install lerobot` alone supplied all hardware and training extras.

Record the `lerobot` package version and command help text with the experiment note. Some CLI options change between releases. The templates below follow the Hugging Face LeRobot v0.6.1 CLI documentation; the installed command's `--help` wins. If a flag is absent, do not copy it anyway.

The LaundryBench environment is distinct from the LeRobot environment. Python 3.11+ is sufficient for the repository; its LeRobot check requires Python 3.12+. The repo's host check reports optional laptop prerequisites but does not verify a physical arm. For LeRobot-side host reporting, after activating that separate environment, run `make host-check PYTHON="$(command -v python)"` and `make lerobot-check PYTHON="$(command -v python)"` from the repository root.

## Phase 1 — run the LaundryBench mock feedback loop

Keep generated evidence outside the checkout. `make demo` writes a fixed run under `projects/laundrybench/outputs` and includes `--force`; do not run it over a run you want to preserve. For a manual review session, use an isolated directory:

```bash
LB_PYTHON="$HOME/.venvs/laundrybench-review/bin/python"
mkdir -p /tmp/laundrybench-ui-demo
"$LB_PYTHON" projects/laundrybench/scripts/demo_web.py \
  --output-dir /tmp/laundrybench-ui-demo
```

In terminal A, serve those same artifacts with the built frontend:

```bash
LB_PYTHON="$HOME/.venvs/laundrybench-review/bin/python"
"$LB_PYTHON" projects/laundrybench/scripts/serve.py \
  --outputs-root /tmp/laundrybench-ui-demo \
  --frontend-dir projects/laundrybench/frontend/dist
```

Open `http://127.0.0.1:8765`. Choose `exp-900-mock-baseline` or `exp-901-mock-candidate`, open episodes, and save a review label. The demo runs start with pending, unreviewed episodes; saving a review in the UI writes `labels.json`. The candidate/baseline difference is synthetic and does not represent training. A label is an after-the-episode outcome record, not an action annotation or robot command.

In terminal B, after saving labels, build a CLI/HTML report from the same run folders:

```bash
LB_PYTHON="$HOME/.venvs/laundrybench-review/bin/python"
"$LB_PYTHON" projects/laundrybench/scripts/report.py \
  --experiment-dir /tmp/laundrybench-ui-demo/exp-901-mock-candidate \
  --baseline /tmp/laundrybench-ui-demo/exp-900-mock-baseline
```

The report writes `summary.json` and `report.html` into the candidate folder. Compare `summary.json`'s `success_rate`, `reviewed_episodes`, `pending_episodes`, `excluded_episodes`, `failure_category_counts`, and `label_revision` with the UI. Both are calculated from the same `episodes.jsonl` plus `labels.json`. If no episodes are reviewed, the rate is unavailable (`null`/—), not 0%. The app returns HTTP 409 when a stale browser tab attempts a label write; reload the run, confirm the label still needs review, then reapply it. Do not force-overwrite the file.

If the UI is not built yet, `make frontend-install` then `make frontend-check` is the repo-supported build/check path. The local operator UI is the path for editable post-episode labels.

**Checkpoint:** two `exp-900/901` folders in `/tmp/laundrybench-ui-demo`, each marked mock/synthetic; browser can save a label; CLI report updates its reviewed-only rate and `label_revision`. This proves the software review loop, not physical metrics.

## Phase 2 — prepare ports, cameras, and identities without movement

In any new terminal used for LeRobot commands, activate the same existing LeRobot environment from Phase 0 and check `command -v lerobot-record` / `command -v lerobot-rollout` before proceeding. Do not run LeRobot CLIs from the separate LaundryBench environment unless they are intentionally installed there.

### Map both arm roles

- **Follower:** the powered arm that moves on the table. In LeRobot flags this is `--robot.type=so101_follower` and `--robot.port=FOLLOWER_PORT`.
- **Leader:** the hand-guided control arm that provides demonstration actions. In flags this is `--teleop.type=so101_leader` and `--teleop.port=LEADER_PORT`.

LeRobot needs both arms and each arm's own ID for leader/follower teleoperation and native demonstration recording. Never put the follower port or ID in both roles. If there is only a follower and no leader/other configured teleoperator, do not claim that you can record demonstrations with this command. Identify which arm is which by physical labels and use LeRobot's interactive port finder as documented; if the port mapping remains ambiguous, stop.

Read-only serial discovery depends on OS:

```bash
# macOS: serial device paths often contain usbmodem or usbserial.
ls /dev/cu.usb* /dev/tty.usb* 2>/dev/null || true

# Linux: prefer persistent by-id names when present.
ls -l /dev/serial/by-id /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || true
```

The LeRobot `lerobot-find-port` utility may ask you to unplug one USB cable and press Enter, then prints that arm's port. Repeat one arm at a time. This is read-only device discovery; it does not move the robot. On Linux, if access is denied, inspect `ls -l /dev/ttyACM*` and `id -nG`; the device group is commonly `dialout`. Have an administrator add your account to the correct serial-device group, then log out/in before retrying. Do not solve this by running robot processes as root. On macOS, use `/dev/cu.*` for serial connections and check that a data-capable cable/USB hub is actually enumerated. Do not assume ports remain the same after unplugging/reboot.

Set shell variables to the exact observed values; these are intentionally conspicuous placeholders:

```bash
# Replace every placeholder before a hardware command. Keep values in a local note,
# not in git. The two port values must be different.
FOLLOWER_PORT="<observed follower /dev/cu.usbmodem... or /dev/ttyACM...>"
LEADER_PORT="<observed leader /dev/cu.usbmodem... or /dev/ttyACM...>"
FOLLOWER_ID="<exact ID used when this follower was calibrated>"
LEADER_ID="<exact ID used when this leader was calibrated>"
```

Find calibration files by filename in the LeRobot cache (never commit them):

```bash
find "$HOME/.cache/huggingface/lerobot/calibration" \
  -type f \( -path '*/robots/so_follower/*.json' \
  -o -path '*/teleoperators/so_leader/*.json' \) -print 2>/dev/null
```

The usual v0.6.1-style locations are `~/.cache/huggingface/lerobot/calibration/robots/so_follower/<ID>.json` and `.../teleoperators/so_leader/<ID>.json`; installations may set `HF_LEROBOT_HOME` or otherwise relocate cache data. If those files or IDs are not available, inspect the installed version's docs and environment, not by recalibrating on guesswork. Back up the calibration directory outside git before future maintenance.

### Enumerate the camera

Connect only the intended overhead USB camera first. On macOS, camera indices typically come from AVFoundation; on Linux they may be `/dev/video*`. LeRobot v0.6.1's camera guide uses `lerobot-find-cameras opencv`; run the captured `lerobot-find-cameras --help` first and follow the installed command if its syntax differs. The finder reports IDs and profiles and saves test frames, so run it from a disposable working directory rather than the repository:

```bash
mkdir -p /tmp/lerobot-camera-probe
cd /tmp/lerobot-camera-probe
lerobot-find-cameras opencv
```

Record the chosen camera index/path, output profile, and observed FPS. Start with a profile the camera actually reports, for example 640 x 480 at 15 FPS if supported; do not request 1920 x 1080/30 merely because a YAML file says so. Keep the same named camera slot (`front`), index/path, dimensions, and FPS for record, dataset inspection, training and rollout. A policy trained with one camera feature layout/resolution may reject or misread a different rollout layout.

Use local environment discovery to write down the exact fields, but do not modify the repository's mock configuration as if it were a physical config:

| Field | Value to record |
|---|---|
| Follower serial path | Exact OS path from discovery |
| Follower ID | Existing calibrated ID |
| Leader serial path | Exact OS path from discovery |
| Leader ID | Existing calibrated ID |
| Camera feature key | `front` (use one stable name) |
| Camera index/path | Exact enumerated device ID |
| Resolution/FPS | A supported profile verified live |
| LeRobot version | `python -c ...` output from the active LeRobot environment |
| LaundryBench revision | `git rev-parse HEAD` plus uncommitted changes noted |

**Checkpoint:** both physical arms identified separately, both matching calibration IDs found, permissions allow non-root serial access, and the camera finder sees a live stream at the selected profile. No motion has occurred.

## Phase 3 — supervised teleoperation and smoke demonstrations

Before a motion command: clear the table/workspace; keep the leader, follower, and cable paths clear; keep the physical power disconnect accessible; make sure the operator is beside the follower; confirm no person or loose object can enter the arm's sweep; use light fabric only. Do not change the camera, calibration IDs, or arm roles between teleoperation, demonstration capture, and eventual rollout.

**MOVES THE FOLLOWER (leader teleoperation):** this is the first commanded motion. Confirm the ports and IDs are exact before running. LeRobot may prompt about calibration if it cannot find the existing ID; choose to stop and diagnose, not to recalibrate.

```bash
lerobot-teleoperate \
  --robot.type=so101_follower \
  --robot.port="$FOLLOWER_PORT" \
  --robot.id="$FOLLOWER_ID" \
  --robot.cameras="{ front: {type: opencv, index_or_path: <CAMERA_INDEX>, width: 640, height: 480, fps: 15} }" \
  --teleop.type=so101_leader \
  --teleop.port="$LEADER_PORT" \
  --teleop.id="$LEADER_ID" \
  --display_data=true
```

Replace `<CAMERA_INDEX>` with the integer or path returned by discovery, and dimensions/FPS with the actual supported profile. `--display_data` availability and requirements are version-dependent; omit it only if the installed command help says it is not supported or Rerun is not installed. Use the stop key documented by this installed command. Keep the first check brief. Confirm the follower mirrors leader motion in the expected direction, the gripper works, and displayed frames change. Stop if follower lags, moves unexpectedly, approaches a collision, or camera output freezes.

For the first recording, create a new local dataset ID; keep uploads off. Use a short single task and only 2-3 episodes. **RECORDS PHYSICAL DEMONSTRATIONS and lets the leader move the follower.** The keyboard save/retry/stop behavior below is from LeRobot's v0.6.1 cheat sheet; verify in installed `lerobot-record --help` before beginning.

```bash
DATASET_ID="<HF_USERNAME>/laundrybench_sock_smoke_YYYYMMDD"

lerobot-record \
  --robot.type=so101_follower \
  --robot.port="$FOLLOWER_PORT" \
  --robot.id="$FOLLOWER_ID" \
  --robot.cameras="{ front: {type: opencv, index_or_path: <CAMERA_INDEX>, width: 640, height: 480, fps: 15} }" \
  --teleop.type=so101_leader \
  --teleop.port="$LEADER_PORT" \
  --teleop.id="$LEADER_ID" \
  --dataset.repo_id="$DATASET_ID" \
  --dataset.num_episodes=3 \
  --dataset.single_task="pick up the sock and place it in the sock basket" \
  --dataset.push_to_hub=false \
  --display_data=true
```

Use LeRobot's key flow from installed help: save a complete attempt, discard/retry a broken capture, or exit cleanly so video encodes. Capture the final dataset repo ID/path printed at completion; LeRobot versions may append a timestamp. Replace the recording base ID in your shell with the exact final identity before visualization, upload, or training; never assume the base ID survived timestamping:

```bash
DATASET_ID="<PASTE THE EXACT FINAL DATASET REPO ID PRINTED BY lerobot-record>"
```

On macOS, if the global keyboard listener is unavailable, LeRobot v0.6.1 accepts the same `n` / `r` / `q` controls in the focused interactive terminal; keep that terminal focused. Do not save a partial/ambiguous episode just to hit the count. The local cache is typically under `~/.cache/huggingface/lerobot/<username>/<dataset-name>`; when exact dataset path is unclear, inspect the command's completion output and run `find "$HOME/.cache/huggingface/lerobot" -maxdepth 4 -type d -name "laundrybench_sock_smoke*" -print`.

Inspect the actual dataset with the installed `lerobot-dataset-viz --help` then, if that flag set is supported:

```bash
lerobot-dataset-viz \
  --repo-id "$DATASET_ID" \
  --root "$HOME/.cache/huggingface/lerobot" \
  --mode local \
  --episode-index 0
```

Use the LeRobot dataset viewer to inspect camera view, state, actions, episode duration and task text together. If your version stores the dataset elsewhere, point `--root` to its parent as the installed help documents. Reject a smoke set with blank/frozen video, wrong feature names, incomplete clips, wrong task labels, state/action discontinuities from incorrect teleoperation, or mismatched episode counts. Do not proceed to ACT until this checkpoint is good.

**Expected artifact:** a new local LeRobot dataset with metadata, episode data and encoded video; it remains native LeRobot data. Do not expect LaundryBench's `manifest.yaml`, `episodes.jsonl`, or run UI to ingest it automatically.

## Phase 4 — collect and train ACT (cloud GPU path)

Do not plan to train a meaningful ACT model on an Intel Mac. Use a Linux NVIDIA CUDA host or a managed GPU job, separately from the robot edge machine. A common pattern: keep the robot laptop connected to hardware, collect and save dataset locally; upload the chosen dataset to a private Hugging Face dataset repository (or copy to a controlled cloud VM), then start the training environment there. Confirm data privacy and Hub permissions before any upload; never paste tokens into shell history or commit them.

For local Linux CUDA, confirm `nvidia-smi` and in the LeRobot environment verify `torch.cuda.is_available()` is true. The latest official installation docs prescribe Python >=3.12; the v0.6.1 docs and project readiness note make clear that the older Intel-macOS setup is not the CUDA training target. If local cloud host doesn't have the right LeRobot `training` extra, install/pin there per the official installation guide, then re-capture version and help.

The shortest explicit cloud route is a Hugging Face Job from the machine with the local dataset. It sends a local-only dataset to a **private** Hub dataset repo for the job; the training result goes to a model repo. This is pay-as-you-go cloud compute. Check `hf jobs hardware` and current pricing, use an account authorized for private dataset/model access, and authenticate with the interactive login command below. Never turn on `--dataset.push_to_hub` for a public dataset or expose private video accidentally. The v0.6.1 docs show `a10g-small` as an example flavor; verify it and all flags in installed help before starting a billable job.

```bash
# Use an interactive login; do not put the access token in this file or shell history.
hf auth login
hf jobs hardware

HF_USER="<YOUR_HF_USERNAME>"
DATASET_ID="<PASTE THE EXACT FINAL DATASET REPO ID PRINTED BY lerobot-record>"
POLICY_ID="$HF_USER/act_laundrybench_YYYYMMDD"

# Managed cloud GPU. The local-only dataset is uploaded privately by the job.
lerobot-train \
  --dataset.repo_id="$DATASET_ID" \
  --policy.type=act \
  --policy.repo_id="$POLICY_ID" \
  --policy.private=true \
  --job.target=a10g-small \
  --steps=20000
```

This is the direct LeRobot CLI, not LaundryBench's stub `train.py`. Check the job logs and model repo for a finished checkpoint, exact training config, and source dataset identity. If you choose your own Linux NVIDIA host instead, first make the exact dataset revision available to that host (controlled file transfer into LeRobot's dataset root, or an intentionally private Hub dataset). Verify `nvidia-smi`, confirm `torch.cuda.is_available()` in that host's LeRobot environment, install/pin LeRobot's `training` extra for that version, and use a local-only checkpoint output:

```bash
lerobot-train \
  --dataset.repo_id="<EXACT_FINAL_DATASET_REPO_ID>" \
  --policy.type=act \
  --output_dir="outputs/train/act_laundrybench_YYYYMMDD" \
  --job_name="act_laundrybench_YYYYMMDD" \
  --policy.device=cuda \
  --policy.push_to_hub=false \
  --steps=20000
```

Verify `--policy.push_to_hub=false` and dataset-root options in that environment's `--help`; omit `--policy.repo_id` when you want local-only checkpoints. To intentionally publish a model, use a private repo and `--policy.private=true` only after confirming visibility. Do not run the GPU training command on the robot laptop unless that laptop actually has a supported CUDA-capable NVIDIA GPU.

For meaningful performance iteration, a few smoke episodes are not enough. Collect a larger, consistent demonstration set after reviewing the smoke set (HF currently recommends ACT as a good first policy and says 50 demonstrations can be effective, but task complexity and demonstration quality matter). Freeze the task, workspace, camera placement, and episode protocol. Keep a held-out evaluation split or at least a fixed physical attempt protocol; never train on the outcomes you call a held-out test. Copy the exact dataset repo ID/revision, training command, LeRobot/PyTorch/CUDA versions, GPU type, seed, and checkpoint path/ID into the experiment note.

**Training checkpoint:** the output folder contains the final/last pretrained checkpoint and `train_config.json` (path structure depends on version), loss/logs are finite, the train command exited successfully, and the checkpoint's dataset, camera feature names, joint feature order/units, pre/postprocessors and policy config are saved. A zero exit status without checkpoint artifacts is not a pass. Preserve the checkpoint and logs outside git.

## Phase 5 — evaluate a native LeRobot checkpoint under operator control

LaundryBench `scripts/run_policy.py` is not the policy runner. A native LeRobot rollout can test a policy on the arm, but it remains outside LaundryBench's outcome/evidence lifecycle. Begin only after the dataset and checkpoint passed inspection, all physical issues below are understood, and the operator explicitly confirms this bounded physical action.

Version v0.6.1's `lerobot-rollout` supports `--strategy.type=base` for bounded policy execution without recording. Use the installed help and exact camera and IDs from the dataset. A first rollout should be short (`--duration=10` or similarly conservative) and supervised. `--duration=0` means run indefinitely in current docs: do not omit duration and do not use zero. Confirm an immediate local stop method and reachable physical power disconnect before start.

**EXECUTES A TRAINED POLICY ON THE PHYSICAL FOLLOWER.** This is an operator command, not a dry run. Run it only after the preflight checklist and exact installed-version help are satisfied.

```bash
lerobot-rollout \
  --strategy.type=base \
  --policy.path="<LOCAL_CHECKPOINT_OR_HF_POLICY_ID>" \
  --robot.type=so101_follower \
  --robot.port="$FOLLOWER_PORT" \
  --robot.id="$FOLLOWER_ID" \
  --robot.cameras="{ front: {type: opencv, index_or_path: <CAMERA_INDEX>, width: 640, height: 480, fps: 15} }" \
  --task="pick up the sock and place it in the sock basket" \
  --duration=10 \
  --display_data=true
```

The native base rollout does not save an evaluation dataset. If the installed v0.6.1 rollout help includes `--strategy.type=episodic`, that strategy can record bounded evaluation episodes to a **new** native evaluation dataset; check its exact supported options, reset behavior, episode count/duration, push-to-Hub defaults, and stop keys before using it. Do not accidentally push evaluation footage publicly. LeRobot's v0.6.1 inference docs state the `episodic` strategy records each policy-driven episode and uses keyboard controls to stop/discard episodes. A policy rollout that runs cleanly is not a successful task result; the operator still observes each attempt and notes its actual outcome.

**Native evaluation evidence:** save the evaluation dataset/run path, checkpoint identity, task/protocol version, date/operator, exact command/version, each episode's ground-truth outcome, intervention, failure mode, and notes. LeRobot's dataset viewer is currently the supported native inspection path. If you run `lerobot-rollout` with `base`, keep an external attempt sheet because there is no recorded evaluation dataset.

## Phase 6 — what is and is not joined to LaundryBench

Current LaundryBench run layout is `manifest.yaml`, `episodes.jsonl`, `traces/steps.jsonl`, optional `quality.json`, `experiment.json`, label sidecar `labels.json`, and optional per-episode `media/<episode_id>/media.json` + video. Its frontend persists post-episode labels and recalculates reviewed-only metrics from the run. The media importer requires an already-existing LaundryBench episode and explicit `duration_s` plus absolute host-clock `trace_start_s`. It copies MP4/WebM only; it does not open camera streams, convert LeRobot state/action tables, create episodes, create LaundryBench traces, or measure physical clock synchronization. Therefore it cannot currently connect a native LeRobot rollout to the UI. Do not attach a physical video clip to an unrelated mock episode.

**Physical integration gates tracked in Linear:**

| Issue | Remaining gate | Why the home loop stops short |
|---|---|---|
| JWA-26 | Verify the offline SO-101 adapter against the calibrated hardware and installed LeRobot version; inspect state/frames, disconnect/reconnect and bounded motion | Offline fake-follower tests are not physical compatibility validation |
| JWA-16 | Wire `scripts/record.py` as a guarded LeRobot recording wrapper with explicit ports/IDs/settings | The file currently fails fast; native recording is direct LeRobot only |
| JWA-17 | Wire a reproducible `train.py` CLI/config and CUDA training container/job | The file currently fails fast; train directly with LeRobot on a Linux NVIDIA host until implemented |
| JWA-23 | Load an ACT checkpoint through a LaundryBench policy adapter and bounded physical evaluation, with guaranteed stop and provenance | Current `run_policy.py` is a stub; no ACT `Policy.reset()/act()` bridge exists |
| JWA-14 | Connect physical episode completion/pending review to the frontend label lifecycle | The UI can review current LaundryBench runs, but native LeRobot episodes are not LaundryBench runs |
| JWA-28 | Validate real robot/camera media and physical trace/video alignment with recorded event evidence | Software timing fixtures and imported media do not prove synchronized physical evidence |

The issue sequence is not automatically sequential in all parts; JWA-23 depends on the SO-101 adapter and a trained checkpoint. Track gates and evidence in an experiment note. **Do not manufacture a `manifest.yaml`, `episodes.jsonl`, `traces/steps.jsonl`, metrics, or media clock offset from native files by hand to make the UI look integrated.** The correct integration is a tested adapter/importer with schema/version checks and provenance.

Once the missing connector is implemented, the intended loop is:

1. Record reviewed demonstrations and freeze dataset revision, task, workspace, and camera protocol.
2. Train ACT on Linux NVIDIA/cloud; save checkpoint identity, exact training command/config, and logs.
3. Run a bounded follower rollout with clear supervision and guaranteed robot stop; save per-episode outcomes, joint traces, and camera evidence.
4. Import those *same physical episodes* with verified mapping and clock evidence into LaundryBench runs; add experiment context, then open the local UI.
5. Human-review each episode; choose `missed_grasp`, `grasp_lost`, `wrong_object`, `dropped`, `missed_basket`, `timeout`, `intervention`, `hardware_fault`, `frozen_camera`, or `unspecified` as applicable. Keep intervention separate from cause.
6. Compare to the same task/protocol baseline. Select one dominant failure. Add targeted demonstrations or alter one controlled factor, version the changed dataset/policy/protocol, train a candidate, and rerun the same bounded test.

## Stop criteria and checkpoints by phase

| Phase | Pass only when | Stop / diagnose when |
|---|---|---|
| Environment | Exact Python/LeRobot versions captured; required CLI `--help` works | LeRobot import/CLI help fails, required extras absent, or command paths point to another environment |
| Discovery | Two distinct ports map to the correct leader/follower IDs; live camera profile confirmed | Roles/IDs ambiguous, calibration prompt appears unexpectedly, permissions fail, or camera frame is stale |
| Teleop | Follower tracks leader safely; camera display is live; stop path tested | Reversed/jerky movement, stalled follower, unexpected torque, collision risk, frozen image |
| Smoke demos | 2-3 complete local episodes; viewer shows correct task, frames, state/action and duration | Missing/corrupt video, wrong task/camera key, truncated episode, inconsistent action/state, surprise Hub upload |
| Training | Expected checkpoint/config/logs exist; finite loss and metadata match dataset | CUDA unavailable on cloud host, data feature mismatch, NaN loss, missing checkpoint, or wrong dataset revision |
| Native rollout | Bounded supervised evaluation completes with observed outcome notes and no safety fault | Unbounded run, policy/config mismatch, stale/wrong camera, unexpected motion or missing stop behavior |
| LaundryBench UI | Synthetic runs show labels change UI and CLI summaries consistently | Any mock artifact is described as physical; never use a native-only dataset as a LaundryBench run |

## Troubleshooting

### Nothing moves in teleoperation

1. Stop; verify `--robot.type=so101_follower`/`--robot.port` point to the follower and `--teleop.type=so101_leader`/`--teleop.port` to the leader. They must be different ports.
2. Confirm the leader is connected/powered and is the input device. Follower-only hardware cannot produce this two-arm demonstration path.
3. Check OS enumeration again and use persistent Linux `/dev/serial/by-id` where possible. Check non-root serial group permissions on Linux or data cable/USB enumeration on macOS.
4. Recheck exact calibrated robot/teleop IDs and active Python environment. Same ID must be used each time; LeRobot uses ID to find calibration.
5. If a calibration prompt appears, stop instead of recalibrating. Resolve which config/cache the CLI is reading.
6. If device is connected but follower still does not track, stop and capture the sanitized error/version for JWA-26. Don't repeatedly reconnect while the work area is ambiguous.

### Camera preview freezes, shows wrong camera, or is blank

- Quit the process using the documented stop key. Re-run camera discovery after unplug/replug; indices can change. Ensure no other app holds the camera. Use the detected device path/index and a profile it reported.
- Try one USB camera, a shorter USB cable/hub path, and a lower supported resolution/FPS. Confirm moving an object changes frames, not just a static preview. If the preview only updates at 1-2 FPS, do not record/train: check USB bandwidth, camera format, actual FPS, host CPU, and whether another high-resolution stream is open.
- Give the stream the same stable feature key (`front`) when recording and rolling out. Camera display requires optional visualization dependencies; recording itself must still produce encoded frames.
- If video appears smooth but trace timing is uncertain, note that no hardware synchronization is guaranteed. Do not invent `trace_start_s`.

### CUDA unavailable / out-of-memory / training slow

- `torch.cuda.is_available() == False` means the current environment is not using a usable NVIDIA GPU. On Intel macOS, do not expect CUDA; move training to a Linux NVIDIA instance or supported managed GPU job. MPS applies to Apple Silicon and is not CUDA.
- On Linux cloud VM, check `nvidia-smi`, Python/PyTorch build, `lerobot-train --help`, and available disk/RAM before training. Use the LeRobot install guidance for the driver-compatible PyTorch CUDA wheel and `training` extras.
- For out-of-memory, lower training batch size using the installed config flag (inspect `lerobot-train --help`/ACT configuration), reduce image resolution only with a protocol/version change, or use a larger GPU. Record the choice in the experiment note; don't silently change the evaluation camera.

### UI shows no runs, or CLI rate does not match the screen

- Confirm the server's `--outputs-root` points to the exact parent containing `exp-900-mock-baseline` and `exp-901-mock-candidate`, and that there is only one writer server for that directory.
- Refresh after saving; `report.py` writes a static snapshot only when re-run. Verify both UI and CLI read the same run directory and `labels.json` revision.
- A 409 means the browser's expected revision is stale. Reload and verify latest labels before reapplying. If the reviewed count is zero, an unavailable rate is correct. Pending and excluded episodes do not enter metrics.
- Native LeRobot folder not appearing is expected: it is not the LaundryBench run schema.

### Empty / incomplete LeRobot dataset or upload surprise

- `--dataset.num_episodes` is the requested number, not proof that those episodes were valid. Check process completion, cached dataset path, metadata, episode count, video streams and viewer. If the shell exits early, inspect the terminal error and do not train on partial data.
- Start new collections with a unique repo_id; avoid reusing/stamping confusion. Current LeRobot may timestamp the repo ID by default. Save the exact final name printed at completion.
- Use `--dataset.push_to_hub=false` only if supported by the exact version. If a private repo is necessary for cloud access, authenticate intentionally and confirm visibility before upload. Hub tokens stay out of source and chat.

### `lerobot-record` / `lerobot-rollout` flag mismatch

- LeRobot v0.5.x uses legacy behavior; v0.6.x provides `lerobot-rollout`. Check `python -c` package version and `command -v` for every executable. Capture command `--help`; don't mix current docs flags into an older CLI. In v0.6.1, current docs show `lerobot-record` with `--robot.id` and `--teleop.id`; the rollout docs use `--strategy.type=base` for no-record eval and `episodic` for saved eval episodes.
- If rolling out a policy that has different camera feature keys, size, joint ordering/units, or processors from the dataset, stop before motion and resolve the checkpoint/config mismatch.

## Experiment note to leave after a session

Create one note per real collection/training/evaluation and capture:

```text
Experiment/run ID:
Task + protocol ID/version:
Physical action type: teleoperation demo / ACT rollout / assisted trial
Date and operator:
Repository revision and dirty changes:
OS, CPU, Python, LeRobot, PyTorch, CUDA/GPU versions:
Follower port + calibrated ID:
Leader port + calibrated ID:
Camera feature key/index-or-path/resolution/FPS:
LeRobot command and exact --help/version:
Dataset ID/revision/local path; requested and kept episode count:
Checkpoint ID/path/digest and training command/log location:
Evaluation attempt count, outcome per attempt, intervention, failure category:
Camera/video and trace paths; timing source/known offset or unknown:
Stop/cleanup/reconnect result:
One failure pattern and one proposed targeted change:
Next gate/issue:
```

Preserve calibration files, datasets, videos, logs, checkpoints and private tokens outside git. Preserve synthetic UI fixtures as synthetic. Physical claims require actual physical episode evidence.

## Official references and repository anchors

LeRobot CLI syntax is version-sensitive. These Hugging Face sources were checked for this guide; open the versioned docs that match the environment before running a hardware command:

- [LeRobot v0.6.1 SO-101 guide](https://huggingface.co/docs/lerobot/v0.6.1/so101)
- [LeRobot v0.6.1 imitation-learning workflow](https://huggingface.co/docs/lerobot/v0.6.1/il_robots)
- [LeRobot v0.6.1 command cheat sheet](https://huggingface.co/docs/lerobot/v0.6.1/cheat-sheet)
- [LeRobot v0.6.1 policy deployment (`lerobot-rollout`)](https://huggingface.co/docs/lerobot/v0.6.1/inference)
- [LeRobot v0.6.1 installation guide](https://huggingface.co/docs/lerobot/v0.6.1/installation)
- [LeRobot v0.6.1 camera discovery and capture guide](https://huggingface.co/docs/lerobot/v0.6.1/cameras)
- [LeRobot dataset visualization guide](https://huggingface.co/docs/lerobot/v0.6.1/using_dataset_tools)
- [LeRobot v0.6.1 ACT guide](https://huggingface.co/docs/lerobot/v0.6.1/act)

Repository references: `skills/so101-bringup/SKILL.md`; `skills/laundrybench-engineering/SKILL.md`; `docs/plans/so101-readiness.md`; `docs/architecture/so101-adapter.md`; `docs/architecture/results-application.md`; `docs/architecture/media-contract.md`; `docs/architecture/experiment-context.md`; `projects/laundrybench/scripts/{record.py,train.py,run_policy.py,evaluate.py,report.py,import_media.py}`; `projects/laundrybench/configs/*.yaml`.
