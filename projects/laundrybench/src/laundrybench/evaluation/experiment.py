from __future__ import annotations

import json
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from laundrybench.evaluation.judge import SuccessJudge
from laundrybench.evaluation.quality import check_episode_quality, write_quality_report
from laundrybench.evaluation.runner import run_episode
from laundrybench.observability.logger import JsonlEpisodeLogger, JsonlStepLogger
from laundrybench.observability.manifest import RunManifest, write_manifest
from laundrybench.policies.base import Policy
from laundrybench.robot.base import Robot
from laundrybench.types import EpisodeResult


def run_experiment(
    experiment_dir: Path,
    manifest: RunManifest,
    *,
    robot: Robot,
    policy: Policy,
    judge: SuccessJudge,
    episodes: int,
    control_hz: float,
    timeout_s: float,
    clock: Callable[[], float] = time.perf_counter,
    sleep: Callable[[float], None] = time.sleep,
) -> list[EpisodeResult]:
    """Run ``episodes`` episodes and write the experiment directory contract.

    Writes ``manifest.yaml``, ``episodes.jsonl``, ``traces/steps.jsonl``, and
    ``quality.json`` under ``experiment_dir``. Episode ids are
    ``f"{manifest.experiment_id}-{index:03d}"``. Existing logs are replaced.
    """

    experiment_dir = Path(experiment_dir)
    write_manifest(experiment_dir / "manifest.yaml", manifest)
    episodes_path = experiment_dir / "episodes.jsonl"
    steps_path = experiment_dir / "traces" / "steps.jsonl"
    # Both loggers append, so a forced re-run starts from empty logs.
    episodes_path.unlink(missing_ok=True)
    steps_path.unlink(missing_ok=True)
    logger = JsonlEpisodeLogger(episodes_path)
    step_logger = JsonlStepLogger(steps_path)

    results = []
    for index in range(episodes):
        result = run_episode(
            robot,
            policy,
            judge,
            control_hz=control_hz,
            timeout_s=timeout_s,
            clock=clock,
            sleep=sleep,
            episode_id=f"{manifest.experiment_id}-{index:03d}",
            on_step=step_logger.log,
        )
        logger.log(result)
        results.append(result)

    steps_by_episode: dict[str, list[dict]] = defaultdict(list)
    if steps_path.exists():
        with steps_path.open(encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                steps_by_episode[record["episode_id"]].append(record)
    flags = []
    for result in results:
        record = asdict(result)
        record["failure_category"] = (
            result.failure_category.value if result.failure_category is not None else None
        )
        flags.extend(
            check_episode_quality(
                steps_by_episode.get(result.episode_id, []),
                control_hz=control_hz,
                result=record,
            )
        )
    write_quality_report(
        experiment_dir / "quality.json", flags, [result.episode_id for result in results]
    )
    return results
