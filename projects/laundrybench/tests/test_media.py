import hashlib
import io
import json
from pathlib import Path

import pytest

import scripts.import_media as import_media_module
from laundrybench.evaluation.media import (
    MediaError,
    copy_byte_range,
    parse_byte_range,
    read_episode_media,
    resolve_episode_media,
    trace_time_for_video_time,
    video_time_for_trace_time,
)
from scripts.import_media import import_media


def run_with_episode(tmp_path: Path) -> Path:
    run = tmp_path / "run-1"
    run.mkdir()
    (run / "episodes.jsonl").write_text(
        json.dumps({"episode_id": "ep-1", "success": True}) + "\n", encoding="utf-8"
    )
    return run


def test_missing_manifest_returns_empty_versioned_contract(tmp_path: Path) -> None:
    run = run_with_episode(tmp_path)
    assert read_episode_media(run, "ep-1") == {
        "schema_version": 1,
        "episode_id": "ep-1",
        "streams": [],
        "events": [],
    }


def test_import_registers_user_selected_file_and_preserves_explicit_events(tmp_path: Path) -> None:
    run = run_with_episode(tmp_path)
    source = tmp_path / "recording.mp4"
    source.write_bytes(b"fixture bytes; no codec validity implied")
    manifest = import_media(
        run,
        "ep-1",
        "front",
        source,
        4.5,
        1000.25,
        events=[{"name": "grasp", "timestamp_s": 1002.0}],
    )

    assert manifest["streams"] == [
        {
            "camera": "front",
            "path": manifest["streams"][0]["path"],
            "mime_type": "video/mp4",
            "duration_s": 4.5,
            "trace_start_s": 1000.25,
        }
    ]
    assert manifest["streams"][0]["path"].startswith("media/ep-1/front-")
    assert manifest["events"] == [{"name": "grasp", "timestamp_s": 1002.0}]
    assert resolve_episode_media(run, "ep-1", "front").read_bytes() == source.read_bytes()


def test_trace_video_clock_conversion_uses_explicit_offset_and_bounds() -> None:
    # video t=0 is trace host time 1000.25; no physical sync is exercised here.
    assert trace_time_for_video_time(2.0, 1000.25, 4.5) == 1002.25
    assert video_time_for_trace_time(1002.25, 1000.25, 4.5) == 2.0
    assert video_time_for_trace_time(999.0, 1000.25, 4.5) is None
    assert video_time_for_trace_time(1005.0, 1000.25, 4.5) is None
    with pytest.raises(MediaError):
        trace_time_for_video_time(4.6, 1000.25, 4.5)


