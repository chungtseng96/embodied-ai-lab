# Episode media contract

**Date:** 2026-11-01  
**Status:** Implemented software contract; physical timing validation pending  
**Owner:** LaundryBench

LaundryBench may attach locally recorded camera files to existing run episodes
without taking over capture. LeRobot remains responsible for recording and
exporting camera data. `scripts/import_media.py` copies explicitly selected
recordings into a run artifact; it does not open cameras, start recording, or
operate hardware.

## Layout and schema

Each episode may have a sidecar at `media/<episode_id>/media.json`:

```json
{
  "schema_version": 1,
  "episode_id": "episode-0001",
  "streams": [
    {
      "camera": "observation.images.front",
      "path": "media/episode-0001/front.mp4",
      "mime_type": "video/mp4",
      "duration_s": 18.4,
      "trace_start_s": 1793520123.25
    }
  ],
  "events": [
    {"name": "grasp", "timestamp_s": 1793520128.1}
  ]
}
```

`streams` is allowed to be empty. Every stream names the recorded camera slot,
uses a run-root-relative POSIX path, and declares a positive video duration.
The supported media types are MP4 and WebM (`video/mp4`, `video/webm`). Paths
must stay inside the run directory and may not traverse symlinks.

`trace_start_s` is an absolute host-clock timestamp: it is the trace timestamp
that corresponds to video offset zero. Alignment is therefore
`trace_time_s = video_time_s + trace_start_s`. The offset must come from the
recorded artifacts or explicit operator input; this contract does not claim
physical synchronization or verify that two clocks were synchronized.

`events` contains only explicitly recorded markers. Each marker has a name and
an absolute trace/host timestamp. No event timestamps are inferred from video,
trace shape, or episode outcomes. A marker may fall outside one camera's clip;
clients can omit it from that camera's visible interval.

## Importing an existing recording

For example, register an existing LeRobot export with:

```sh
python projects/laundrybench/scripts/import_media.py \
  --run-root /absolute/path/to/outputs/run-001 \
  --episode-id episode-0001 \
  --camera observation.images.front \
  --source /absolute/path/to/recordings/episode-0001.mp4 \
  --duration-s 18.4 \
  --trace-start-s 1793520123.25
```

`--trace-start-s` must be the recorded host timestamp aligned to video time
zero. Repeat `--event NAME=TRACE_TIMESTAMP_S` only for markers recorded
elsewhere. Existing streams and events are preserved, and supplied markers are
appended. A camera collision fails unless `--replace` is passed. The importer
does not serialize concurrent invocations; run one import at a time per run.
Videos remain run artifacts and must not be committed to git.

## Validation and serving

`read_episode_media(run_root, episode_id)` returns a validated v1 manifest. If
the sidecar is absent it returns an empty manifest, matching episodes without
video. A malformed sidecar or missing/unsafe referenced file is an artifact
error; an API can report that error explicitly to the operator. `resolve_episode_media`
resolves a requested camera only after loading and validating its manifest.
`parse_byte_range` and `copy_byte_range` support a single HTTP byte range so
browsers can seek without downloading the complete recording.

The loopback API exposes `GET /api/runs/{run}/episodes/{episode}/media` for the
manifest. Each stream includes a camera URL at
`/api/runs/{run}/episodes/{episode}/media/{camera}`. Media GET requests support
full responses and a single `Range` request, including open and suffix forms;
valid ranges return HTTP 206 and unsatisfiable single ranges return HTTP 416
with `Content-Range: bytes */<size>`. HEAD ignores `Range` and returns full
representation headers without a body. Unsupported multi-range requests,
unknown range units, and `If-Range` requests fall back to a full HTTP 200
response because the service does not emit validators. A missing sidecar yields
an empty manifest; unknown episodes/cameras return 404 and malformed or unsafe
media artifacts return 422.

Validation checks schema fields, timestamps, duration, extension/MIME pairing,
file existence, path confinement, and symlink boundaries. It does not inspect
container headers, decode frames, verify codecs, or establish trace/video
physical synchronization. Importing copies bytes without claiming the source
contains a valid or playable video. Codec validation requires a separate media
tool and is outside the standard-library contract.
