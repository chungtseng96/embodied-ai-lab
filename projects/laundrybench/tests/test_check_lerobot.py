"""Tests for the read-only LeRobot environment diagnostic."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_lerobot.py"
SPEC = importlib.util.spec_from_file_location("check_lerobot", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
check_lerobot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_lerobot)


def _fake_python(tmp_path: Path, body: str) -> Path:
    executable = tmp_path / "fake-python"
    executable.write_text(f"#!/usr/bin/env python3\n{body}\n", encoding="utf-8")
    executable.chmod(0o755)
    return executable


def test_torch_codec_probe_success_runs_in_child_process(tmp_path: Path) -> None:
    payload = {
        "ok": True,
        "torch_version": "2.6.0",
        "torchcodec_version": "0.2.0",
        "imports": [
            "torch",
            "torchcodec",
            "torchcodec.decoders.VideoDecoder",
            "lerobot.policies.act.modeling_act.ACTPolicy",
        ],
    }
    fake_python = _fake_python(
        tmp_path,
        "import os\n"
        "assert os.environ['HF_HUB_OFFLINE'] == '1'\n"
        "assert os.environ['TRANSFORMERS_OFFLINE'] == '1'\n"
        "assert os.environ['HF_HUB_DISABLE_TELEMETRY'] == '1'\n"
        f"print({json.dumps(json.dumps(payload))})",
    )

    result = check_lerobot._probe_torch_codec(str(fake_python))

    assert result == {key: value for key, value in payload.items() if key != "ok"} | {"ok": True}


def test_torch_codec_probe_reports_import_or_abi_failure(tmp_path: Path) -> None:
    payload = {
        "ok": False,
        "error": "OSError: /private/env/lib/python3.12/site-packages/torchcodec.so: "
        + "undefined symbol "
        + "x" * 700,
    }
    fake_python = _fake_python(
        tmp_path,
        f"print({json.dumps(json.dumps(payload))})\nraise SystemExit(1)",
    )

    result = check_lerobot._probe_torch_codec(str(fake_python))

    assert result["ok"] is False
    assert result["error"].startswith("OSError: <path>: undefined symbol")
    assert len(result["error"]) == check_lerobot.OUTPUT_LIMIT


def test_torch_codec_probe_times_out(tmp_path: Path) -> None:
    fake_python = _fake_python(tmp_path, "import time\ntime.sleep(2)")

    result = check_lerobot._probe_torch_codec(str(fake_python), timeout=0.05)

    assert result["ok"] is False
    assert "timed out" in result["error"]


def test_command_version_requires_successful_exit_and_recognizable_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_python(tmp_path, "print('ffmpeg version 7.0')\nraise SystemExit(9)")
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")

    result = check_lerobot._version_command("fake-python", "-version")

    assert result["ok"] is False
    assert result["version"] == "ffmpeg version 7.0"
    assert "status 9" in result["error"]


def test_main_prints_structured_json_and_fails_when_required_check_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    status = {
        "ok": False,
        "checks": {
            "lerobot": {"status": "fail", "required": True, "message": "wrong pinned version"},
            "hardware": {"status": "warning", "required": False, "message": "not checked"},
        },
    }
    monkeypatch.setattr(check_lerobot, "collect_status", lambda: status)

    result = check_lerobot.main()

    assert result == 1
    assert json.loads(capsys.readouterr().out) == status


def test_collect_status_rejects_a_non_pinned_lerobot_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(check_lerobot.metadata, "version", lambda _: "0.5.0")
    monkeypatch.setattr(
        check_lerobot,
        "_version_command",
        lambda command, *args: {
            "ok": True,
            "version": "ffmpeg version 7.0" if command == "ffmpeg" else "lerobot-info 0.5.0",
            "error": None,
        },
    )
    monkeypatch.setattr(check_lerobot, "_probe_torch_codec", lambda: {"ok": True})

    status = check_lerobot.collect_status()

    assert status["checks"]["lerobot"]["status"] == "fail"
    assert status["checks"]["lerobot"]["version"] == "0.5.0"
    assert status["checks"]["lerobot"]["expected"] == "0.6.1"
    assert status["ok"] is False


@pytest.mark.parametrize("ffmpeg_ok,imports_ok", [(True, True), (False, True), (True, False)])
def test_required_runtime_failures_control_overall_status(
    monkeypatch: pytest.MonkeyPatch, ffmpeg_ok: bool, imports_ok: bool,
) -> None:
    monkeypatch.setattr(check_lerobot.sys, "version_info", (3, 12, 0))
    monkeypatch.setattr(check_lerobot.metadata, "version", lambda _: "0.6.1")
    monkeypatch.setattr(
        check_lerobot, "_version_command",
        lambda *args: {"ok": ffmpeg_ok, "version": "ffmpeg version 6.1", "error": None},
    )
    monkeypatch.setattr(
        check_lerobot, "_probe_torch_codec",
        lambda: {"ok": imports_ok, "error": "incompatible runtime"},
    )
    status = check_lerobot.collect_status()
    assert status["ok"] is (ffmpeg_ok and imports_ok)
    assert status["lerobot"]["importable"] is imports_ok
    assert status["checks"]["hardware"]["status"] == "warning"
