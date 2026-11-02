# SO-101 Home Feedback Loop

**Purpose:** bring your already-calibrated SO-101 and installed LeRobot environment through a safe first home session, then run repeatable demonstrations, ACT training, rollout, evidence review, and targeted iteration without confusing native LeRobot artifacts with LaundryBench runs.

**Current capability in one sentence:** LaundryBench now has a dry-run-first LeRobot recorder, strict ACT training/provenance wrapper, supervised ACT policy adapter, bounded SO-101 rollout, camera evidence capture, and UI review/metrics path; software integration is implemented, while calibrated-device compatibility, actual demonstrations/training, camera timing, and task success still require operator-run physical acceptance.

## Read this before the commands

There are two usable workflows, and a software-wired physical feedback loop whose hardware acceptance remains open:

| Workflow | Works now | Does not mean |
|---|---|---|
| LaundryBench mock loop | `make web-demo`, UI labels, CLI/HTML summary, synthetic comparisons | Physical behavior, training data, or robot performance |
| Joined physical pipeline | `record.py` creates a supervised native dataset plus recording manifest; `train.py` validates/provenances ACT; `run_policy.py` creates a bounded physical LaundryBench run with capture artifacts and pending labels | A successful physical task or validated operation on your particular arms/camera/checkpoint; no robot or task run has been done as part of this guide |

