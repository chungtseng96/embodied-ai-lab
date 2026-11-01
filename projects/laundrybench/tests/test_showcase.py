import hashlib
import json
import os
from pathlib import Path

import pytest

from laundrybench.web.showcase import (
    BASELINE_ID,
    CANDIDATE_ID,
    export_showcase,
)

COMMIT = "0123456789abcdef0123456789abcdef01234567"
JS_NAME = "index-B4qxe3SM.js"
CSS_NAME = "index-MVdMDkp6.css"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def seed_vite_build(output: Path) -> None:
    assets = output / "assets"
    assets.mkdir(parents=True)
    (assets / JS_NAME).write_text("// trusted Vite output fixture", encoding="utf-8")
    (assets / CSS_NAME).write_text("/* trusted Vite output fixture */", encoding="utf-8")
    (output / "index.html").write_text(
        """<!doctype html>
<html lang="en"><head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>LaundryBench</title>
<script type="module" crossorigin src="/assets/index-B4qxe3SM.js"></script>
<link rel="stylesheet" crossorigin href="/assets/index-MVdMDkp6.css">
</head><body><div id="root"></div></body></html>""",
        encoding="utf-8",
    )


def test_export_is_curated_and_uses_shared_run_summaries(tmp_path):
    output = tmp_path / "frontend" / "dist"
    seed_vite_build(output)
    index_before = (output / "index.html").read_bytes()
    js_before = (output / "assets" / JS_NAME).read_bytes()
    css_before = (output / "assets" / CSS_NAME).read_bytes()
    video = b"test-only synthetic video bytes"

    manifest = export_showcase(
        output,
        source_commit=COMMIT,
        video_factory=lambda: video,
        require_frontend=True,
    )

    assert manifest["schema_version"] == 1
    assert manifest["source_commit"] == COMMIT
    assert manifest["candidate_id"] == CANDIDATE_ID
    assert manifest["baseline_id"] == BASELINE_ID
    assert manifest["evidence_kind"] == "synthetic"
    assert manifest["walkthrough_video_url"] is None
    assert len(manifest["assets"]) == 1
    assert manifest["limitations"]
    assert (output / "index.html").read_bytes() == index_before
    assert (output / "assets" / JS_NAME).read_bytes() == js_before
    assert (output / "assets" / CSS_NAME).read_bytes() == css_before
    assert manifest["inventory"]["/index.html"] == hashlib.sha256(index_before).hexdigest()
    assert manifest["inventory"][f"/assets/{JS_NAME}"] == hashlib.sha256(js_before).hexdigest()
    assert (output / "media" / f"{hashlib.sha256(video).hexdigest()}.mp4").read_bytes() == video

    index = read_json(output / "data" / "runs.json")
    assert [run["id"] for run in index["runs"]] == [CANDIDATE_ID, BASELINE_ID]
    assert len(index["runs"]) == 2
    details = {
        run_id: read_json(output / "data" / "runs" / f"{run_id}.json")
        for run_id in (CANDIDATE_ID, BASELINE_ID)
    }
    for detail in details.values():
        summary = detail["summary"]
        assert summary["reviewed_episodes"] == summary["episodes"] == 12
        assert summary["pending_episodes"] == 0
        assert summary["success_rate"] == summary["successes"] / summary["reviewed_episodes"]
        assert detail["experiment"]["task"] == details[CANDIDATE_ID]["experiment"]["task"]
        assert detail["experiment"]["protocol"] == details[CANDIDATE_ID]["experiment"]["protocol"]
        assert all(
            "not human-reviewed" in episode["annotation"]["notes"] for episode in detail["episodes"]
        )

    candidate_context = details[CANDIDATE_ID]["experiment"]
    baseline_context = details[BASELINE_ID]["experiment"]
    assert candidate_context["checkpoint"] != baseline_context["checkpoint"]
    assert "hypothetical" in candidate_context["hypothesis"]
    assert candidate_context["effective_overrides"] != baseline_context["effective_overrides"]

    episode_id = details[CANDIDATE_ID]["episodes"][0]["episode_id"]
    run_dir = output / "data" / "runs" / CANDIDATE_ID / "episodes" / episode_id
    trace = read_json(run_dir / "trace.json")
    media = read_json(run_dir / "media.json")
    assert trace["episode_id"] == episode_id
    assert trace["steps"]
    assert media["streams"][0]["url"] == f"/media/{hashlib.sha256(video).hexdigest()}.mp4"
    assert media["streams"][0]["url"] == media["streams"][0]["path"]

    comparison = read_json(
        output / "data" / "runs" / CANDIDATE_ID / "compare" / f"{BASELINE_ID}.json"
    )
    acknowledged = read_json(
        output / "data" / "runs" / CANDIDATE_ID / "compare" / f"{BASELINE_ID}.acknowledged.json"
    )
    assert comparison["compatibility"]["status"] == "matched"
    assert comparison["delta"]["reviewed_episodes"] == 0
    assert acknowledged["compatibility"] == comparison["compatibility"]

    generated = {
        path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()
    }
    assert "data/runs/exp-901-mock-candidate/manifest.yaml" not in generated
    assert not any(path.endswith(("episodes.jsonl", "labels.json")) for path in generated)


