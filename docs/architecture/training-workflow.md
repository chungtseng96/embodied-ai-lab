# ACT training workflow

LaundryBench delegates training and checkpoint serialization to the pinned
LeRobot 0.6.1 `lerobot-train` entrypoint. The adapter validates the dataset and
the policy I/O contract, constructs an argv list, records provenance, and
checks native outputs. It does not reimplement ACT or LeRobot processors.

## Prepare a run

Copy `projects/laundrybench/configs/training.example.yaml` to a local config
outside version control. Fill in the dataset's exact `local-sha256:<tree-digest>`
identity, LeRobot repo ID, dataset revision, local dataset root and its
completed recording manifest, output directory, task/protocol
identity, camera names/profile, and ordered feature names. `meta/info.json`
must be present below the local dataset root. The adapter checks its declared
repo ID when present, checks the feature keys, order, dtype, shapes, camera
dimensions, and dataset FPS. The completed recording manifest must bind the
same content ID, `meta/info.json` SHA-256, LeRobot 0.6.1, RGB camera
profile, and `use_degrees: false` for both robot and teleoperator. This prevents
the config alone from asserting normalized units for an unrelated dataset.
Relative `dataset_root`, `dataset_manifest`, and `output_dir` paths resolve
from the config file's directory, matching the recording and rollout wrappers.
Use absolute paths when a copied config lives elsewhere.
For a local recording, create a content revision with
`python scripts/train.py --fingerprint-dataset /absolute/dataset/root`; the
`local-sha256:<64 hex>` digest uses the shared `dataset-tree-sha256-v1`
contract: every regular file in `meta/`, `data/`, and `videos/`, with
relative-path and size framing; it rejects symlinks and does not hash root-level files outside those
trees. It is rechecked during training and stays the same after an identical
copy to another path. For a Hub dataset, specify the full 40-character commit
SHA. A Hub revision is marked verified only if metadata contains the same
revision; LeRobot local metadata often omits it. The run record preserves the
revision and verification status, recording manifest hash, and metadata
SHA-256.

The ordered `joint_names` use the canonical SO-101 order. `state_names` and
`action_names` are explicit declarations of the names stored in dataset
metadata; they are checked verbatim and are never inferred from suffixes.
The camera mapping uses bare names such as `front`, matching runtime image
keys, and must correspond exactly to `observation.images.<name>` features.
Control rate must equal the dataset's declared FPS. No resampling is
implemented.