The mock-first `evaluation.yaml`, `robot.yaml`, and `camera.yaml` remain mock configs; `scripts/evaluate.py` is still the synthetic evaluation path. The explicit physical configs live separately in `recording.example.yaml`, `training.example.yaml`, and `rollout.example.yaml`. Unlike the earlier placeholder state, the wrappers now connect recording provenance, dataset/checkpoint contracts, ACT inference, physical episode records, camera media, and manual review. The remaining gate is real-device and real-task acceptance, not a software claim that the loop has already succeeded.

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
- [ ] Run LaundryBench `make host-check PYTHON="$LB_PYTHON"` from its dedicated environment, `make lerobot-check PYTHON="$(command -v python)"` from the activated LeRobot environment, and the mock UI loop. Run record/train/rollout dry-runs as each prerequisite becomes available: recording plan before capture, training plan only after a completed dataset/manifest, rollout plan only after a finalized local checkpoint.
- [ ] Identify which physical arm is the **leader** and which is the **follower**; map both different serial ports and calibration IDs. If you do not have the leader arm or another calibrated control device, stop before teleoperation/recording: follower-only control is not enough for the demonstrated native recording command.
- [ ] Enumerate the external camera without moving the robot; record index/path, supported resolution/FPS, and a fresh test frame. Put the camera above the table with the full object and destination visible.
- [ ] Verify LeRobot IDs match existing calibration files; verify each port is stable; verify the chosen `front` camera key, index, resolution, and FPS can be opened. Do not run calibration.
- [ ] With a clear work area and operator present, perform a brief, bounded **leader-driven teleoperation check** only after confirming roles, ports, IDs, and stop method. Stop at once if direction, tracking, or camera image is unexpected.
- [ ] Only after preflight passes, use the supervised recorder for the first bounded leader-driven movement and capture 2 smoke demonstrations to a new local-only dataset. Stop immediately if direction, tracking, or camera image is unexpected; inspect every episode. Task outcomes remain pending until human review.
- [ ] If a compatible Linux NVIDIA host/checkpoint is ready, run the bounded LaundryBench rollout under direct supervision, then label every episode in the UI and compare its reviewed-only metrics/report with a compatible baseline. Otherwise stop after recording and schedule training separately.
- [ ] Finish by writing down exact port/ID/camera/task values, versions, dataset ID and digest, checkpoint, run path, reviewed/pending counts, failures, and the next acceptance gate.

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
command -v lerobot-dataset-viz
lerobot-record --help > /tmp/lerobot-record-help.txt
lerobot-train --help > /tmp/lerobot-train-help.txt
lerobot-rollout --help > /tmp/lerobot-rollout-help.txt
lerobot-find-port --help > /tmp/lerobot-find-port-help.txt
lerobot-find-cameras --help > /tmp/lerobot-find-cameras-help.txt
lerobot-dataset-viz --help > /tmp/lerobot-dataset-viz-help.txt
```

If the version or command path is missing, activate the environment where LeRobot was installed instead of installing a second version over it. If `--help` fails because an optional dependency is missing, fix the environment before connecting the arms. New LeRobot releases move optional capabilities into install extras; the official installation guide maps robot scripts to `core_scripts`, model training to `training`, cameras/video to their required extras, and SO-101 motor support to Feetech. Do not assume `pip install lerobot` alone supplied all hardware and training extras.

Record the `lerobot` package version and command help text with the experiment note. Some CLI options change between releases. The templates below follow the Hugging Face LeRobot v0.6.1 CLI documentation; the installed command's `--help` wins. If a flag is absent, do not copy it anyway.

The LaundryBench environment is distinct from the LeRobot environment. Python 3.11+ is sufficient for the repository; its LeRobot check requires Python 3.12+. The repo's host check reports optional laptop prerequisites but does not verify a physical arm. For LeRobot-side host reporting, after activating that separate environment, run `make host-check PYTHON="$(command -v python)"` and `make lerobot-check PYTHON="$(command -v python)"` from the repository root. If you changed `LB_ENV` because the example path already existed, use that same chosen path in every later standalone `LB_PYTHON=...` line.

In each new terminal that will run LaundryBench commands, set `LB_PYTHON` to the dedicated project environment again; shell variables do not carry over between terminals:

```bash
LB_PYTHON="$HOME/.venvs/laundrybench-review/bin/python"
"$LB_PYTHON" --version
```

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

Record the chosen camera index/path, output profile, and observed FPS. Start with a profile the camera actually reports, for example 640 x 480 at 15 FPS if supported; do not request 1920 x 1080/30 merely because a YAML file says so. Recording dataset FPS cannot exceed camera acquisition FPS; training control rate must exactly match dataset FPS; rollout camera acquisition must be at least the control rate. The aligned examples use a 15 FPS camera and a 15 FPS dataset/control rate; if the camera only supports a lower rate, set recording `dataset.fps`, training `control_hz`, and rollout `runtime.control_hz` to the same lower rate. Keep the same camera name (`front`), index/path, dimensions, and RGB mode throughout; camera acquisition FPS may be higher than the dataset/control rate. A policy trained with one camera feature layout/resolution may reject or misread a different rollout layout.

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

## Phase 3 — configure and record supervised demonstrations

Keep the LeRobot leader/follower roles, ports, IDs, camera feature key, frame geometry, dataset FPS/control rate, and normalized joint setting consistent through collection and rollout. In recording YAML, `camera.fps` is the acquired camera rate and `dataset.fps` is the recorded/control cadence; the latter must not exceed the former. The recording wrapper expects the physical **follower** and a distinct calibrated **leader**. It does not recalibrate and pins LeRobot 0.6.1 through the configured Python executable.

Copy the example to a private local config file. Replace every device-specific placeholder and set absolute paths for the dataset root, recording manifest, LeRobot Python, and LeRobot home. Keep the dataset root new and the manifest outside it. If `HF_LEROBOT_HOME` is set in your shell, it must resolve to the configured LeRobot home. Use the already calibrated IDs and verify their files in the role-specific cache paths from Phase 2.

```bash
cd projects/laundrybench
LB_PYTHON="$HOME/.venvs/laundrybench-review/bin/python"
cp configs/recording.example.yaml /tmp/recording.home.yaml
# Edit /tmp/recording.home.yaml with the observed absolute paths and IDs.
```

Inspect the plan. This writes a `planned` manifest and prints the exact LeRobot argv but does not open serial/camera devices or create a dataset:

```bash
"$LB_PYTHON" scripts/record.py --help
"$LB_PYTHON" scripts/record.py --config /tmp/recording.home.yaml
```

Review the printed follower/leader ports and IDs, camera profile, dataset root, episode count, and `upload_enabled: false`. Stop if roles or IDs are ambiguous, the camera profile has not been observed, the root already exists, or the calibration paths do not match the IDs and selected cache. Before execution, the wrapper checks the configured Python executable, requires exactly LeRobot 0.6.1 and its recording module, validates both nonempty calibration JSON files at their role-specific LeRobot lookup paths, and requires a foreground interactive terminal. It writes lifecycle states `planned`, `running`, `completed`, or `failed` to the configured recording manifest.

**MOVES THE FOLLOWER AND RECORDS PHYSICAL DEMONSTRATIONS.** After the manual safety preflight in Phase 2 passes, run this in the foreground interactive terminal with you beside the follower, the work area clear, and the physical stop accessible:

```bash
"$LB_PYTHON" scripts/record.py \
  --config /tmp/recording.home.yaml \
  --execute --supervised
