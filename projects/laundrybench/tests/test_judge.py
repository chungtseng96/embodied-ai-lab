from laundrybench.evaluation.judge import MockSuccessJudge
from laundrybench.types import Observation


def test_mock_judge_is_false_before_threshold() -> None:
    judge = MockSuccessJudge(seed=0, success_after_steps=3)
    assert judge.is_success(Observation(0.0, [0.0] * 6, metadata={"step": 2})) is False


def test_mock_judge_is_deterministic_for_seed() -> None:
    obs = Observation(0.0, [0.0] * 6, metadata={"step": 5})
    a = [MockSuccessJudge(seed=1).is_success(obs) for _ in range(5)]
    b = [MockSuccessJudge(seed=1).is_success(obs) for _ in range(5)]
    assert a == b


def test_mock_judge_on_timeout_is_false() -> None:
    assert MockSuccessJudge().on_timeout(Observation(0.0, [0.0] * 6)) is False
