"""Tests for the reproducible native edge-environment bootstrap."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap_edge_env.py"
SPEC = importlib.util.spec_from_file_location("bootstrap_edge_env", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


def test_reuses_complete_environment_without_clearing_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    venv = tmp_path / "edge"
    python = venv / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("numpy==1.26.4\n", encoding="utf-8")
    commands: list[list[str]] = []

    monkeypatch.setattr(bootstrap.shutil, "which", lambda command: "/usr/local/bin/uv")
    monkeypatch.setattr(bootstrap, "_run", commands.append)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "bootstrap_edge_env.py",
            "--venv",
            str(venv),
            "--requirements",
            str(requirements),
        ],
    )

    assert bootstrap.main() == 0
    assert all(command[1] == "pip" for command in commands)
    assert commands[1][5:7] == ["--no-deps", "lerobot==0.6.1"]


def test_refuses_an_incomplete_existing_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    venv = tmp_path / "edge"
    venv.mkdir()
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("numpy==1.26.4\n", encoding="utf-8")
    monkeypatch.setattr(bootstrap.shutil, "which", lambda command: "/usr/local/bin/uv")
    monkeypatch.setattr(sys, "argv", ["bootstrap_edge_env.py", "--venv", str(venv)])

    with pytest.raises(SystemExit, match="not a complete virtual environment"):
        bootstrap.main()
