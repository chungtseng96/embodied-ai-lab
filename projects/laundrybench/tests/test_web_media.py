from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http.client import HTTPConnection
from pathlib import Path

import pytest

from laundrybench.web import create_server


def seed_run(root: Path) -> Path:
    run = root / "run-media"
    run.mkdir()
    (run / "episodes.jsonl").write_text(
        json.dumps(
            {
                "episode_id": "episode-001",
                "success": True,
                "duration_s": 2.0,
                "intervention": False,
                "failure_category": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return run


@contextmanager
def running(root: Path):
    server = create_server(root, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def request(port: int, path: str, method: str = "GET", headers: dict | None = None):
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    connection.request(method, path, headers=headers or {})
    response = connection.getresponse()
    result = response.status, dict(response.getheaders()), response.read()
    connection.close()
    return result


def write_manifest(run: Path, *, path: str = "media/episode-001/front.mp4") -> Path:
    media_dir = run / "media" / "episode-001"
    media_dir.mkdir(parents=True, exist_ok=True)
    if path.endswith("front.mp4"):
        (media_dir / "front.mp4").write_bytes(b"0123456789")
    (media_dir / "media.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "episode_id": "episode-001",
                "streams": [
                    {
                        "camera": "front camera",
                        "path": path,
                        "mime_type": "video/mp4",
                        "duration_s": 5.0,
                        "trace_start_s": 1000.25,
                    }
                ],
                "events": [{"name": "grasp", "timestamp_s": 1002.0}],
            }
        ),
        encoding="utf-8",
    )
    return media_dir


BASE = "/api/runs/run-media/episodes/episode-001"


def test_media_manifest_full_range_suffix_open_and_head(tmp_path: Path) -> None:
    run = seed_run(tmp_path)
    write_manifest(run)
    with running(tmp_path) as port:
        status, _, body = request(port, BASE + "/media")
        assert status == 200
        manifest = json.loads(body)
        assert manifest["schema_version"] == 1
        assert manifest["events"] == [{"name": "grasp", "timestamp_s": 1002.0}]
        assert manifest["streams"][0]["url"] == BASE + "/media/front%20camera"

        url = manifest["streams"][0]["url"]
        status, headers, body = request(port, url)
        assert status == 200
        assert body == b"0123456789"
        assert headers["Content-Type"] == "video/mp4"
        assert headers["Content-Length"] == "10"
        assert headers["Accept-Ranges"] == "bytes"

        status, headers, body = request(port, url, headers={"Range": "bytes=2-5"})
        assert status == 206
        assert body == b"2345"
        assert headers["Content-Range"] == "bytes 2-5/10"
        assert headers["Content-Length"] == "4"

        status, headers, body = request(port, url, headers={"Range": "bytes=-3"})
        assert status == 206
        assert body == b"789"
        assert headers["Content-Range"] == "bytes 7-9/10"

        status, headers, body = request(port, url, headers={"Range": "bytes=6-"})
        assert status == 206
        assert body == b"6789"
        assert headers["Content-Range"] == "bytes 6-9/10"

        status, headers, body = request(port, url, "HEAD")
        assert status == 200
        assert body == b""
        assert headers["Content-Length"] == "10"

        status, headers, body = request(port, url, "HEAD", {"Range": "bytes=1-2"})
        assert status == 200
        assert body == b""
        assert headers["Content-Length"] == "10"
        assert "Content-Range" not in headers
        status, headers, body = request(port, BASE + "/media/unknown", "HEAD")
        assert status == 404
        assert body == b""
        assert int(headers["Content-Length"]) > 0

        for headers_in in (
            {"Range": "bytes=1-2,5-6"},
            {"Range": "items=1-2"},
            {"Range": "bytes=1-2", "If-Range": '"no-validator"'},
        ):
            status, headers, body = request(port, url, headers=headers_in)
            assert status == 200
            assert body == b"0123456789"
            assert headers["Content-Length"] == "10"
            assert "Content-Range" not in headers


def test_media_missing_empty_and_unknown_ids_are_clean(tmp_path: Path) -> None:
    run = seed_run(tmp_path)
    with running(tmp_path) as port:
        status, _, body = request(port, BASE + "/media")
        assert status == 200
        assert json.loads(body)["streams"] == []
        assert request(port, "/api/runs/run-media/episodes/no-such-episode/media")[0] == 404
        assert request(port, BASE + "/media/front")[0] == 404
        assert request(port, BASE + "/media/front%2F..%2Fsecret")[0] == 404

    media_dir = write_manifest(run)
    (media_dir / "front.mp4").write_bytes(b"")
    with running(tmp_path) as port:
        assert request(port, BASE + "/media")[0] == 422


@pytest.mark.parametrize("unsafe_path", ["../outside.mp4", "media/episode-001/missing.mp4"])
def test_unsafe_or_missing_manifest_media_returns_422(tmp_path: Path, unsafe_path: str) -> None:
    run = seed_run(tmp_path)
    write_manifest(run, path=unsafe_path)
    with running(tmp_path) as port:
        assert request(port, BASE + "/media")[0] == 422
        assert request(port, BASE + "/media/front%20camera")[0] == 422


def test_symlink_media_is_rejected_without_serving_external_bytes(tmp_path: Path) -> None:
    run = seed_run(tmp_path)
    media_dir = run / "media" / "episode-001"
    media_dir.mkdir(parents=True)
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"secret bytes")
    try:
        (media_dir / "linked.mp4").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    write_manifest(run, path="media/episode-001/linked.mp4")
    with running(tmp_path) as port:
        status, _, _ = request(port, BASE + "/media")
        assert status == 422
        status, _, _ = request(port, BASE + "/media/front%20camera")
        assert status == 422


@pytest.mark.parametrize("range_header", ["bytes=10-", "bytes=1-0"])
def test_invalid_or_unsatisfiable_ranges_return_416(tmp_path: Path, range_header: str) -> None:
    run = seed_run(tmp_path)
    write_manifest(run)
    with running(tmp_path) as port:
        status, headers, body = request(
            port,
            BASE + "/media/front%20camera",
            headers={"Range": range_header},
        )
    assert status == 416
    assert headers["Content-Range"] == "bytes */10"
    assert headers["Accept-Ranges"] == "bytes"
    assert body == b""