```

The wrapper prints the exact target and argv, launches LeRobot with shell execution disabled, uploads off, and resume disabled. Follow LeRobot's interactive save/retry/quit controls for v0.6.1. Start with the example's two short episodes; do not save a partial attempt just to meet the count. Ctrl+C/SIGTERM stops the process group and records failure/interruption. Stop if a calibration prompt appears; do not recalibrate as a workaround.

**Expected outputs:** the new native dataset at `dataset.root`, the configured recording JSON manifest outside it, and dataset metadata/data/video. The completed manifest records the effective repo ID when present, portable `local-sha256:<64 hex>` tree digest, `meta/info.json` digest, exact command, device/calibration IDs, exit result, and a validated ACT I/O contract only when metadata matches. The dataset digest covers every regular file in `meta/`, `data/`, and `videos/`; it is distinct from the absolute root and native repo ID. A copied full tree retains the digest; any changed file changes it.

After exit, require manifest `status: completed`, return code zero, dataset files and metadata present, and `act_io_contract.status: validated`. Inspect an episode with the LeRobot viewer before training. Activate the same LeRobot environment used for recording, then use the explicit dataset root and configured repo ID (prefer exact `repo_id_effective` from the manifest when present):

```bash
DATASET_ROOT="<ABSOLUTE recording.dataset.root>"
DATASET_REPO_ID="<EFFECTIVE repo ID or recording.dataset.repo_id>"
lerobot-dataset-viz \
  --repo-id "$DATASET_REPO_ID" \
  --root "$DATASET_ROOT" \
  --mode local \
  --episode-index 0
```

The viewer needs the LeRobot visualization extra/Rerun; use the installed `lerobot-dataset-viz --help` and install guidance if unavailable. Inspect camera frames, task text, state/action plots, duration, and whether the actual object/destination are visible. The schema can validate dimensions/names/FPS, but cannot prove camera freshness or task success.

## Phase 4 — validate and train ACT with provenance

LaundryBench's training wrapper delegates ACT to LeRobot 0.6.1 and validates the completed recording manifest, content digest, metadata digest, named camera and dimensions, exact ordered six-joint state/action names, normalized units, recording's `use_degrees=false` settings, task/protocol, and matching dataset/control FPS. It refuses an existing output directory. Without `--execute`, it validates and prints a plan; it does not import LeRobot, create output, upload data, or train.

Fingerprint the dataset and copy the exact `local-sha256:` value into `training.dataset_id`. For **local training**, also set `training.dataset_revision` to that same local content ID. For **cloud training**, keep `dataset_id` as the local content ID but set `dataset_revision` to the exact 40-character Hub dataset commit SHA after privately uploading the dataset as described below. Set `dataset_repo_id` to the effective repo ID from the recording manifest (and matching `meta/info.json` when present), and `dataset_manifest` to the completed recording manifest. Keep `dataset_root` pointing to the complete local dataset tree; the cloud wrapper independently verifies its identity against the selected private Hub commit. Use absolute paths for dataset, manifest, and a fresh output directory. Copy/edit the strict example. Its `contract` must match the validated dataset exactly: `state_names` and `action_names` must copy metadata feature names verbatim (LeRobot SO-101 v0.6.1 uses `.pos` suffixes); `joint_names` is the canonical bare order `shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper`. Units are normalized, camera key/dimensions/RGB/uint8 match the data, `use_degrees: false`, and normalized bounds match SO-101. Set `control_hz` equal to dataset FPS; no resampling is implemented. Keep the aligned example rates together; if you lower the rate, update recording dataset FPS, training control FPS, rollout control FPS, and camera acquisition FPS so camera acquisition remains at least as high as control.

```bash
"$LB_PYTHON" scripts/train.py --help
"$LB_PYTHON" scripts/train.py \
  --fingerprint-dataset "/absolute/path/to/recorded-dataset"
