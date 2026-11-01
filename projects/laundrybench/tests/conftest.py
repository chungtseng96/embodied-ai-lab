import pytest


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