def test_export_rejects_unverified_source_identity_before_writing(tmp_path):
    called = False

    def video_factory():
        nonlocal called
        called = True
        return b"video"

    output = tmp_path / "dist"
    with pytest.raises(ValueError, match="40-character lowercase hexadecimal"):
        export_showcase(output, source_commit="unknown", video_factory=video_factory)
    assert called is False
    assert not output.exists()


def test_export_copies_and_hashes_explicit_walkthrough_video(tmp_path):
    output = tmp_path / "dist"
    seed_vite_build(output)
    recording = tmp_path / "showcase-demo.webm"
    recording_bytes = b"test-only Playwright walkthrough recording"
    recording.write_bytes(recording_bytes)
    video = b"test-only synthetic evidence bytes"

    manifest = export_showcase(
        output,
        source_commit=COMMIT,
        video_factory=lambda: video,
        walkthrough_video=recording,
        require_frontend=True,
    )

    walkthrough_hash = hashlib.sha256(recording_bytes).hexdigest()
    walkthrough_url = f"/media/{walkthrough_hash}.webm"
    assert manifest["walkthrough_video_url"] == walkthrough_url
    assert manifest["assets"][walkthrough_url] == walkthrough_hash
    assert manifest["inventory"][walkthrough_url] == walkthrough_hash
    assert (output / walkthrough_url.lstrip("/")).read_bytes() == recording_bytes
    assert recording.read_bytes() == recording_bytes


@pytest.mark.parametrize("invalid", ["empty", "suffix", "symlink", "directory", "oversize"])
def test_export_rejects_walkthrough_input_before_writing(tmp_path, invalid):
    output = tmp_path / "dist"
    seed_vite_build(output)
    recording = tmp_path / "recording.webm"
    outside = tmp_path / "outside.webm"
    outside.write_bytes(b"private source")
    if invalid == "empty":
        recording.write_bytes(b"")
    elif invalid == "suffix":
        recording = tmp_path / "recording.avi"
        recording.write_bytes(b"unsupported")
    elif invalid == "symlink":
        recording.symlink_to(outside)
    elif invalid == "directory":
        recording.mkdir()
    else:
        with recording.open("wb") as handle:
            handle.truncate(50 * 1024 * 1024 + 1)
    before = {
        path.relative_to(output).as_posix(): path.read_bytes()
        for path in output.rglob("*")
        if path.is_file()
    }
    called = False

    def video_factory():
        nonlocal called
        called = True
        return b"video"

    with pytest.raises(ValueError):
        export_showcase(
            output,
            source_commit=COMMIT,
            video_factory=video_factory,
            walkthrough_video=recording,
        )
    after = {
        path.relative_to(output).as_posix(): path.read_bytes()
        for path in output.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert called is False
    assert not (output / "showcase.json").exists()
    assert not (output / "media").exists()


@pytest.mark.parametrize("unknown", ["root_file", "stale_data", "unreferenced_asset", "symlink"])
def test_export_refuses_unknown_output_and_leaves_it_untouched(tmp_path, unknown):
    output = tmp_path / "dist"
    seed_vite_build(output)
    outside = tmp_path / "private-source.txt"
    outside.write_text("private", encoding="utf-8")
    if unknown == "root_file":
        (output / "private.txt").write_text("private", encoding="utf-8")
    elif unknown == "stale_data":
        stale = output / "data" / "runs" / "private.json"
        stale.parent.mkdir(parents=True)
        stale.write_text('{"private": true}', encoding="utf-8")
    elif unknown == "unreferenced_asset":
        (output / "assets" / "private-Aa123456.js").write_text("private", encoding="utf-8")
    else:
        (output / "assets" / "private-Aa123456.js").symlink_to(outside)

    before = {
        path.relative_to(output).as_posix(): ("symlink", os.readlink(path))
        if path.is_symlink()
        else ("file", path.read_bytes())
        for path in output.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    called = False

    def video_factory():
        nonlocal called
        called = True
        return b"video"

    with pytest.raises(ValueError):
        export_showcase(output, source_commit=COMMIT, video_factory=video_factory)

    after = {
        path.relative_to(output).as_posix(): ("symlink", os.readlink(path))
        if path.is_symlink()
        else ("file", path.read_bytes())
        for path in output.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    assert after == before
    assert called is False
    assert not (output / "showcase.json").exists()
    assert not (output / "media").exists()