cp configs/training.example.yaml /tmp/training.home.yaml
# Edit the config with the fingerprint, completed manifest, contract and paths.
"$LB_PYTHON" scripts/train.py --config /tmp/training.home.yaml
```

For actual training use a compatible LeRobot 0.6.1 training environment and supported accelerator. For Linux NVIDIA, check `nvidia-smi` and verify `torch.cuda.is_available()`. The dataset tree is portable: you may copy it to the GPU host, then point `training.dataset_root` to the copy, provided the copy is complete and unchanged, its freshly computed `local-sha256:` digest exactly matches the recording manifest's dataset ID, and its `meta/info.json` digest matches the manifest. Keep the original completed recording manifest as provenance; do not rewrite it to replace its recorded collection path. The wrapper checks tree identity and metadata content, not that the training host reuses the original absolute dataset path. If you cannot transfer the private dataset safely, use the explicitly private HF Jobs path instead. Then execute using the LaundryBench environment on the training host and the Python from that host’s actual LeRobot 0.6.1 environment:

```bash
"$LB_PYTHON" scripts/train.py \
  --config /tmp/training.home.yaml \
  --lerobot-python "/absolute/path/to/lerobot-env/bin/python" \
  --execute
```

A local completed run has `laundrybench_training.json` and a root-level `policy_contract.json` in the configured LaundryBench output directory. LeRobot writes to the fresh `native/` child; use the checkpoint path in the manifest, typically `native/checkpoints/<step>/pretrained_model/`, for rollout. A usable native checkpoint includes `config.json`, `model.safetensors`, `policy_preprocessor.json`, `policy_postprocessor.json`, referenced normalizer/unnormalizer processor-state `.safetensors`, and its `policy_contract.json`; the root-level contract is also emitted for convenient provenance. Contracts hash model weights, processor JSONs, and processor-state files, then bind them to dataset/task/protocol/camera/joint metadata. A zero exit code without all expected files is not a pass. Two smoke demos check plumbing, not ACT quality or safe task performance.

Cloud mode is an explicitly opted-in, billable route for a laptop without an NVIDIA GPU. It requires `mode: cloud`, a job target, explicit private model repo, `private: true`, and `allow_private_upload: true`. You must privately upload the dataset yourself first; the LaundryBench wrapper never uploads it. The wrapper checks the selected LeRobot environment's Hub credentials, requires the dataset repo to be private and the requested SHA to resolve to that exact commit, downloads only `meta/`, `data/`, and `videos/` into a temporary snapshot, and compares that snapshot's content digest to the local recording manifest before it creates the run output or submits a job. The native Job receives `--dataset.revision=<40-character-SHA>`, so it cannot silently train from a different `main` revision. The cloud dry-run marks this remote check pending; the check happens only on `--execute`.

Under the existing `training:` mapping in `/tmp/training.home.yaml`, set these fields (choose a valid target and a private model repo):

```yaml
mode: cloud
allow_private_upload: true
cloud:
  target: a10g-small
  model_repo_id: your-namespace/private-act-checkpoint
  private: true
```

Create a private dataset repository, upload the complete local dataset tree, then record the exact commit SHA. Do not upload publicly. If the repo already exists, verify its visibility is private before uploading. The HF CLI commands below follow the official Hub CLI (`hf repos create`, `hf upload`); authenticate interactively and do not put tokens in shell history or this config.

```bash
DATASET_REPO_ID="<namespace/private-dataset>"
DATASET_ROOT="/absolute/path/to/verified-recorded-dataset"
hf auth login
hf repos create "$DATASET_REPO_ID" --repo-type dataset --private
hf upload "$DATASET_REPO_ID" "$DATASET_ROOT" --repo-type dataset
```

If `hf repos create` reports that the repository already exists, inspect it in the Hub settings and confirm it is private before proceeding. After upload, query and save the commit SHA produced by that upload. This command prints the current dataset commit SHA using the activated LeRobot environment:

```bash
LEROBOT_PYTHON="/absolute/path/to/lerobot-env/bin/python"
DATASET_REPO_ID="<namespace/private-dataset>" \
  "$LEROBOT_PYTHON" - <<'PY'
import os
from huggingface_hub import HfApi

repo_id = os.environ["DATASET_REPO_ID"]
info = HfApi().repo_info(repo_id=repo_id, repo_type="dataset")
if info.private is not True:
    raise SystemExit("Refusing to use a dataset repository that is not private")
print(info.sha)
PY
```

Set `training.dataset_repo_id` to this private dataset repo, `training.dataset_revision` to the exact 40-character commit SHA, and `training.dataset_root` to the existing absolute local tree already bound to the completed recording manifest. Keep `training.dataset_id` as the local `local-sha256:` content digest. The wrapper verifies the private Hub snapshot against that local content identity before submission. It rejects an existing public model repo; use a new private model repo or an existing private one. The Jobs flow pins `--dataset.revision` and enables a private model push. Refer to Hugging Face's [Hub CLI guide](https://huggingface.co/docs/huggingface_hub/en/guides/cli) and [upload guide](https://huggingface.co/docs/huggingface_hub/en/guides/upload) for the current syntax and behavior.

First plan again and inspect the printed command/target. Review account access, dataset/video privacy, current hardware availability and price. Authenticate interactively and submit only after those checks:

```bash
hf auth login
"$LB_PYTHON" scripts/train.py --config /tmp/training.home.yaml
# Only after reviewing the private target, cost, and printed plan:
"$LB_PYTHON" scripts/train.py \
  --config /tmp/training.home.yaml \
  --lerobot-python "/absolute/path/to/lerobot-env/bin/python" \
  --execute
