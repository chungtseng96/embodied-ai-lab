"""Bounded-memory camera capture for real evaluation observations.

This adapter consumes the same observations delivered to a policy. It does not
open a camera or operate a robot. Video is encoded incrementally by ffmpeg and
registered only after every configured stream has closed successfully.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import select
import shutil
import subprocess
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from laundrybench.evaluation.media import MIME_BY_SUFFIX, read_episode_media
from laundrybench.types import Observation

_EPISODE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,199}\Z")
_CAMERA = re.compile(r"[A-Za-z0-9][A-Za-z0-9_. -]{0,99}\Z")
_MEDIA_SCHEMA_VERSION = 1


class CaptureError(RuntimeError):
    """Capture failed; the episode must not be reported with complete media."""


@dataclass(frozen=True, slots=True)
class CameraVideoSpec:
    """Explicit output geometry and cadence for one observation image key."""

    width: int
    height: int
    fps: int

    def __post_init__(self) -> None:
        if any(
            type(value) is not int or value <= 0
            for value in (self.width, self.height, self.fps)
        ):
            raise ValueError("camera width, height, and fps must be positive integers")
        if self.width % 2 or self.height % 2:
            raise ValueError("camera width and height must be even for browser-compatible H.264")


@dataclass(frozen=True, slots=True)
class StreamCaptureStats:
    camera: str
    frame_count: int
    expected_fps: int
    max_timestamp_error_s: float


class _FFmpegStream:
    def __init__(
        self,
        *,
        camera: str,
        spec: CameraVideoSpec,
        temporary_path: Path,
        ffmpeg: str,
        write_timeout_s: float,
        popen: Callable[..., Any],
    ) -> None:
        self.camera = camera
        self.spec = spec
        self.temporary_path = temporary_path
        self.write_timeout_s = write_timeout_s
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pixel_format",
            "rgb24",
            "-video_size",
            f"{spec.width}x{spec.height}",
            "-framerate",
            str(spec.fps),
            "-i",
            "pipe:0",
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-f",
            "mp4",
            str(temporary_path),
        ]
        try:
            self.process = popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                bufsize=0,
            )
        except OSError as error:
            raise CaptureError(f"could not start ffmpeg for camera {camera!r}: {error}") from error
        if self.process.stdin is None:
            self.process.kill()
            self.process.wait(timeout=write_timeout_s)
            raise CaptureError(f"ffmpeg did not provide an input pipe for camera {camera!r}")
        try:
            os.set_blocking(self.process.stdin.fileno(), False)
        except OSError as error:
            self.process.kill()
            self.process.wait(timeout=write_timeout_s)
            raise CaptureError(f"could not configure ffmpeg input for camera {camera!r}") from error
        self.frame_count = 0
        self.max_timestamp_error_s = 0.0
        self.start_timestamp_s: float | None = None

    def timestamp_error(self, timestamp_s: float) -> float:
        if self.start_timestamp_s is None:
            return 0.0
        expected = self.start_timestamp_s + self.frame_count / self.spec.fps
        return abs(timestamp_s - expected)

    def write(self, frame: Any, timestamp_s: float) -> None:
        payload = _rgb_bytes(frame, self.spec)
        if self.start_timestamp_s is None:
            self.start_timestamp_s = timestamp_s
        error = self.timestamp_error(timestamp_s)
        self.max_timestamp_error_s = max(self.max_timestamp_error_s, error)
        _write_bounded(self.process, payload, self.write_timeout_s, self.camera)
        self.frame_count += 1

    def finish(self) -> None:
        if self.process.stdin is not None and not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            return_code = self.process.wait(timeout=self.write_timeout_s)
        except subprocess.TimeoutExpired as error:
            self.process.kill()
            try:
                self.process.wait(timeout=self.write_timeout_s)
            except subprocess.TimeoutExpired:
                raise CaptureError(
                    f"ffmpeg could not be reaped for camera {self.camera!r}"
                ) from error
            raise CaptureError(
                f"ffmpeg timed out while finalizing camera {self.camera!r}"
            ) from error
        if return_code != 0:
            raise CaptureError(
                f"ffmpeg exited with status {return_code} for camera {self.camera!r}"
            )

    def abort(self) -> None:
        if self.process.poll() is None:
            try:
                self.process.kill()
            finally:
                try:
                    self.process.wait(timeout=self.write_timeout_s)
                except subprocess.TimeoutExpired as error:
                    raise CaptureError(
                        f"ffmpeg could not be reaped for camera {self.camera!r}"
                    ) from error
        if self.process.stdin is not None and not self.process.stdin.closed:
            self.process.stdin.close()


def _rgb_bytes(frame: Any, spec: CameraVideoSpec) -> memoryview:
    """Return one tightly packed RGB frame without retaining prior observations."""
    try:
        import numpy as np
    except ImportError as error:  # pragma: no cover - project runtime dependency is optional
        raise CaptureError("numpy is required to encode observation image arrays") from error
    try:
        array = np.asarray(frame)
        if array.ndim != 3 or array.shape != (spec.height, spec.width, 3):
            raise CaptureError(
                f"camera frame must have shape {(spec.height, spec.width, 3)}, got {array.shape}"
            )
        if array.dtype != np.uint8:
            raise CaptureError(f"camera frame must use uint8 pixels, got {array.dtype}")
        return memoryview(np.ascontiguousarray(array)).cast("B")
    except (TypeError, ValueError) as error:
        if isinstance(error, CaptureError):
            raise
        raise CaptureError("camera frame cannot be converted to a uint8 RGB array") from error


def _write_bounded(process: Any, payload: memoryview, timeout_s: float, camera: str) -> None:
    pipe = process.stdin
    deadline = time.monotonic() + timeout_s
    offset = 0
    fd = pipe.fileno()
    while offset < len(payload):
        if process.poll() is not None:
            raise CaptureError(f"ffmpeg stopped while encoding camera {camera!r}")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise CaptureError(f"ffmpeg input stalled for camera {camera!r}")
        _, writable, _ = select.select([], [fd], [], remaining)
        if not writable:
            raise CaptureError(f"ffmpeg input stalled for camera {camera!r}")
        try:
            written = os.write(fd, payload[offset:])
            if written <= 0:
                raise CaptureError(f"ffmpeg accepted no input bytes for camera {camera!r}")
            offset += written
        except BlockingIOError:
            continue
        except BrokenPipeError as error:
            raise CaptureError(f"ffmpeg closed its input for camera {camera!r}") from error


class EpisodeCapture:
    """Capture observation frames into the existing episode media contract.

    ``start`` takes the evaluator's episode ID. Call ``observe`` once for each
    observation that is passed to the policy. Call ``event`` only for markers
    recorded by an explicit source. ``finalize`` publishes the v1 manifest.
    """

    def __init__(
        self,
        run_root: str | Path,
        cameras: Mapping[str, CameraVideoSpec],
        *,
        ffmpeg: str = "ffmpeg",
        write_timeout_s: float = 10.0,
        max_clock_error_s: float = 0.1,
        max_duration_s: float = 300.0,
        max_frames: int = 9000,
        popen: Callable[..., Any] = subprocess.Popen,
    ) -> None:
        self.run_root = Path(run_root).resolve()
        self.cameras = dict(cameras)
        if not self.cameras:
            raise ValueError("at least one named camera is required")
        if any(not isinstance(name, str) or not _CAMERA.fullmatch(name) for name in self.cameras):
            raise ValueError("camera names must follow the episode media contract")
        if len(self.cameras) != len(set(self.cameras)):
            raise ValueError("camera names must be unique")
        if any(not isinstance(spec, CameraVideoSpec) for spec in self.cameras.values()):
            raise ValueError("each camera must have an explicit CameraVideoSpec")
        if len({spec.fps for spec in self.cameras.values()}) != 1:
            raise ValueError("all camera streams must use the same observation cadence")
        if not math.isfinite(write_timeout_s) or write_timeout_s <= 0:
            raise ValueError("write_timeout_s must be finite and positive")
        if not math.isfinite(max_clock_error_s) or max_clock_error_s < 0:
            raise ValueError("max_clock_error_s must be finite and non-negative")
        if not math.isfinite(max_duration_s) or max_duration_s <= 0:
            raise ValueError("max_duration_s must be finite and positive")
        if type(max_frames) is not int or max_frames <= 0:
            raise ValueError("max_frames must be a positive integer")
        executable = shutil.which(ffmpeg)
        if executable is None:
            raise CaptureError(f"ffmpeg executable not found: {ffmpeg}")
        self.ffmpeg = executable
        self.write_timeout_s = write_timeout_s
        self.max_clock_error_s = max_clock_error_s
        self.max_duration_s = max_duration_s
        self.max_frames = max_frames
        self._popen = popen
        self._episode_id: str | None = None
        self._streams: dict[str, _FFmpegStream] = {}
        self._temporary_paths: dict[str, Path] = {}
        self._published_paths: set[Path] = set()
        self._events: list[dict[str, str | float]] = []
        self._last_timestamp_s: float | None = None

    @property
    def active(self) -> bool:
        return self._episode_id is not None

    def start(self, episode_id: str) -> None:
        if self.active:
            raise CaptureError("capture is already active")
        if not isinstance(episode_id, str) or not _EPISODE_ID.fullmatch(episode_id):
            raise ValueError("invalid episode id")
        self.run_root.mkdir(parents=True, exist_ok=True)
        manifest_path = self.run_root / "media" / episode_id / "media.json"
        if manifest_path.exists() or manifest_path.is_symlink():
            raise CaptureError(f"media manifest already exists for episode {episode_id!r}")
        existing = read_episode_media_if_present(self.run_root, episode_id)
        if existing["streams"] or existing["events"]:
            raise CaptureError(f"media already exists for episode {episode_id!r}")
        directory = self.run_root / "media" / episode_id
        directory.mkdir(parents=True, exist_ok=True)
        self._episode_id = episode_id
        self._events = []
        self._last_timestamp_s = None
        self._published_paths = set()
        try:
            for camera, spec in self.cameras.items():
                final_path = self._stream_path(camera)
                temporary = final_path.with_name(f".{final_path.name}.partial")
                if final_path.exists() or temporary.exists():
                    raise CaptureError(f"capture output already exists for camera {camera!r}")
                self._temporary_paths[camera] = temporary
                self._streams[camera] = _FFmpegStream(
                    camera=camera,
                    spec=spec,
                    temporary_path=temporary,
                    ffmpeg=self.ffmpeg,
                    write_timeout_s=self.write_timeout_s,
                    popen=self._popen,
                )
        except BaseException as error:
            self._abort(error=error)
            raise

    def observe(self, observation: Observation) -> None:
        self._require_active()
        try:
            timestamp = _finite_timestamp(observation.timestamp_s)
        except (TypeError, ValueError, OverflowError) as error:
            self._abort(error=error)
            raise
        if self._last_timestamp_s is not None and timestamp <= self._last_timestamp_s:
            error = CaptureError("observation timestamps must be strictly increasing")
            self._abort(error=error)
            raise error
        missing = set(self.cameras) - set(observation.images)
        if missing:
            error = CaptureError(f"observation is missing camera frames: {sorted(missing)}")
            self._abort(error=error)
            raise error
        try:
            for camera, stream in self._streams.items():
                if stream.frame_count >= self.max_frames:
                    raise CaptureError(f"capture exceeded maximum frame count for {camera!r}")
                if stream.frame_count / stream.spec.fps >= self.max_duration_s:
                    raise CaptureError(f"capture exceeded maximum duration for {camera!r}")
                timestamp_error = stream.timestamp_error(timestamp)
                if timestamp_error > self.max_clock_error_s:
                    raise CaptureError(
                        f"camera {camera!r} cadence exceeded clock error budget "
                        f"({timestamp_error:.6f}s > {self.max_clock_error_s:.6f}s)"
                    )
            for camera, stream in self._streams.items():
                stream.write(observation.images[camera], timestamp)
            self._last_timestamp_s = timestamp
        except BaseException as error:
            self._abort(error=error)
            raise

    def event(self, name: str, timestamp_s: float) -> None:
        self._require_active()
        if not isinstance(name, str) or not name.strip():
            raise ValueError("event name must be a non-empty string")
        self._events.append({"name": name, "timestamp_s": _finite_timestamp(timestamp_s)})

    def finalize(self) -> dict:
        episode_id = self._require_active()
        if any(stream.frame_count == 0 for stream in self._streams.values()):
            error = CaptureError("cannot finalize capture without at least one frame per camera")
            self._abort(error=error)
            raise error
        streams = []
        try:
            for camera, stream in self._streams.items():
                if stream.max_timestamp_error_s > self.max_clock_error_s:
                    raise CaptureError(
                        f"camera {camera!r} cadence exceeded clock error budget "
                        f"({stream.max_timestamp_error_s:.6f}s > "
                        f"{self.max_clock_error_s:.6f}s)"
                    )
            for camera, stream in self._streams.items():
                stream.finish()
                temporary = self._temporary_paths[camera]
                final_path = self._stream_path(camera)
                if not temporary.is_file() or temporary.stat().st_size == 0:
                    raise CaptureError(f"ffmpeg produced no video for camera {camera!r}")
                os.replace(temporary, final_path)
                self._published_paths.add(final_path)
                spec = self.cameras[camera]
                streams.append(
                    {
                        "camera": camera,
                        "path": final_path.relative_to(self.run_root).as_posix(),
                        "mime_type": MIME_BY_SUFFIX[final_path.suffix],
                        "duration_s": stream.frame_count / spec.fps,
                        "trace_start_s": stream.start_timestamp_s,
                    }
                )
            manifest = {
                "schema_version": _MEDIA_SCHEMA_VERSION,
                "episode_id": episode_id,
                "streams": streams,
                "events": self._events,
            }
            self._write_diagnostic(
                episode_id,
                {
                    "schema_version": 1,
                    "episode_id": episode_id,
                    "status": "complete",
                    "clock_source": "observation.timestamp_s (host observation time)",
                    "alignment_model": (
                        "fixed_frame_rate; trace_start_s is first observation timestamp"
                    ),
                    "max_clock_error_budget_s": self.max_clock_error_s,
                    "streams": [_stats_json(item) for item in self.stats()],
                },
            )
            manifest_path = self.run_root / "media" / episode_id / "media.json"
            temporary_manifest = manifest_path.with_name(".media.json.partial")
            temporary_manifest.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            os.replace(temporary_manifest, manifest_path)
            return manifest
        except BaseException as error:
            self._abort(error=error)
            raise
        finally:
            if self.active and all(
                stream.process.poll() is not None for stream in self._streams.values()
            ):
                self._clear_state()

    def abort(self, reason: str = "episode ended before capture finalized") -> None:
        """Stop encoders and remove unregistered partial files after an episode failure."""
        self._abort(error=CaptureError(reason))

    def stats(self) -> tuple[StreamCaptureStats, ...]:
        return tuple(
            StreamCaptureStats(
                camera=camera,
                frame_count=stream.frame_count,
                expected_fps=stream.spec.fps,
                max_timestamp_error_s=stream.max_timestamp_error_s,
            )
            for camera, stream in self._streams.items()
        )

    def _stream_path(self, camera: str) -> Path:
        assert self._episode_id is not None
        slug = re.sub(r"[^A-Za-z0-9_-]+", "-", camera).strip("-") or "camera"
        digest = hashlib.sha256(camera.encode("utf-8")).hexdigest()[:8]
        return self.run_root / "media" / self._episode_id / f"{slug[:64]}-{digest}.mp4"

    def _require_active(self) -> str:
        if self._episode_id is None:
            raise CaptureError("no active capture")
        return self._episode_id

    def _abort(self, *, error: BaseException | None = None) -> None:
        episode_id = self._episode_id
        stats = self.stats() if episode_id is not None else ()
        first_error: BaseException | None = None
        for stream in self._streams.values():
            try:
                stream.abort()
            except BaseException as cleanup_error:  # noqa: BLE001 - reap even on interruption
                first_error = first_error or cleanup_error
        for path in self._temporary_paths.values():
            try:
                path.unlink(missing_ok=True)
            except OSError as cleanup_error:
                first_error = first_error or cleanup_error
        if episode_id is not None:
            for path in self._published_paths:
                try:
                    path.unlink(missing_ok=True)
                except OSError as cleanup_error:
                    first_error = first_error or cleanup_error
            manifest = self.run_root / "media" / episode_id / "media.json"
            manifest.unlink(missing_ok=True)
            diagnostic = {
                "schema_version": 1,
                "episode_id": episode_id,
                "status": "failed" if error is not None else "aborted",
                "clock_source": "observation.timestamp_s (host observation time)",
                "error": str(error) if error is not None else "capture aborted",
                "streams": [_stats_json(item) for item in stats],
            }
            self._write_diagnostic(episode_id, diagnostic)
        self._clear_state()
        if first_error is not None:
            raise CaptureError(f"capture cleanup failed: {first_error}") from first_error

    def _clear_state(self) -> None:
        self._episode_id = None
        self._streams = {}
        self._temporary_paths = {}
        self._published_paths = set()
        self._events = []
        self._last_timestamp_s = None

    def _write_diagnostic(self, episode_id: str, payload: dict) -> None:
        path = self.run_root / "media" / episode_id / "capture_diagnostics.json"
        temporary = path.with_name(".capture_diagnostics.json.partial")
        try:
            temporary.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            os.replace(temporary, path)
        except OSError:
            temporary.unlink(missing_ok=True)
            raise


def _finite_timestamp(value: Any) -> float:
    try:
        valid = type(value) in (int, float) and math.isfinite(value)
    except OverflowError as error:
        raise ValueError("timestamp_s must be a finite host-clock number") from error
    if not valid:
        raise ValueError("timestamp_s must be a finite host-clock number")
    return float(value)


def _stats_json(item: StreamCaptureStats) -> dict:
    return {
        "camera": item.camera,
        "frame_count": item.frame_count,
        "expected_fps": item.expected_fps,
        "max_timestamp_error_s": item.max_timestamp_error_s,
    }


def read_episode_media_if_present(run_root: Path, episode_id: str) -> dict:
    """Read an existing sidecar if present without fabricating an empty file."""
    return read_episode_media(run_root, episode_id)
