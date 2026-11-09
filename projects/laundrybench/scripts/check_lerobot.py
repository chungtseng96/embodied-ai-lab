"""Read-only diagnostics for the pinned LaundryBench LeRobot environment."""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

MIN_PYTHON = (3, 12)
PINNED_LEROBOT = "0.6.1"
PROBE_TIMEOUT_SECONDS = 45
OUTPUT_LIMIT = 500

# Import the runtime packages in a child process. In particular, TorchCodec can
# fail while loading native libraries; keeping that probe separate protects the
# stock-Python script and lets us bound a stuck native import. Intel macOS has
# no supported TorchCodec wheel, so its edge profile probes LeRobot's PyAV path.
_TORCH_CODEC_PROBE = r'''
import json
try:
    import torch
    import torchcodec
    # Import the ACT path used for training and the video decoder used by the
    # data pipeline, without loading a policy or opening media/hardware.
    from torchcodec.decoders import VideoDecoder
    from lerobot.policies.act.modeling_act import ACTPolicy
    result = {
        "ok": True,
        "torch_version": str(torch.__version__),
        "torchcodec_version": str(getattr(torchcodec, "__version__", "unknown")),
        "imports": [
            "torch",
            "torchcodec",
            "torchcodec.decoders.VideoDecoder",
            "lerobot.policies.act.modeling_act.ACTPolicy",
        ],
    }
    print(json.dumps(result))
except BaseException as exc:
    message = str(exc).replace('\\n', ' ')
    print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {message[:300]}"}))
    raise SystemExit(1)
'''

_PYAV_ACT_PROBE = r'''
import json
try:
    import av
    import torch
    from lerobot.policies.act.modeling_act import ACTPolicy
    result = {
        "ok": True,
        "torch_version": str(torch.__version__),
        "av_version": str(getattr(av, "__version__", "unknown")),
        "video_backend": "pyav",
        "imports": [
            "torch",
            "av",
            "lerobot.policies.act.modeling_act.ACTPolicy",
        ],
    }
    print(json.dumps(result))
except BaseException as exc:
    message = str(exc).replace('\n', ' ')
    print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {message[:300]}"}))
    raise SystemExit(1)
'''


def _bounded(value: str, limit: int = OUTPUT_LIMIT) -> str:
    value = " ".join(value.split())
    if len(value) > limit:
        return value[: limit - 3] + "..."
    return value


def _redact_paths(value: str) -> str:
    """Keep import diagnostics useful without echoing local environment paths."""
    return re.sub(r"(?<!\w)(?:[A-Za-z]:)?[/\\][^\s:()]+", "<path>", value)