```

A training process can record `submitted`, `detached`, or `submission_error` depending on how the submit client ended; a job ID must be present to continue finalization, and none of those statuses alone prove completion. Follow native HF Job logs until the remote job is complete. Get the exact 40-character model repository commit revision, then download that immutable revision to a new private local directory:

```bash
MODEL_REPO="<PRIVATE_NAMESPACE/MODEL_REPO>"
MODEL_REVISION="<FULL_40_CHARACTER_MODEL_COMMIT_SHA>"
DOWNLOAD_DIR="/absolute/path/to/private-model-download"
hf download "$MODEL_REPO" --repo-type model \
  --revision "$MODEL_REVISION" --local-dir "$DOWNLOAD_DIR"
find "$DOWNLOAD_DIR" -name config.json -print
```

From that output, set `CHECKPOINT_DIR` to the directory containing the ACT `config.json`, `model.safetensors`, both processor JSON files, and every processor-state file they reference. The checkpoint may be directly in `$DOWNLOAD_DIR` or in a nested `pretrained_model` directory; select the actual directory that contains the complete model bundle. Do not assume a fixed subdirectory; verify the files before finalizing. Use the same cloud config and configured output directory recorded for the submission:

```bash
CHECKPOINT_DIR="$DOWNLOAD_DIR/<exact directory containing model files>"
"$LB_PYTHON" scripts/train.py \
  --config /tmp/training.home.yaml \
  --finalize-checkpoint "$CHECKPOINT_DIR" \
  --remote-model-revision "$MODEL_REVISION" \
  --confirm-remote-complete
```

The finalizer accepts a prior `submitted`, `detached`, or `submission_error` record only when a Job ID is recorded and config/dataset/model-repo lineage matches. It requires your explicit completion confirmation. It writes `policy_contract.json` and `laundrybench_finalize.json` with `status: contract_finalized` into the downloaded checkpoint; only then can rollout dry-run validate that local bundle. The original training run keeps its original submission state. The finalizer relies on your confirmation of remote completion and selected model commit; the recorded revision verification is operator-asserted, not independently queried.

## Phase 5 — dry-run, then bounded supervised ACT rollout

Copy the example to a local config and set absolute paths for a completed local checkpoint with adjacent `policy_contract.json` and a fresh output directory under `projects/laundrybench/outputs/physical/<EXPERIMENT_ID>`. Set the exact dataset ID/revision, task/protocol, existing calibrated follower port/ID, same camera key/dimensions, and finite conservative limits. The rollout runner resolves relative paths from the YAML file; the copied `/tmp` config must not retain its example-relative output path. The example defaults to three episodes, 15 seconds each, 15 Hz control and `max_relative_target: 1.0`, aligned with the recording/training examples. Keep `runtime.control_hz: 15` only if the trained dataset FPS is exactly 15; otherwise set it to the exact training FPS. Camera acquisition FPS must be at least control FPS. Keep the per-command relative limit small. The implementation caps it at five normalized units, which is not a collision, velocity, or emergency-stop guarantee.

```bash
cd projects/laundrybench
cp configs/rollout.example.yaml /tmp/rollout.home.yaml
# Edit paths, dataset/checkpoint identity, follower and camera values.
"$LB_PYTHON" scripts/run_policy.py --help
"$LB_PYTHON" scripts/run_policy.py --config /tmp/rollout.home.yaml
```

Default invocation is a no-motion dry run: it validates config, checkpoint files, saved LeRobot processors, hashes and policy contract without importing Torch/LeRobot or connecting to the robot. The output directory must be new. Resolve all mismatches before physical execution, especially dataset revision, task/protocol, camera key/shape, dataset/control FPS, joint order/units and processor hashes.

**EXECUTES A TRAINED POLICY ON THE PHYSICAL FOLLOWER.** Run only after the dry run passes and you confirm the calibrated follower port/ID, clear work area, live matching camera, accessible physical stop, and your presence beside the arm. `run_policy.py` calls `connect(calibrate=False)`; it does not calibrate or home. The runner validates its contract and runtime limits before connecting. Ctrl+C/SIGTERM/error aborts active capture and stops/disconnects the robot; keep the physical stop accessible throughout.

```bash
"$LB_PYTHON" scripts/run_policy.py \
  --config /tmp/rollout.home.yaml \
  --execute --supervised
