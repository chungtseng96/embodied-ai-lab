from __future__ import annotations

import importlib.util
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_lelab.py"
SPEC = importlib.util.spec_from_file_location("lelab_operator_cli", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
lelab_operator_cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lelab_operator_cli)


def test_lelab_command_can_start_without_opening_a_browser() -> None:
    command = lelab_operator_cli.build_command(
        Path(".venv-lelab/bin/lelab"), no_open=True
    )

    assert command == [".venv-lelab/bin/lelab", "--no-open"]


def test_lelab_command_stop_does_not_start_a_session() -> None:
    command = lelab_operator_cli.build_command(
        Path(".venv-lelab/bin/lelab"), stop=True
    )

    assert command == [".venv-lelab/bin/lelab", "--stop"]


def test_lelab_environment_prepends_validated_lerobot_site() -> None:
    environment = lelab_operator_cli.build_environment(
        {"PYTHONPATH": "/tmp/existing"},
        lerobot_site=Path("/tmp/lerobot-site"),
        lerobot_home=Path("/tmp/lerobot-home"),
    )

    assert environment["PYTHONPATH"] == os.pathsep.join(
        ("/tmp/lerobot-site", "/tmp/existing")
    )
    assert environment["HF_LEROBOT_HOME"] == "/tmp/lerobot-home"
