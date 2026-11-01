"""Register a previously recorded local MP4/WebM file for one run episode."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from laundrybench.evaluation.media import (
    MIME_BY_SUFFIX,
    SCHEMA_VERSION,
    MediaError,
    read_episode_media,
    trace_time_for_video_time,
)


def _sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _episode_ids(run_root: Path) -> set[str]:
    path = run_root / "episodes.jsonl"
    try:
        records = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as error:
        raise MediaError("run has missing or invalid episodes.jsonl") from error
    values = [record.get("episode_id") for record in records if isinstance(record, dict)]
    if len(values) != len(records) or not all(isinstance(item, str) for item in values):
        raise MediaError("run has invalid episode evidence")
    return set(values)


def import_media(
    run_root: Path,
    episode_id: str,
    camera: str,
    source: Path,
    duration_s: float,
    trace_start_s: float,
    *,
    events: list[dict] | None = None,
    replace: bool = False,
) -> dict:
    """Copy explicit user-selected media into a run and register its metadata."""
    root = Path(run_root).resolve(strict=True)
    if not isinstance(episode_id, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]{0,199}", episode_id
    ):
        raise MediaError("invalid episode id")
    if not root.is_dir() or episode_id not in _episode_ids(root):
        raise MediaError("episode id is not present in this run")
    source = Path(source).resolve(strict=True)
    if not source.is_file() or source.suffix.lower() not in MIME_BY_SUFFIX:
        raise MediaError("source must be a local MP4 or WebM file")
    if not camera or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_. -]{0,99}", camera):
        raise MediaError("invalid camera name")
    if not isinstance(duration_s, (int, float)) or isinstance(duration_s, bool) or duration_s <= 0:
        raise MediaError("duration must be positive")
    if not isinstance(trace_start_s, (int, float)) or isinstance(trace_start_s, bool):
        raise MediaError("trace start must be a host-clock timestamp")
    # Validate finite numbers and the explicit t_video=0 clock anchor.
    trace_time_for_video_time(0, trace_start_s, duration_s)

    media_root = root / "media"
    sidecar_dir = media_root / episode_id
    for directory in (media_root, sidecar_dir):
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            raise MediaError("episode media directory is unsafe")
        if not directory.resolve().is_relative_to(root):
            raise MediaError("episode media directory escapes the run root")
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = sidecar_dir / "media.json"
    if manifest_path.is_symlink() or (manifest_path.exists() and not manifest_path.is_file()):
        raise MediaError("symlink media manifests are not supported")
    manifest = read_episode_media(root, episode_id)
    existing = next((stream for stream in manifest["streams"] if stream["camera"] == camera), None)
    if existing and not replace:
        raise MediaError("camera already has media; pass --replace to replace it")

    safe_camera = re.sub(r"[^A-Za-z0-9_-]+", "_", camera).strip("_") or "camera"
    source_digest = _sha256(source)
    fd, staged_media_name = tempfile.mkstemp(
        prefix=".media-source-", suffix=source.suffix.lower(), dir=sidecar_dir
    )
    staged_manifest_name: str | None = None
    try:
        with os.fdopen(fd, "wb") as staged, source.open("rb") as incoming:
            shutil.copyfileobj(incoming, staged)
            staged.flush()
            os.fsync(staged.fileno())
        staged_path = Path(staged_media_name)
        staged_size = staged_path.stat().st_size
        if staged_size == 0:
            raise MediaError("source media file is empty")
        if _sha256(staged_path) != source_digest:
            raise MediaError("source media changed while it was being imported")
        filename = f"{safe_camera}-{source_digest[:16]}{source.suffix.lower()}"
        relative_path = f"media/{episode_id}/{filename}"
        target = sidecar_dir / filename
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise MediaError("media target must be a regular non-symlink file")
        updated = {
            "schema_version": SCHEMA_VERSION,
            "episode_id": episode_id,
            "streams": [stream for stream in manifest["streams"] if stream["camera"] != camera]
            + [
                {
                    "camera": camera,
                    "path": relative_path,
                    "mime_type": MIME_BY_SUFFIX[source.suffix.lower()],
                    "duration_s": float(duration_s),
                    "trace_start_s": float(trace_start_s),
                }
            ],
            "events": manifest["events"] + (events or []),
        }
        # Validate complete metadata against the staged bytes before replacing
        # any previously registered media. The final path is substituted after.
        from laundrybench.evaluation.media import _validate_manifest

        staged_relative = f"media/{episode_id}/{staged_path.name}"
        updated["streams"][-1]["path"] = staged_relative
        updated = _validate_manifest(root, episode_id, updated)
        updated["streams"][-1]["path"] = relative_path
        manifest_fd, staged_manifest_name = tempfile.mkstemp(
            prefix=".media-manifest-", dir=sidecar_dir
        )
        with os.fdopen(manifest_fd, "w", encoding="utf-8") as staged_manifest:
            json.dump(updated, staged_manifest, indent=2, allow_nan=False)
            staged_manifest.write("\n")
            staged_manifest.flush()
            os.fsync(staged_manifest.fileno())
        if target.exists():
            # Content-addressed targets are immutable. Reusing identical bytes
            # avoids replacing an artifact an older sidecar may still cite.
            if _sha256(target) != source_digest:
                raise MediaError("content-addressed media target has unexpected bytes")
        else:
            os.replace(staged_media_name, target)
            staged_media_name = ""
        os.replace(staged_manifest_name, manifest_path)
        staged_manifest_name = None
    finally:
        if staged_media_name and os.path.exists(staged_media_name):
            os.unlink(staged_media_name)
        if staged_manifest_name and os.path.exists(staged_manifest_name):
            os.unlink(staged_manifest_name)
    return updated


def _event(value: str) -> dict:
    try:
        name, timestamp = value.rsplit("=", 1)
        return {"name": name, "timestamp_s": float(timestamp)}
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError("events use NAME=TRACE_TIMESTAMP_S") from None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-root", type=Path, required=True, help="existing run output directory"
    )
    parser.add_argument("--episode-id", required=True)
    parser.add_argument("--camera", required=True, help="recorded camera slot/name")
    parser.add_argument(
        "--source", type=Path, required=True, help="existing local .mp4 or .webm file"
    )
    parser.add_argument("--duration-s", type=float, required=True, help="recorded video duration")
    parser.add_argument(
        "--trace-start-s",
        type=float,
        required=True,
        help="absolute host timestamp corresponding to video time 0",
    )
    parser.add_argument(
        "--event",
        type=_event,
        action="append",
        default=None,
        help="explicitly recorded marker NAME=TRACE_TIMESTAMP_S; may be repeated",
    )
    parser.add_argument(
        "--replace", action="store_true", help="replace media already registered for this camera"
    )
    args = parser.parse_args()
    try:
        result = import_media(
            args.run_root,
            args.episode_id,
            args.camera,
            args.source,
            args.duration_s,
            args.trace_start_s,
            events=args.event,
            replace=args.replace,
        )
    except (MediaError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
