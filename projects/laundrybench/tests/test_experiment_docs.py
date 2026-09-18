"""Every experiment README must carry the fields that keep results honest.

This is the repo's cheapest doc-freshness check: experiments are first-class artifacts,
so a missing Hardware line or Status header is a defect, not a style nit.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

EXPERIMENTS_DIR = Path(__file__).resolve().parents[1] / "experiments"
EXPERIMENT_READMES = sorted(EXPERIMENTS_DIR.glob("exp-*/README.md"))

REQUIRED_HEADINGS = ("## Question", "## Hypothesis", "## Status")
HARDWARE_LINE = re.compile(r"^\*\*Hardware:\*\* (mock|physical)\b", re.MULTILINE)


def test_experiments_exist() -> None:
    assert EXPERIMENT_READMES, f"no exp-*/README.md under {EXPERIMENTS_DIR}"


@pytest.mark.parametrize("readme", EXPERIMENT_READMES, ids=lambda p: p.parent.name)
def test_experiment_readme_has_required_fields(readme: Path) -> None:
    text = readme.read_text(encoding="utf-8")
    missing = [heading for heading in REQUIRED_HEADINGS if heading not in text]
    assert not missing, f"{readme.parent.name} is missing {missing}"
    assert HARDWARE_LINE.search(text), (
        f"{readme.parent.name} needs a `**Hardware:** mock | physical` line "
        "(mock results are never robot results)"
    )
