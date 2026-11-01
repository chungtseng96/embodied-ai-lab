import json

from laundrybench.evaluation.quality import (
    QualityFlag,
    check_episode_quality,
    write_quality_report,
)

CONTROL_HZ = 10.0


def make_steps(
    targets: list[list[float]], *, dt: float = 0.1, episode_id: str = "ep"
) -> list[dict]:
    return [
        {"episode_id": episode_id, "step": i, "timestamp_s": i * dt, "joint_targets": target}
        for i, target in enumerate(targets)
    ]


def varied_targets(n: int) -> list[list[float]]:
    return [[0.1 * i] * 6 for i in range(n)]


def checks(flags: list[QualityFlag]) -> list[str]:
    return [flag.check for flag in flags]


def test_clean_episode_has_no_flags() -> None:
    steps = make_steps(varied_targets(12))
    result = {"episode_id": "ep", "success": True, "failure_category": None}
    assert check_episode_quality(steps, control_hz=CONTROL_HZ, result=result) == []


def test_frozen_actions_flagged_after_ten_identical_targets() -> None:
    steps = make_steps(varied_targets(2) + [[0.5] * 6] * 10)
    assert checks(check_episode_quality(steps, control_hz=CONTROL_HZ)) == ["frozen_actions"]


def test_nine_identical_targets_are_not_frozen() -> None:
    steps = make_steps(varied_targets(2) + [[0.5] * 6] * 9)
    assert check_episode_quality(steps, control_hz=CONTROL_HZ) == []


def test_nan_action_flagged() -> None:
    targets = varied_targets(5)
    targets[3] = [0.1, float("nan"), 0.1, 0.1, 0.1, 0.1]
    flags = check_episode_quality(make_steps(targets), control_hz=CONTROL_HZ)
    assert checks(flags) == ["nan_action"]
    assert flags[0].episode_id == "ep"


def test_joint_limit_flagged() -> None:
    targets = varied_targets(5)
    targets[2] = [0.0, 0.0, 150.0, 0.0, 0.0, 0.0]
    flags = check_episode_quality(make_steps(targets), control_hz=CONTROL_HZ)
    assert checks(flags) == ["joint_limit"]


def test_nan_action_flagged_once_per_episode() -> None:
    targets = varied_targets(20)
    for step in (12, 15, 18):
        targets[step] = [float("nan")] * 6
    flags = check_episode_quality(make_steps(targets), control_hz=CONTROL_HZ)
    assert checks(flags) == ["nan_action"]
    assert "3 steps" in flags[0].detail
    assert "first at step 12" in flags[0].detail


def test_joint_limit_flagged_once_per_episode() -> None:
    targets = varied_targets(10)
    for step in (4, 7):
        targets[step] = [0.0, 0.0, 150.0, 0.0, 0.0, 0.0]
    flags = check_episode_quality(make_steps(targets), control_hz=CONTROL_HZ)
    assert checks(flags) == ["joint_limit"]
    assert "2 steps" in flags[0].detail
    assert "first at step 4" in flags[0].detail


def test_timestamp_gap_flagged() -> None:
    steps = make_steps(varied_targets(5))
    for later in steps[3:]:
        later["timestamp_s"] += 1.0  # 1.1 s gap > 3 / 10 Hz
    flags = check_episode_quality(steps, control_hz=CONTROL_HZ)
    assert checks(flags) == ["timestamp_gap"]


def test_missing_label_flagged_for_unspecified_failure() -> None:
    steps = make_steps(varied_targets(5))
    for category in ("unspecified", None):
        result = {"episode_id": "ep", "success": False, "failure_category": category}
        flags = check_episode_quality(steps, control_hz=CONTROL_HZ, result=result)
        assert checks(flags) == ["missing_label"]


def test_labelled_failure_is_not_missing_label() -> None:
    steps = make_steps(varied_targets(5))
    result = {"episode_id": "ep", "success": False, "failure_category": "timeout"}
    assert check_episode_quality(steps, control_hz=CONTROL_HZ, result=result) == []


def test_write_quality_report_counts_distinct_flagged_episodes(tmp_path) -> None:
    flags = [
        QualityFlag("ep-a", "nan_action", "step 3"),
        QualityFlag("ep-a", "joint_limit", "step 4"),
        QualityFlag("ep-b", "frozen_actions", "steps 0-9"),
    ]
    path = tmp_path / "quality.json"
    write_quality_report(path, flags, ["ep-a", "ep-b", "ep-c"])
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["episodes"] == 3
    assert report["flagged"] == 2
    assert report["flags"][0] == {"episode_id": "ep-a", "check": "nan_action", "detail": "step 3"}
    assert len(report["flags"]) == 3