```

The code cap is ten episodes and 120 seconds per episode, with cadence and target limits from config; choose a smaller first run. Use a new output directory for every rollout. A process that exits cleanly is not evidence that the task succeeded.

## Phase 6 — inspect physical evidence, review outcomes, and iterate

The supervised runner writes a real LaundryBench run directly. It emits `manifest.yaml`, `episodes.jsonl`, `traces/steps.jsonl`, `traces/commands.jsonl`, `quality.json`, `experiment.json`, per-episode `media/<episode_id>/media.json` and MP4, plus `capture_diagnostics.json`. Context binds config, checkpoint, dataset, task/protocol and LeRobot identities. `commands.jsonl` separates requested targets from targets sent after the SO-101 adapter's relative bound. Video records the fresh pre-action observation frames supplied to ACT; the terminal post-action observation is not currently appended, so the final video frame is not full endpoint visual proof. Host observation timestamps are mapped to fixed-FPS video with a bounded cadence/drift check; camera exposure timestamps are unavailable and repeated stale frames cannot be detected without a device counter.

Each rollout episode is provisional: it starts `success: false`, `failure_category: unspecified`, without a human label. It contributes to reviewed-only metrics only after a person saves an outcome. Inspect `capture_diagnostics.json`: require completed status, expected FPS and frame counts, acceptable maximum timestamp residual, no error, `media.json`, and playable video. These checks establish software evidence integrity, not exposure synchronization or task success.

From the repository root, serve the physical run parent directory (one writer server for the root):

```bash
"$LB_PYTHON" projects/laundrybench/scripts/serve.py \
  --outputs-root projects/laundrybench/outputs/physical \
  --frontend-dir projects/laundrybench/frontend/dist
```

Open `http://127.0.0.1:8765`; select the experiment ID in the rollout config. Inspect each episode's camera, timeline, traces/commands and context, then save a human outcome and failure category in the UI. Record intervention separately from cause. Exclude an episode only for a specific evidence-quality reason such as corrupt video, wrong camera, or invalid capture. Never label a task successful only because the process exited cleanly. Labels are in `labels.json`; the original physical episode evidence stays unchanged. If a label write returns HTTP 409, reload and confirm current labels before retrying.

After reviewing, regenerate the report for that same run:

```bash
"$LB_PYTHON" projects/laundrybench/scripts/report.py \
  --experiment-dir projects/laundrybench/outputs/physical/<EXPERIMENT_ID>
```

Compare the UI and `summary.json`/`report.html`: reviewed, pending and excluded episode counts; reviewed-only `success_rate`; `failure_category_counts`; and `label_revision`. If none are reviewed, rate is unavailable, not zero. Compare baseline/candidate only when task, protocol, conditions and relevant context match; do not call a synthetic mock run a physical baseline.

For failure analysis, inspect video and timeline, state/action traces, requested-versus-sent commands, checkpoint/data contract, capture diagnostics and `quality.json`. Choose one dominant failure and one controlled response: repair/add demonstrations, adjust one bounded config/control factor, or investigate adapter/camera/evidence. Keep the failed run immutable. Use new dataset/checkpoint/config/run paths and repeat the same bounded protocol. Record the changed factor and compare only compatible runs.

## Implemented software and open physical acceptance

| Gate | Implemented software | Physical acceptance still needed |
|---|---|---|
| JWA-26 | SO-101 adapter, normalized joint contract and bounded relative targets; offline tests | Verify calibrated hardware direction, observations, live camera, stop/reconnect and installed-host compatibility |
| JWA-16 | Dry-run-first supervised recorder with calibration-path checks and lifecycle manifest | Complete and inspect real demonstrations and dataset metadata |
| JWA-17 | Strict dataset-bound ACT wrapper, checkpoint/proc-state provenance, private Jobs submission and explicit downloaded-checkpoint finalizer | Run actual GPU training and evaluate checkpoint quality; cloud completion, selected revision and model contents require operator confirmation |
| JWA-23 | Contract/hash-checked ACT adapter and bounded supervised physical runner | Validate local checkpoint inference and safe behavior on the calibrated arm |
| JWA-14 | Physical runs use normal LaundryBench artifacts and UI label lifecycle | Confirm real media/traces review correctly and reviewed metrics make sense |
| JWA-28 | Capture from fresh pre-action observations with bounded host-clock/video cadence diagnostics | Validate camera freshness and real host timing; hardware exposure synchronization is not claimed |

