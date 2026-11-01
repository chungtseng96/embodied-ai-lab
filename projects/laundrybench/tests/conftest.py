import shutil
from pathlib import Path

import pytest

REPO_CONFIGS = Path(__file__).resolve().parents[1] / "configs"


def copy_configs(src: Path, dst: Path) -> None:
    for name in ("robot.yaml", "camera.yaml", "task.yaml", "evaluation.yaml"):
        shutil.copy(src / name, dst / name)


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, dt: float) -> None:
        self.t += dt


@pytest.fixture
def fake_clock():
    return FakeClock()
