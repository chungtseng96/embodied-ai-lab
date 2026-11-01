"""Create deterministic local browser-acceptance artifacts and serve the real app."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import threading
from pathlib import Path

from laundrybench.web import create_server

RUN_IDS = ("exp-e2e-alpha", "exp-e2e-beta")


def write_fixture(outputs_root: Path) -> None:
    outputs_root.mkdir(parents=True, exist_ok=True)
    for run_id in RUN_IDS:
        run = outputs_root / run_id
        run.mkdir(parents=True, exist_ok=True)
        if (run / "episodes.jsonl").exists():
            continue
        (run / "manifest.yaml").write_text(
            f"experiment_id: {run_id}\nrobot_implementation: MockRobot\n"
            "policy_implementation: MockPolicy\npolicy_name: MockPolicy\n"
            "execution_mode: synthetic\nseed: 37\n",
            encoding="utf-8",
        )
        records = [
            {"episode_id": "episode-001", "success": True, "duration_s": 2.0,
             "intervention": False, "failure_category": None},
            {"episode_id": "episode-002", "success": False, "duration_s": 3.0,
             "intervention": False, "failure_category": "timeout"},
            {"episode_id": "episode-003", "success": True, "duration_s": 4.0,
             "intervention": False, "failure_category": None},
        ]
        (run / "episodes.jsonl").write_text(
            "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
            encoding="utf-8",
        )
        (run / "labels.json").write_text(
            json.dumps({"schema_version": 2, "revision": 0, "labels": {}}) + "\n",
            encoding="utf-8",
        )
        (run / "experiment.json").write_text(json.dumps({
            "schema_version": 1,
            "revision": 0,
            "name": run_id,
            "hypothesis": "Controlled fixture for browser acceptance",
            "what_changed": "Protocol version differs between fixture runs",
            "task": {"id": "laundry-sort", "version": "1"},
            "protocol": {
                "id": "manual-review",
                "version": "2" if run_id == "exp-e2e-beta" else "1",
            },
            "dataset": {"id": "synthetic-fixture", "revision": "1"},
            "checkpoint": {"identity": "fixture-policy-v1"},
            "effective_overrides": {},
            "evidence_links": [],
        }, sort_keys=True) + "\n", encoding="utf-8")
        traces = run / "traces"
        traces.mkdir(exist_ok=True)
        trace_steps = []
        for episode_id in (record["episode_id"] for record in records):
            for step in range(4):
                trace_steps.append({
                    "episode_id": episode_id,
                    "step": step,
                    "timestamp_s": 100.0 + step * 0.25,
                    "joint_positions": [step * 0.1] * 6,
                    "joint_targets": [step * 0.12] * 6,
                })
        (traces / "steps.jsonl").write_text(
            "".join(json.dumps(step, sort_keys=True) + "\n" for step in trace_steps),
            encoding="utf-8",
        )
        media_dir = run / "media" / "episode-001"
        media_dir.mkdir(parents=True, exist_ok=True)
        video = media_dir / "front.mp4"
        if not video.exists():
            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                raise RuntimeError("ffmpeg is required to create the acceptance fixture video")
            subprocess.run(
                [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                 "-f", "lavfi", "-i", "color=c=blue:s=160x120:r=10:d=1.2",
                 "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)],
                check=True,
            )
        (media_dir / "media.json").write_text(json.dumps({
            "schema_version": 1,
            "episode_id": "episode-001",
            "streams": [{
                "camera": "front",
                "path": "media/episode-001/front.mp4",
                "mime_type": "video/mp4",
                "duration_s": 1.2,
                "trace_start_s": 99.5,
            }],
            "events": [{"name": "grasp", "timestamp_s": 100.0}],
        }, sort_keys=True) + "\n", encoding="utf-8")
        corrupt_dir = run / "media" / "episode-003"
        corrupt_dir.mkdir(parents=True, exist_ok=True)
        (corrupt_dir / "corrupt.mp4").write_bytes(b"not a valid MP4 container")
        (corrupt_dir / "media.json").write_text(json.dumps({
            "schema_version": 1,
            "episode_id": "episode-003",
            "streams": [{
                "camera": "front",
                "path": "media/episode-003/corrupt.mp4",
                "mime_type": "video/mp4",
                "duration_s": 1.0,
                "trace_start_s": 99.5,
            }],
            "events": [],
        }, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outputs-root", type=Path, required=True)
    parser.add_argument("--frontend-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    write_fixture(args.outputs_root)
    server = create_server(args.outputs_root, args.frontend_dir, port=args.port)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"http://127.0.0.1:{server.server_port}", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