def _version_command(command: str, *args: str, timeout: float = 5) -> dict[str, Any]:
    executable = shutil.which(command)
    if executable is None:
        sibling = Path(sys.executable).with_name(command)
        executable = str(sibling) if sibling.exists() else None
    if executable is None:
        return {"ok": False, "version": None, "error": f"{command} executable not found"}

    try:
        result = subprocess.run(
            [executable, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={
                **os.environ,
                "PYTHONDONTWRITEBYTECODE": "1",
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "HF_HUB_DISABLE_TELEMETRY": "1",
            },
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "version": None, "error": f"{command} version check timed out"}
    except OSError as exc:
        return {"ok": False, "version": None, "error": f"{command}: {type(exc).__name__}: {exc}"}

    raw_output = result.stdout or result.stderr or ""
    output = _bounded(raw_output.splitlines()[0] if raw_output else "", 250)
    if result.returncode != 0:
        return {
            "ok": False,
            "version": output or None,
            "error": f"{command} exited with status {result.returncode}",
        }
    return {"ok": True, "version": output or "version not reported", "error": None}


def _probe_import_script(
    python_executable: str = sys.executable,
    script: str = _TORCH_CODEC_PROBE,
    *,
    timeout: float = PROBE_TIMEOUT_SECONDS,
    probe_name: str = "Torch/TorchCodec",
) -> dict[str, Any]:
    try:
        child_env = os.environ.copy()
        child_env.update(
            {
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "HF_HUB_DISABLE_TELEMETRY": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )
        result = subprocess.run(
            [python_executable, "-c", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=child_env,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"{probe_name} import probe timed out after {timeout:g}s"}
    except OSError as exc:
        return {"ok": False, "error": f"could not start import probe: {type(exc).__name__}: {exc}"}

    stdout = result.stdout or ""
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        detail = "probe returned no JSON diagnostic output"
        return {
            "ok": False,
            "error": f"{probe_name} probe exited {result.returncode}: {detail}",
        }
    if not isinstance(payload, dict):
        return {"ok": False, "error": "import probe returned an unexpected diagnostic format"}
    if result.returncode != 0 or not payload.get("ok"):
        detail = _bounded(_redact_paths(str(payload.get("error") or "import probe failed")))
        return {"ok": False, "error": detail}
    return {
        "ok": True,
        **{key: value for key, value in payload.items() if key != "ok"},
    }


def _probe_torch_codec(
    python_executable: str = sys.executable,
    *,
    timeout: float = PROBE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    return _probe_import_script(
        python_executable,
        timeout=timeout,
        probe_name="Torch/TorchCodec",
    )


def _probe_pyav_act(
    python_executable: str = sys.executable,
    *,
    timeout: float = PROBE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    return _probe_import_script(
        python_executable,
        _PYAV_ACT_PROBE,
        timeout=timeout,
        probe_name="Torch/PyAV",
    )


def _is_intel_macos() -> bool:
    return sys.platform == "darwin" and platform.machine().lower() in {"x86_64", "amd64"}


def _probe_video_runtime() -> dict[str, Any]:
    if _is_intel_macos():
        result = _probe_pyav_act()
        return {"runtime_profile": "macos-x86_64-edge", "video_backend": "pyav", **result}

    result = _probe_torch_codec()
    return {"runtime_profile": "native-training", "video_backend": "torchcodec", **result}


def _check_result(
    ok: bool, message: str, *, required: bool = True, **details: Any
) -> dict[str, Any]:
    status = "pass" if ok else "fail" if required else "warning"
    return {"status": status, "required": required, "message": message, **details}


def collect_status() -> dict[str, Any]:
    python_ok = sys.version_info >= MIN_PYTHON
    try:
        lerobot_version = metadata.version("lerobot")
    except metadata.PackageNotFoundError:
        lerobot_version = None
    lerobot_ok = lerobot_version == PINNED_LEROBOT

    ffmpeg = _version_command("ffmpeg", "-version")
    ffmpeg_version_match = re.search(r"\bffmpeg version\s+([^\s]+)", ffmpeg["version"] or "")
    ffmpeg["version_number"] = ffmpeg_version_match.group(1) if ffmpeg_version_match else None
    ffmpeg_ok = ffmpeg["ok"] and ffmpeg_version_match is not None

    torch_codec = _probe_video_runtime()
    ffmpeg_required = not _is_intel_macos()
    runtime_message = (
        "Torch and PyAV imports succeeded for the Intel macOS edge profile"
        if torch_codec.get("video_backend") == "pyav" and torch_codec["ok"]
        else "Torch and TorchCodec imports succeeded"
        if torch_codec["ok"]
        else torch_codec["error"]
    )
    checks = {
        "python": _check_result(
            python_ok,
            (
                f"Python {platform.python_version()} "
                f"{'meets' if python_ok else 'does not meet'} the >=3.12 requirement"
            ),
            version=platform.python_version(),
            executable=sys.executable,
            minimum="3.12",
        ),
        "lerobot": _check_result(
            lerobot_ok,
            (
                f"LeRobot {lerobot_version or 'is not installed'}; "
                f"required version is {PINNED_LEROBOT}"
            ),
            version=lerobot_version,
            expected=PINNED_LEROBOT,
        ),
        "ffmpeg": _check_result(
            ffmpeg_ok,
            ffmpeg.get("error") or (
                f"ffmpeg {ffmpeg['version_number']} is available"
                if ffmpeg_version_match
                else "ffmpeg returned no recognizable version"
            ),
            required=ffmpeg_required,
            version=ffmpeg.get("version_number"),
            output=ffmpeg.get("version"),
        ),
        "torch_codec": _check_result(
            torch_codec["ok"],
            runtime_message,
            **{key: value for key, value in torch_codec.items() if key != "ok"},
        ),
        "hardware": {
            "status": "warning",
            "required": False,
            "message": (
                "Hardware drivers, connected devices, calibration, and arm readiness are not "
                "checked by this software-only diagnostic."
            ),
        },
    }
    optional_lerobot_info = _version_command("lerobot-info", "--version")
    old_ffmpeg = (
        f"ffmpeg version {ffmpeg['version_number']}"
        if ffmpeg.get("version_number")
        else ffmpeg.get("error")
    )
    return {
        "ok": all(check["status"] == "pass" for key, check in checks.items() if check["required"]),
        "checks": checks,
        # Retain the original top-level summaries for callers using the older
        # diagnostic shape while adding the authoritative structured checks.
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
            "meets_lerobot_docs_minimum": python_ok,
        },
        "lerobot": {
            "importable": lerobot_version is not None and torch_codec["ok"],
            "version": lerobot_version,
        },
        "tools": {
            "ffmpeg": old_ffmpeg,
            "lerobot-info": (
                optional_lerobot_info.get("version") if optional_lerobot_info["ok"] else None
            ),
        },
    }


def main() -> int:
    status = collect_status()
    print(json.dumps(status, indent=2), flush=True)
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