The contract describes SO-101 coordinates in normalized robot units:
`shoulder_pan` through `wrist_roll` use [-100, 100], and `gripper` uses [0, 100].
This is separate from ACT's model preprocessing. LeRobot's saved preprocessor
and postprocessor own the actual dataset-statistics transforms (including
ACT's configured mean/std normalization). Training requires and records those
native JSON processor artifacts and every referenced state tensor, hashes them
plus `config.json` and `model.safetensors` into `policy_contract.json`;
rollout verifies the full reference set and all digests before loading.

## Plan and execute

From `projects/laundrybench`, inspect the plan first:

```bash
python3 scripts/train.py --config /path/to/training.yaml
```

This performs strict config, recording-manifest and metadata validation, then prints the exact
command. It does not import LeRobot, create an output directory, upload data,
or start training. To execute local training, pass the Python executable from
the actual Linux NVIDIA LeRobot environment:

```bash
python3 scripts/train.py --config /path/to/training.yaml \
  --lerobot-python /path/to/lerobot-env/bin/python --execute
```

Execution requires LeRobot exactly 0.6.1. Output directories are exclusive;
existing ones are never overwritten. LaundryBench creates the configured run
root for its manifest and contract, then gives LeRobot a fresh `native/`
child directory. LeRobot 0.6.1 rejects an existing native `--output_dir`
unless resuming; the wrapper never enables resume. Local checkpoints therefore
appear under `<run-root>/native/checkpoints/<step>/pretrained_model/`. The manifest records the source commit
and a source tree digest, effective config and dataset metadata hashes, exact
command, task/protocol, seed, LeRobot and Python versions, logs, result state,
and checkpoint files. A local run is `completed` only when LeRobot exits zero
and a checkpoint includes config, model weights, preprocessor, and
postprocessor. A success code without these files is a failed run.

## Optional Hugging Face Jobs

Cloud mode is opt-in in YAML and requires an explicit job target, private model
repo, `private: true`, and `allow_private_upload: true`. LeRobot's native Jobs
behavior trains against an already uploaded dataset and pushes the model to
the private destination. Set `dataset_repo_id` to the exact private dataset
repo and `dataset_revision` to its full 40-character Hub commit SHA. Before
creating the run output or submitting a Job, the selected LeRobot Python
checks the dataset repo is private, snapshots that exact revision, and
compares its content-tree digest with the validated local recording. A mismatch
or public dataset repo stops execution. If the model repo already exists, it
must also be private; otherwise LeRobot is instructed to create it privately.
Upload the completed recording to the private dataset repo before selecting
cloud mode. The wrapper does not upload datasets. Review account access, data visibility, target hardware,
and current price before `--execute`. The command wrapper records a successful
submission as `submitted`; it does not represent remote job completion or a
trained checkpoint. If interrupted, it records `detached` and remote status
`unknown`; the HF Job may continue. A nonzero native client exit is
`submission_error`, which does not prove whether a remote job started. The
local record retains a bounded tail of submission logs. Use native Jobs logs
to follow it. A completed remote model must be fetched
and its final contract materialized and checked before rollout.

To select this mode, add `mode: cloud`, `allow_private_upload: true`, and a
`cloud` mapping with explicit `target`, `model_repo_id`, and `private: true`.
Do not set cloud fields in local mode. `allow_private_upload: true` explicitly
authorizes the model push; the dataset must already be available privately at
the exact pinned Hub commit.

After the HF Job logs show completion, record the model repository's exact
40-character commit SHA and download the model repository to a private local
directory. For example:

```bash
hf download <namespace/model-repo> --repo-type model \
  --revision <model-repo-commit-sha> --local-dir /path/to/downloaded-model
```

Find the completed checkpoint's `pretrained_model` directory and finalize it
against the original config and submitted run record:

```bash
python scripts/train.py --config /path/to/training.yaml \
  --finalize-checkpoint /path/to/downloaded-model/checkpoints/<step>/pretrained_model \
  --remote-model-revision <model-repo-commit-sha> --confirm-remote-complete
```

Finalization accepts a prior `submitted`, `detached`, or `submission_error`
record only when it contains an HF Job ID; it validates an ACT `config.json`,
weights, saved pre/postprocessors and their referenced normalizer state tensors,
the recorded dataset/config/model-repo lineage, and explicit operator
confirmation of remote completion. It writes the
portable contract and a `laundrybench_finalize.json` alongside the downloaded
checkpoint. The original submission manifest keeps its prior state;
finalization records that a usable contract was bound to downloaded artifacts, not that
this machine trained the model or independently queried HF Job completion.
The supplied model-repo commit SHA is recorded as an operator assertion; local
file digests are checked, but the finalizer does not query the Hub or prove
which repo revision populated the download directory.

## Container

`projects/laundrybench/Dockerfile.train` pins the LeRobot version and Python
3.12 in a CUDA 12.8 runtime image. It also pins the tested media/runtime
matrix: PyTorch 2.7.1, torchvision 0.22.1, and torchcodec 0.5.0. The PyTorch
and torchcodec wheels are installed explicitly from the CUDA 12.8 (`cu128`)
index; a constraints file keeps `lerobot[training]==0.6.1` from replacing the
torch/torchvision/torchcodec pins. Torchcodec 0.5 is the compatible decoder
line for PyTorch 2.7. For a matching Linux NVIDIA environment outside Docker,
install the PyTorch pair from `https://download.pytorch.org/whl/cu128`, install
`lerobot[training]==0.6.1` with constraints pinning all three versions, then
install `torchcodec==0.5.0` from the same cu128 index without dependency
resolution. Build it on a
supported Linux NVIDIA host, then
mount a private run config and dataset root and invoke the same `scripts/train.py`
command. Build from `projects/laundrybench` with the source revision supplied:

```bash
docker build -f Dockerfile.train \
  --build-arg LAUNDRYBENCH_SOURCE_SHA="$(git rev-parse HEAD)" \
  -t laundrybench-act:lerobot-0.6.1 .
```

The image does not contain `.git`; training records `source_sha_origin:
build_argument_operator_asserted` and also hashes the copied source files.
This repository change has not been validated with a Docker build or
GPU run; local CI validates only the wrapper using fake process/checkpoint
fixtures.

## Evidence limits

Dry-run validation and fake-executor tests demonstrate command construction,
strict dataset/contract checks, safe output handling, status transitions, and
checkpoint verification. They do not demonstrate ACT convergence, GPU
compatibility, cloud submission success, policy quality, or robot performance.

Reference: Hugging Face's [LeRobot v0.6.1 imitation learning workflow](https://huggingface.co/docs/lerobot/v0.6.1/il_robots), which documents `lerobot-train`, ACT flags, local checkpoints, and optional `--job.target` submission.