@pytest.mark.parametrize("field", ["duration_s", "trace_start_s", "event_timestamp_s"])
def test_oversized_json_integer_metadata_is_rejected_as_media_error(
    tmp_path: Path, field: str
) -> None:
    run = run_with_episode(tmp_path)
    media_dir = run / "media" / "ep-1"
    media_dir.mkdir(parents=True)
    (media_dir / "front.mp4").write_bytes(b"nonempty")
    stream = {
        "camera": "front",
        "path": "media/ep-1/front.mp4",
        "mime_type": "video/mp4",
        "duration_s": 1,
        "trace_start_s": 10,
    }
    manifest = {"schema_version": 1, "episode_id": "ep-1", "streams": [stream]}
    if field in {"duration_s", "trace_start_s"}:
        stream[field] = 10**400
    else:
        manifest["events"] = [{"name": "oversized", "timestamp_s": 10**400}]
    (media_dir / "media.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(MediaError, match="finite number"):
        read_episode_media(run, "ep-1")


def test_oversized_timing_integer_is_rejected_as_media_error() -> None:
    with pytest.raises(MediaError, match="finite number"):
        trace_time_for_video_time(10**400, 1000.0, 1.0)


def test_missing_or_corrupt_media_is_rejected(tmp_path: Path) -> None:
    run = run_with_episode(tmp_path)
    media_dir = run / "media" / "ep-1"
    media_dir.mkdir(parents=True)
    (media_dir / "media.json").write_text("{", encoding="utf-8")
    with pytest.raises(MediaError, match="invalid JSON"):
        read_episode_media(run, "ep-1")

    video = media_dir / "front.mp4"
    video.write_bytes(b"x")
    sidecar = {
        "schema_version": 1,
        "episode_id": "ep-1",
        "streams": [
            {
                "camera": "front",
                "path": "media/ep-1/missing.mp4",
                "mime_type": "video/mp4",
                "duration_s": 1,
                "trace_start_s": 10,
            }
        ],
    }
    (media_dir / "media.json").write_text(json.dumps(sidecar), encoding="utf-8")
    with pytest.raises(MediaError, match="missing"):
        read_episode_media(run, "ep-1")

    (media_dir / "empty.mp4").write_bytes(b"")
    sidecar["streams"][0]["path"] = "media/ep-1/empty.mp4"
    (media_dir / "media.json").write_text(json.dumps(sidecar), encoding="utf-8")
    with pytest.raises(MediaError, match="empty"):
        read_episode_media(run, "ep-1")


def test_traversal_symlinks_and_mime_mismatch_are_rejected(tmp_path: Path) -> None:
    run = run_with_episode(tmp_path)
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"x")
    media_dir = run / "media" / "ep-1"
    media_dir.mkdir(parents=True)
    try:
        (media_dir / "linked.mp4").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")

    def write(path: str, mime: str = "video/mp4") -> None:
        (media_dir / "media.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "episode_id": "ep-1",
                    "streams": [
                        {
                            "camera": "front",
                            "path": path,
                            "mime_type": mime,
                            "duration_s": 1,
                            "trace_start_s": 10,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    write("../outside.mp4")
    with pytest.raises(MediaError):
        read_episode_media(run, "ep-1")
    write("media/ep-1/linked.mp4")
    with pytest.raises(MediaError, match="symlink"):
        read_episode_media(run, "ep-1")
    (media_dir / "outside.mp4").write_bytes(b"x")
    write("media/ep-1/outside.mp4", "video/webm")
    with pytest.raises(MediaError, match="MIME"):
        read_episode_media(run, "ep-1")


@pytest.mark.parametrize(
    ("header", "size", "expected"),
    [
        ("bytes=2-5", 10, (2, 5)),
        ("bytes=7-", 10, (7, 9)),
        ("bytes=-3", 10, (7, 9)),
        ("bytes=-50", 10, (0, 9)),
        ("bytes=8-20", 10, (8, 9)),
    ],
)
def test_parse_single_http_byte_ranges(header: str, size: int, expected: tuple[int, int]) -> None:
    assert parse_byte_range(header, size) == expected


@pytest.mark.parametrize(
    "header", ["bytes=10-", "bytes=2-1", "bytes=1-2,4-5", "items=1-2", "bytes=-0"]
)
def test_invalid_or_unsatisfiable_ranges_are_rejected(header: str) -> None:
    with pytest.raises(MediaError):
        parse_byte_range(header, 10)


def test_extremely_large_range_integer_is_a_media_error() -> None:
    with pytest.raises(MediaError, match="invalid byte range"):
        parse_byte_range("bytes=" + ("9" * 5000) + "-", 10)


def test_copy_byte_range_is_bounded_and_inclusive() -> None:
    sink = io.BytesIO()
    copy_byte_range(io.BytesIO(b"0123456789"), sink, 3, 7, chunk_size=2)
    assert sink.getvalue() == b"34567"


def test_import_requires_existing_episode_and_requires_replace_on_collision(tmp_path: Path) -> None:
    run = run_with_episode(tmp_path)
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.webm"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    import_media(
        run,
        "ep-1",
        "front",
        first,
        1,
        10,
        events=[{"name": "start", "timestamp_s": 10}],
    )
    with pytest.raises(MediaError, match="already has media"):
        import_media(run, "ep-1", "front", second, 2, 20)
    import_media(
        run,
        "ep-1",
        "front",
        second,
        2,
        20,
        events=[{"name": "finish", "timestamp_s": 22}],
        replace=True,
    )
    manifest = read_episode_media(run, "ep-1")
    assert manifest["streams"][0]["mime_type"] == "video/webm"
    assert manifest["events"] == [
        {"name": "start", "timestamp_s": 10.0},
        {"name": "finish", "timestamp_s": 22.0},
    ]
    assert resolve_episode_media(run, "ep-1", "front").read_bytes() == b"second"
    with pytest.raises(MediaError, match="not present"):
        import_media(run, "unknown", "front", first, 1, 10)


def test_import_rejects_traversal_id_and_media_root_symlink_before_creating_outside(
    tmp_path: Path,
) -> None:
    run = run_with_episode(tmp_path)
    source = tmp_path / "recording.mp4"
    source.write_bytes(b"nonempty")
    with pytest.raises(MediaError, match="invalid episode id"):
        import_media(run, "../../outside", "front", source, 1, 10)

    outside = tmp_path / "outside"
    outside.mkdir()
    (run / "media").symlink_to(outside, target_is_directory=True)
    with pytest.raises(MediaError, match="directory is unsafe"):
        import_media(run, "ep-1", "front", source, 1, 10)
    assert list(outside.iterdir()) == []


def test_import_rejects_symlink_at_content_addressed_target(tmp_path: Path) -> None:
    run = run_with_episode(tmp_path)
    source = tmp_path / "recording.mp4"
    source.write_bytes(b"recorded bytes")
    media_dir = run / "media" / "ep-1"
    media_dir.mkdir(parents=True)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    target = media_dir / f"front-{digest}.mp4"
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"outside bytes")
    try:
        target.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")

    with pytest.raises(MediaError, match="target must be a regular"):
        import_media(run, "ep-1", "front", source, 1, 10)
    assert outside.read_bytes() == b"outside bytes"
    assert not (media_dir / "media.json").exists()


def test_changed_source_copy_preserves_existing_sidecar_and_media(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = run_with_episode(tmp_path)
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    first.write_bytes(b"previous media")
    second.write_bytes(b"new source media")
    old_manifest = import_media(run, "ep-1", "front", first, 1, 10)
    old_media = resolve_episode_media(run, "ep-1", "front")

    def copy_changed_source(_source, sink) -> None:
        sink.write(b"bytes changed after source hashing")

    monkeypatch.setattr(import_media_module.shutil, "copyfileobj", copy_changed_source)
    with pytest.raises(MediaError, match="changed while it was being imported"):
        import_media(run, "ep-1", "front", second, 2, 20, replace=True)

    assert read_episode_media(run, "ep-1") == old_manifest
    assert old_media.read_bytes() == b"previous media"
