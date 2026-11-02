from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from laundrybench.evaluation.capture import (
    CameraVideoSpec,
    CaptureError,
    EpisodeCapture,
    _rgb_bytes,
)
from laundrybench.evaluation.media import read_episode_media
from laundrybench.types import Observation


def observation(timestamp_s: float, *, value: int = 10) -> Observation:
    return Observation(
        timestamp_s=timestamp_s,
        joint_positions=[0.0] * 6,
        images={"observation.images.front": np.full((8, 8, 3), value, dtype=np.uint8)},
    )


def recorder(run_root: Path, **kwargs) -> EpisodeCapture:
    return EpisodeCapture(
        run_root,
        {"observation.images.front": CameraVideoSpec(width=8, height=8, fps=2)},
        **kwargs,
    )


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is optional")
def test_capture_encodes_observed_frames_and_writes_contract_manifest(tmp_path: Path) -> None:
    capture = recorder(tmp_path, max_clock_error_s=0.001)
    capture.start("episode-real-1")
    for index, timestamp in enumerate((1000.0, 1000.5, 1001.0)):
        capture.observe(observation(timestamp, value=index * 60))
    capture.event("grasp", 1000.75)

    manifest = capture.finalize()
    validated = read_episode_media(tmp_path, "episode-real-1")
    stream = validated["streams"][0]
    video_path = tmp_path / stream["path"]
    assert manifest == validated
    assert stream["camera"] == "observation.images.front"
    assert stream["trace_start_s"] == 1000.0
    assert stream["duration_s"] == 1.5
    assert validated["events"] == [{"name": "grasp", "timestamp_s": 1000.75}]
    assert b"ftyp" in video_path.read_bytes()[:16]
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video_path), "-f", "null", "-"],
        check=True,
        capture_output=True,
    )
    diagnostics = json.loads(
        (tmp_path / "media" / "episode-real-1" / "capture_diagnostics.json").read_text()
    )
    assert diagnostics["status"] == "complete"
    assert diagnostics["clock_source"].startswith("observation.timestamp_s")
    assert diagnostics["streams"][0]["frame_count"] == 3
    assert diagnostics["streams"][0]["max_timestamp_error_s"] == 0


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is optional")
def test_large_rgb_frames_survive_nonblocking_partial_pipe_writes(tmp_path: Path) -> None:
    width, height, fps = 640, 480, 2
    camera = "observation.images.front"
    spec = CameraVideoSpec(width=width, height=height, fps=fps)
    sample = np.full((height, width, 3), 64, dtype=np.uint8)
    payload = _rgb_bytes(sample, spec)
    assert payload.ndim == 1
    assert payload.itemsize == 1
    assert len(payload) == height * width * 3

    capture = EpisodeCapture(
        tmp_path,
        {camera: spec},
        max_clock_error_s=0.001,
    )
    capture.start("episode-large-frames")
    expected_values = (24, 100, 212)
    for index, value in enumerate(expected_values):
        frame = np.full((height, width, 3), value, dtype=np.uint8)
        capture.observe(
            Observation(
                timestamp_s=2000.0 + index / fps,
                joint_positions=[0.0] * 6,
                images={camera: frame},
            )
        )
    manifest = capture.finalize()

    video_path = tmp_path / manifest["streams"][0]["path"]
    decoded = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(video_path),
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "pipe:1",
        ],
        check=True,
        capture_output=True,
    ).stdout
    frame_bytes = height * width * 3
    assert len(decoded) == frame_bytes * len(expected_values)
    decoded_frames = np.frombuffer(decoded, dtype=np.uint8).reshape(
        len(expected_values), height, width, 3
    )
    for frame, expected in zip(decoded_frames, expected_values, strict=True):
        assert abs(float(frame.mean()) - expected) < 8
    assert manifest["streams"][0]["duration_s"] == len(expected_values) / fps
    diagnostics = json.loads(
        (tmp_path / "media" / "episode-large-frames" / "capture_diagnostics.json").read_text()
    )
    assert diagnostics["streams"][0]["frame_count"] == len(expected_values)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is optional")
def test_cumulative_timestamp_drift_fails_capture_without_manifest(tmp_path: Path) -> None:
    capture = recorder(tmp_path, max_clock_error_s=0.05)
    capture.start("episode-drift")
    capture.observe(observation(500.0))
    capture.observe(observation(500.5))
    with pytest.raises(CaptureError, match="clock error budget"):
        capture.observe(observation(501.2))

    directory = tmp_path / "media" / "episode-drift"
    assert not (directory / "media.json").exists()
    assert not list(directory.glob("*.mp4"))
    diagnostic = json.loads((directory / "capture_diagnostics.json").read_text())
    assert diagnostic["status"] == "failed"
    assert "clock error budget" in diagnostic["error"]
    assert diagnostic["streams"][0]["frame_count"] == 2


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is optional")
def test_non_monotonic_timestamp_and_frame_limits_are_recorded_as_errors(tmp_path: Path) -> None:
    capture = recorder(tmp_path, max_frames=1)
    capture.start("episode-limit")
    capture.observe(observation(2.0))
    with pytest.raises(CaptureError, match="maximum frame count"):
        capture.observe(observation(2.5))
    diagnostic = json.loads(
        (tmp_path / "media" / "episode-limit" / "capture_diagnostics.json").read_text()
    )
    assert diagnostic["status"] == "failed"
    assert diagnostic["streams"][0]["frame_count"] == 1


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is optional")
def test_invalid_frame_and_duplicate_timestamps_stop_encoder_and_leave_diagnostic(
    tmp_path: Path,
) -> None:
    capture = recorder(tmp_path)
    capture.start("episode-invalid")
    capture.observe(observation(10.0))
    with pytest.raises(CaptureError, match="strictly increasing"):
        capture.observe(observation(10.0))
    data = json.loads(
        (tmp_path / "media" / "episode-invalid" / "capture_diagnostics.json").read_text()
    )
    assert "strictly increasing" in data["error"]
    assert not capture.active

    bad = recorder(tmp_path)
    bad.start("episode-bad-frame")
    frame = observation(12.0)
    frame.images["observation.images.front"] = np.zeros((8, 8, 4), dtype=np.uint8)
    with pytest.raises(CaptureError, match="must have shape"):
        bad.observe(frame)
    assert not (tmp_path / "media" / "episode-bad-frame" / "media.json").exists()


def test_start_failure_does_not_leave_encoder_or_success_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("laundrybench.evaluation.capture.shutil.which", lambda _: "/fake/ffmpeg")
    def fail_to_spawn(*args, **kwargs):
        raise OSError("synthetic ffmpeg launch failure")

    capture = recorder(tmp_path, popen=fail_to_spawn)
    with pytest.raises(CaptureError, match="could not start ffmpeg"):
        capture.start("episode-spawn-failure")

    diagnostic = json.loads(
        (tmp_path / "media" / "episode-spawn-failure" / "capture_diagnostics.json").read_text()
    )
    assert diagnostic["status"] == "failed"
    assert "synthetic ffmpeg launch failure" in diagnostic["error"]
    assert not (tmp_path / "media" / "episode-spawn-failure" / "media.json").exists()


def test_camera_geometry_and_capture_bounds_are_explicit() -> None:
    with pytest.raises(ValueError, match="even"):
        CameraVideoSpec(width=7, height=8, fps=10)
    with pytest.raises(ValueError, match="max_frames"):
        recorder(Path("/tmp/not-created"), max_frames=0)