The optional CPU integration smoke uses generated synthetic inputs and a one-step CPU training pass; it checks LeRobot compatibility and adapter plumbing, not training on recorded demonstrations or checkpoint quality. No hardware action, real demonstration, GPU job, or physical rollout was run in preparing this guide. Stop on unexpected motion, unexpected calibration flow, contract mismatch, or capture diagnostics failure. The software integration is implemented; physical acceptance and task success are still unverified.

## Stop criteria and checkpoints by phase

| Phase | Pass only when | Stop / diagnose when |
|---|---|---|
| Environment | Isolated LaundryBench env, active LeRobot 0.6.1 Python, wrappers' `--help` and mock UI loop work | CLI path points to another env, extras are absent, or project Python is below 3.11 |
| Discovery/dry runs | Correct leader/follower roles and existing IDs; camera live; record/train/rollout plans match intended data/paths | Roles/IDs ambiguous, unexpected calibration prompt, permission error, mismatched dataset/checkpoint contract |
| Recording | Completed manifest, full dataset tree, validated metadata contract, inspected demonstrations | Failed/partial manifest, no videos, invalid metadata contract, frozen/wrong camera, or unexpected Hub upload |
| Training | Completed manifest shows checkpoint and processor contracts/hashes; finite logs and correct dataset revision | Fingerprint mismatch, unsupported CUDA, output exists, NaN/error, or missing checkpoint artifact |
| Physical rollout | Bounded run, clean capture diagnostics, all episodes reviewed, metric/report matches labels | Unexpected motion, stale camera, contract mismatch, capture abort, or unreviewed/unsupported success claim |
| Review/iteration | Physical runs are compared only under compatible task/protocol; one targeted change is recorded | Synthetic data is presented as physical or old run evidence is manually rewritten |

## Troubleshooting

### Recording does not start or the follower does not move

1. For a dry run, check config path/required fields and that its manifest is `planned`. For execution, it must run in a foreground TTY with both `--execute --supervised`.
2. Verify recording config has a distinct physical follower and leader port and ID, with each calibration path matching the ID/cache selected by `lerobot.home` and `HF_LEROBOT_HOME`.
3. Check OS enumeration and non-root serial permissions. Confirm the leader is powered/connected and the arm roles match physical labels.
4. The wrapper requires LeRobot exactly 0.6.1 in the configured Python. Recheck `lerobot.python` and the command plan; do not repair by recalibrating.
5. If any calibration prompt appears, stop immediately and resolve the configured ID/cache mismatch. If physical behavior remains unexpected, power-stop safely and preserve the recording manifest/error for JWA-26.

### Camera preview freezes, shows wrong camera, or is blank

- Stop the recorder/rollout immediately using Ctrl+C or the physical stop if needed. Re-run camera discovery after unplug/replug; indices can change. Ensure no other app holds the camera. Use the detected device path/index and a profile it reported.
- Try one USB camera, a shorter USB cable/hub path, and a lower supported resolution/FPS. Confirm moving an object changes frames, not just a static preview. If the preview only updates at 1-2 FPS, do not record/train: check USB bandwidth, camera format, actual FPS, host CPU, and whether another high-resolution stream is open.
- Give the stream the same stable feature key (`front`) for training and rollout. Check the recording `act_io_contract`, then after rollout inspect `capture_diagnostics.json`, `media.json`, the expected frame count and that the MP4 plays.
- A cadence failure aborts capture; fix FPS/host load and use a new output directory. The diagnostics bound host observation-to-video timing but do not provide camera exposure synchronization or detect repeated stale frames.

### CUDA unavailable / out-of-memory / training slow

- `torch.cuda.is_available() == False` means the current environment is not using a usable NVIDIA GPU. On Intel macOS, do not expect CUDA; move training to a Linux NVIDIA instance or supported managed GPU job. MPS applies to Apple Silicon and is not CUDA.
- On Linux cloud VM, check `nvidia-smi`, Python/PyTorch build, `lerobot-train --help`, and available disk/RAM before training. Use the LeRobot install guidance for the driver-compatible PyTorch CUDA wheel and `training` extras.
- Training config selects device and batch size; `train.py` prints the exact command in plan mode. For out-of-memory, lower configured `batch_size` or use a larger GPU. Reduce image resolution only with a protocol/version change; record the change and do not silently alter the evaluation camera.

