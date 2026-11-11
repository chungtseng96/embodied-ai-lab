from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_operator_ui.py"
SPEC = importlib.util.spec_from_file_location("operator_ui_cli", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
operator_ui_cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(operator_ui_cli)


def test_operator_ui_command_is_local_and_limits_camera_scan() -> None:
    command = operator_ui_cli.build_command(
        "/usr/local/bin/phosphobot",
        port=8020,
        max_opencv_index=2,
    )

    assert command == [
        "/usr/local/bin/phosphobot",
        "run",
        "--host=127.0.0.1",
        "--port=8020",
        "--max-opencv-index=2",
        "--no-can",
        "--no-realsense",
        "--no-telemetry",
    ]
