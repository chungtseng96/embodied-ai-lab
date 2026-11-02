# Supervised native LeRobot recording

LaundryBench's recording adapter builds a deterministic argument vector for
LeRobot 0.6.1. LeRobot remains responsible for the device drivers, teleoperation,
dataset encoding, and episode controls. This does not turn a native dataset into
a LaundryBench evaluation run or label its physical outcomes.

## Interfaces and version basis

The target is the official LeRobot 0.6.1 release and its
[`lerobot.scripts.lerobot_record` source module](https://github.com/huggingface/lerobot/blob/v0.6.1/src/lerobot/scripts/lerobot_record.py).
The versioned
[SO-101 follower config](https://github.com/huggingface/lerobot/blob/v0.6.1/src/lerobot/robots/so_follower/config_so_follower.py)
and
[SO-101 leader config](https://github.com/huggingface/lerobot/blob/v0.6.1/src/lerobot/teleoperators/so_leader/config_so_leader.py)
expose independent `use_degrees` settings, so the wrapper pins both to false
for matching normalized joint values. The official
[OpenCV camera config](https://github.com/huggingface/lerobot/blob/v0.6.1/src/lerobot/cameras/opencv/configuration_opencv.py)
defaults to RGB output; the wrapper sets `color_mode=rgb` explicitly and
records RGB in the manifest.
The versioned
[real robot recording guide](https://huggingface.co/docs/lerobot/v0.6.1/il_robots)
shows SO-101 follower and leader types, separate `robot` and `teleop` ports and
IDs, the named `robot.cameras` map, `dataset.repo_id`, `dataset.num_episodes`,
and `dataset.single_task`. It documents `dataset.root` for a chosen local
dataset directory and `dataset.push_to_hub=false` for keeping collection local.
The adapter uses the versioned Python module entry point rather than resolving
a potentially unrelated `lerobot-record` executable from `PATH`; execution
probes the selected Python environment for both package version and module
availability before launching it.

LeRobot may generate a session suffix for a dataset repository name. The
manifest therefore distinguishes `dataset.repo_id_requested` from
`dataset.repo_id_effective`. The latter is filled only when the completed
dataset's own `meta/info.json` exposes an exact identity; the wrapper never
passes the requested base name off as the final name. For a completed local
dataset, `dataset.dataset_id` is `local-sha256:<digest>` over every regular file
under `meta/`, `data/`, and `videos/`. The digest includes each path relative to
the dataset root and the file bytes, uses the `dataset-tree-sha256-v1` contract,
rejects symlinks, and excludes no files from those trees. Copying a dataset
preserves this identity; moving it to a different absolute path does not alter
the digest. The absolute `dataset.root` remains a locator for the collection
host, not the portable ID. `meta_info_sha256` separately binds the exact
`meta/info.json` bytes. When no native repo ID is present in metadata, check the
dataset directory and LeRobot output before using a native ID in later
commands.

## Safe workflow

From the LaundryBench project root, start with the JSON dry run:

```bash
python scripts/record.py --config configs/recording.example.yaml
```

The example config is deliberately separate from mock-first `robot.yaml` and
`camera.yaml`. Replace its ports, IDs, calibration paths, camera profile, local
dataset root, manifest path, and LeRobot Python with values observed on the
target host. Paths in the config are resolved relative to the config file.
The manifest is stored at the explicit `dataset.manifest_path`, outside the
dataset root in the example.

The default command only prints JSON argv and writes a `planned` manifest. It
does not probe or import LeRobot, enumerate cameras, open serial ports, create a
LeRobot dataset, or upload anything. The argv uses `shell=False`, explicit
SO-101 device types and roles, distinct ports and calibration IDs, a named
camera profile, an explicit root, episode and time bounds, one task string,
`--robot.use_degrees=false`, `--teleop.use_degrees=false`,
an explicit `--dataset.fps`, `--dataset.push_to_hub=false`, and
`--resume=false`. The configured `camera.fps` is the acquisition rate and must
be at least the recording/control rate `dataset.fps`; both rates are recorded
separately.

After reviewing the printed target, only an operator physically present with
the follower and stop access should use:

```bash
python scripts/record.py --config configs/recording.local.yaml --execute --supervised
```

Before starting LeRobot, the adapter checks that both selected calibration
files are readable nonempty JSON objects at the role-specific lookup path under
the configured `lerobot.home`, and that their filename stems exactly match the
configured IDs. `HF_LEROBOT_HOME`, when set, must resolve to that same path;
the child receives the configured value. The adapter also requires the selected
Python to report LeRobot 0.6.1 and the versioned recording module to be
import-discoverable. It does not run calibration. If LeRobot nevertheless
signals a missing or invalid calibration, stop the recording session and
resolve the device ID or calibration cache; do not accept a calibration flow.
Execution also requires an interactive foreground terminal. On POSIX hosts the
child runs in a separate process group that temporarily takes the terminal so
LeRobot's keyboard controls work; Ctrl-C reaches the recording process, and
SIGTERM to the wrapper stops the child group and restores terminal ownership.

The adapter refuses an existing dataset root and will not resume or overwrite
one. It creates an atomic lifecycle manifest with `planned`, `running`,
`completed`, or `failed` status, exact device IDs and ports, selected Python
version, root, command argv, and exit status. Ctrl-C terminates the launched
process group and records a failed/interrupted status. The completed manifest
also stores SHA-256 of `meta/info.json` so later training can bind to the exact
dataset schema used for the ACT contract. A zero exit code means
the recorder returned successfully; it does not establish that an episode was
good or that the task physically succeeded.

On a completed recording, the adapter reads only `meta/info.json` and records
an ACT input/output contract when native state and action names normalize to the
six SO-101 joints in order, feature shapes and float type agree, metadata FPS
matches `dataset.fps`, and the configured camera feature has the requested RGB
dimensions. Native names such as `shoulder_pan.pos` are preserved verbatim in
`state.names` and `action.names`; `canonical_joint_names` maps only exact bare
or `.pos` aliases for the six known joints to the canonical LaundryBench names.
Unknown names, duplicates, or reordering invalidate the contract.
The requested RGB color mode is explicit in the command; LeRobot's info schema
does not guarantee channel order as a metadata field. Units are copied only
when the dataset metadata provides a matching units list;
the command explicitly configures `use_degrees=false` independently on the
follower and leader. Missing or inconsistent metadata leaves the contract
unvalidated and records why. Camera
content-to-name correctness, calibration quality, dropped frames, episode
outcome, and physical success still require operator inspection.

## Validation boundary

Tests use temporary config and metadata fixtures plus an injected fake process
and version probe. They do not import LeRobot or connect to hardware. The
example calibration paths are placeholders and are not a claim that a robot,
camera, calibration, or LeRobot environment is ready on a particular host.