### TorchCodec/FFmpeg or binary ABI import error

First confirm which LeRobot Python is running the training command. In a dedicated training environment, run the repo readiness check and optional CPU ACT adapter smoke:

```bash
set -e
cd projects/laundrybench
LEROBOT_PYTHON="/absolute/path/to/your/lerobot-env/bin/python"
"$LEROBOT_PYTHON" scripts/check_lerobot.py
"$LEROBOT_PYTHON" -c 'import torch, torchcodec; from torchcodec.decoders import get_safe_default_video_backend; print("torch", torch.__version__, "torchcodec", torchcodec.__version__, "backend", get_safe_default_video_backend())'
ffmpeg -version
PYTHONPATH="$PWD/src" "$LEROBOT_PYTHON" -m pytest tests/optional/test_lerobot_act_smoke.py
```

- The checked-in Linux CUDA training container currently pins Torch 2.7.1, torchvision 0.22.1, and TorchCodec 0.5.0 for CUDA 12.8. Treat that as a matched container stack, not a command to replace packages in your existing LeRobot environment. If the import/backend check fails, recreate a dedicated training environment/container with the compatible stack and repeat the readiness/CPU smoke checks; keep the LeRobot environment used for calibrated hardware separate until the replacement is verified.

### UI shows no runs, or CLI rate does not match the screen

- For a physical rollout config using `outputs/physical/<EXPERIMENT_ID>`, serve `projects/laundrybench/outputs/physical` as `--outputs-root`; the UI lists runs immediately inside that directory. Use one writer server for the root.
- Refresh after saving; `report.py` writes its static snapshot only when rerun. Verify UI and report point to the same rollout directory and `labels.json` revision.
- A 409 means the browser's expected revision is stale. Reload and verify latest labels before reapplying. If reviewed count is zero, unavailable success rate is correct. Pending and excluded episodes do not enter reviewed metrics.
- If the physical run does not appear, inspect the rollout config's resolved `output_dir` and serve its parent. Do not point the UI at the native dataset root; the rollout wrapper already creates the LaundryBench run itself.

### Recording failed, dataset is incomplete, or fingerprint differs

- Recording needs a new dataset root and separate manifest path each attempt; the wrapper refuses overwrite and resume. Read manifest `status`, `return_code`, `error`, and LeRobot output before continuing.
- Do not train on a partial/failed tree. Verify the metadata contract is `validated`, dataset root contains `meta/`, `data/` and `videos/`, and the dataset digest matches a fresh `--fingerprint-dataset` result.
- A dataset copy must be complete and unmodified. Any added/deleted/changed file changes its digest; rerun fingerprint and update config only after intentionally freezing the new dataset revision.
- Recording always sets `--dataset.push_to_hub=false`. The cloud wrapper does not upload the dataset: upload it yourself to a private Hub dataset repo, use the exact commit SHA in `training.dataset_revision`, and let the wrapper verify that private snapshot matches the local recording digest. If verification fails, stop and check repo visibility, commit SHA, and whether the complete `meta/`, `data/`, and `videos/` tree was uploaded. Do not put tokens in source/chat.

### Training or rollout contract mismatch

- The wrappers pin LeRobot 0.6.1; inspect the selected `lerobot-python` and `--help` in the same environment. Do not bypass the checked wrapper with an unrelated `lerobot-rollout` command.
- Training requires the completed recording manifest, matching content and metadata hashes, explicit state/action names/units and matching dataset FPS. A config that merely asserts a contract is not enough.
- Rollout dry-run prints a mismatch before hardware connect. Check the checkpoint's local `policy_contract.json`, dataset revision, processor digests, camera names/dimensions, and `runtime.control_hz`. Fix config or train from the intended data before physical execution.
- If local output directory already exists, use a new unique path; do not delete evidence to rerun.

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

Repository anchors: `skills/so101-bringup/SKILL.md`; `skills/laundrybench-engineering/SKILL.md`; `projects/laundrybench/docs/architecture/{recording-workflow.md,training-workflow.md,act-rollout.md,physical-evidence.md}`; `projects/laundrybench/scripts/{record.py,train.py,run_policy.py}`.
