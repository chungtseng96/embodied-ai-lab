"""Versioned references to recorded episode media.

This module validates the media metadata and keeps every referenced file inside
the run directory. It deliberately does not decode or otherwise validate video
codecs; that requires an installed media toolchain.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path, PurePosixPath
from typing import BinaryIO

SCHEMA_VERSION = 1
MIME_BY_SUFFIX = {".mp4": "video/mp4", ".webm": "video/webm"}
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,199}\Z")
_CAMERA = re.compile(r"[A-Za-z0-9][A-Za-z0-9_. -]{0,99}\Z")


class MediaError(ValueError):
    """Invalid or unsafe media metadata or reference."""


def _finite_number(value: object, field: str) -> float:
    try:
        valid = type(value) in (int, float) and math.isfinite(value)
    except OverflowError as error:
        raise MediaError(f"{field} must be a finite number") from error
    if not valid:
        raise MediaError(f"{field} must be a finite number")
    return float(value)


def _run_root(run_root: Path) -> Path:
    root = Path(run_root).resolve(strict=True)
    if not root.is_dir():
        raise MediaError("run root must be a directory")
    return root


def _resolve_relative_media(run_root: Path, relative_path: str) -> Path:
    """Resolve one run-root-relative media path, rejecting traversal/symlinks."""
    root = _run_root(run_root)
    if not isinstance(relative_path, str) or not relative_path:
        raise MediaError("media path must be a non-empty relative path")
    relative = PurePosixPath(relative_path)
    if relative.is_absolute() or any(part in ("", ".", "..") for part in relative.parts):
        raise MediaError("media path must be a confined relative POSIX path")
    if "\\" in relative_path or ":" in relative_path:
        raise MediaError("media path must use POSIX path components")
    suffix = Path(relative.name).suffix.lower()
    if suffix not in MIME_BY_SUFFIX:
        raise MediaError("media path must use an MP4 or WebM extension")

    path = root
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            raise MediaError("symlink media references are not supported")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise MediaError("media file is missing or inaccessible") from error
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise MediaError("media file is missing or outside the run root")
    if resolved.stat().st_size <= 0:
        raise MediaError("media file is empty")
    return resolved


def resolve_media(run_root: Path, episode_id: str, camera: str) -> Path:
    """Resolve a camera through its validated episode manifest (route helper)."""
    manifest = read_episode_media(run_root, episode_id)
    for stream in manifest["streams"]:
        if stream["camera"] == camera:
            return _resolve_relative_media(run_root, stream["path"])
    raise MediaError("camera media not found")


def resolve_episode_media(run_root: Path, episode_id: str, camera: str) -> Path:
    """Named alias for :func:`resolve_media`."""
    return resolve_media(run_root, episode_id, camera)


def _validate_manifest(run_root: Path, episode_id: str, value: object) -> dict:
    if not _ID.fullmatch(episode_id):
        raise MediaError("invalid episode id")
    if not isinstance(value, dict) or set(value) - {
        "schema_version",
        "episode_id",
        "streams",
        "events",
    }:
        raise MediaError("invalid media manifest fields")
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or type(value.get("schema_version")) is not int
    ):
        raise MediaError("unsupported media schema version")
    if value.get("episode_id") != episode_id:
        raise MediaError("media manifest episode id does not match")
    streams = value.get("streams")
    if not isinstance(streams, list):
        raise MediaError("media streams must be a list")
    cameras: set[str] = set()
    normalized_streams = []
    for stream in streams:
        required = {"camera", "path", "mime_type", "duration_s", "trace_start_s"}
        if not isinstance(stream, dict) or set(stream) != required:
            raise MediaError("invalid media stream fields")
        camera, path, mime_type = stream["camera"], stream["path"], stream["mime_type"]
        if not isinstance(camera, str) or not _CAMERA.fullmatch(camera) or camera in cameras:
            raise MediaError("camera names must be valid and unique per episode")
        cameras.add(camera)
        resolved = _resolve_relative_media(run_root, path)
        expected_mime = MIME_BY_SUFFIX[resolved.suffix.lower()]
        if mime_type != expected_mime:
            raise MediaError("media MIME type does not match its allowlisted extension")
        duration = _finite_number(stream["duration_s"], "duration_s")
        trace_start = _finite_number(stream["trace_start_s"], "trace_start_s")
        if duration <= 0:
            raise MediaError("duration_s must be positive")
        normalized_streams.append(
            {
                "camera": camera,
                "path": PurePosixPath(path).as_posix(),
                "mime_type": mime_type,
                "duration_s": duration,
                "trace_start_s": trace_start,
            }
        )

    events = value.get("events", [])
    if not isinstance(events, list):
        raise MediaError("media events must be a list")
    normalized_events = []
    for event in events:
        if not isinstance(event, dict) or set(event) != {"name", "timestamp_s"}:
            raise MediaError("events require exactly name and timestamp_s")
        if not isinstance(event["name"], str) or not event["name"].strip():
            raise MediaError("event name must be a non-empty string")
        normalized_events.append(
            {
                "name": event["name"],
                "timestamp_s": _finite_number(event["timestamp_s"], "timestamp_s"),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "episode_id": episode_id,
        "streams": normalized_streams,
        "events": normalized_events,
    }


def read_episode_media(run_root: Path, episode_id: str) -> dict:
    """Read and validate ``media/<episode_id>/media.json``.

    A missing sidecar is represented as an empty v1 manifest. Metadata checks
    include file existence and confinement, but do not validate video contents.
    """
    root = _run_root(run_root)
    if not isinstance(episode_id, str) or not _ID.fullmatch(episode_id):
        raise MediaError("invalid episode id")
    manifest_path = root / "media" / episode_id / "media.json"
    for part in (root / "media", root / "media" / episode_id, manifest_path):
        if part.is_symlink():
            raise MediaError("symlink media manifests are not supported")
    if not manifest_path.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "episode_id": episode_id,
            "streams": [],
            "events": [],
        }
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MediaError("media manifest is missing or invalid JSON") from error
    return _validate_manifest(root, episode_id, value)


def parse_byte_range(header: str, size: int) -> tuple[int, int]:
    """Parse one HTTP byte range and return inclusive ``(start, end)`` offsets."""
    if type(size) is not int or size < 0:
        raise MediaError("invalid media size")
    if not isinstance(header, str) or not header.startswith("bytes=") or "," in header:
        raise MediaError("only one byte range is supported")
    spec = header[6:].strip()
    match = re.fullmatch(r"(\d*)-(\d*)", spec)
    if not match or not any(match.groups()) or size == 0:
        raise MediaError("invalid byte range")
    first, last = match.groups()
    try:
        if not first:
            suffix = int(last)
            if suffix <= 0:
                raise MediaError("invalid suffix byte range")
            return max(0, size - suffix), size - 1
        start = int(first)
        end = min(int(last), size - 1) if last else size - 1
    except ValueError as error:
        raise MediaError("invalid byte range") from error
    if start >= size or end < start:
        raise MediaError("unsatisfiable byte range")
    return start, end


def trace_time_for_video_time(
    video_time_s: float, trace_start_s: float, duration_s: float
) -> float:
    """Map a video offset into trace host time, rejecting offsets outside the clip."""
    video_time = _finite_number(video_time_s, "video_time_s")
    trace_start = _finite_number(trace_start_s, "trace_start_s")
    duration = _finite_number(duration_s, "duration_s")
    if duration <= 0 or not 0 <= video_time <= duration:
        raise MediaError("video_time_s must fall within the media duration")
    return video_time + trace_start


def video_time_for_trace_time(
    trace_time_s: float, trace_start_s: float, duration_s: float
) -> float | None:
    """Map host/trace time into video offset; return None outside the clip."""
    trace_time = _finite_number(trace_time_s, "trace_time_s")
    trace_start = _finite_number(trace_start_s, "trace_start_s")
    duration = _finite_number(duration_s, "duration_s")
    if duration <= 0:
        raise MediaError("duration_s must be positive")
    video_time = trace_time - trace_start
    return video_time if 0 <= video_time <= duration else None


def copy_byte_range(
    source: BinaryIO, sink: BinaryIO, start: int, end: int, chunk_size: int = 64 * 1024
) -> None:
    """Copy an inclusive byte range from a seekable source in bounded chunks."""
    if type(start) is not int or type(end) is not int or start < 0 or end < start:
        raise MediaError("invalid byte range offsets")
    if type(chunk_size) is not int or chunk_size <= 0:
        raise MediaError("chunk_size must be positive")
    source.seek(start)
    remaining = end - start + 1
    while remaining:
        chunk = source.read(min(chunk_size, remaining))
        if not chunk:
            raise MediaError("media file changed while streaming")
        sink.write(chunk)
        remaining -= len(chunk)
