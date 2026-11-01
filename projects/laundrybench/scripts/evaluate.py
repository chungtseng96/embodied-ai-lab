from __future__ import annotations

import argparse
import json
import platform
import re
from datetime import UTC, datetime
from pathlib import Path

from laundrybench.config import load_config
from laundrybench.evaluation.judge import MockSuccessJudge
from laundrybench.evaluation.metrics import summarize
from laundrybench.evaluation.runner import run_episode
from laundrybench.observability.logger import JsonlEpisodeLogger
from laundrybench.observability.manifest import (
    EXPERIMENT_ID_RE,
    RunManifest,
    config_hash,
    git_revision,
    lerobot_version,
    write_manifest,
)
from laundrybench.policies.mock import MockPolicy
from laundrybench.robot.mock import MockRobot


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LaundryBench mock evaluation.")
    parser.add_argument(
        "--experiment",
        required=True,
        help="experiment id matching exp-NNN-name, e.g. exp-001-baseline",
    )
    parser.add_argument("--config-dir", type=Path, default=Path("configs"))
    parser.add_argument(
        "--episodes",
        type=int,
        default=None,
        help="number of episodes (default: evaluation.attempts_per_condition)",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument(
        "--force", action="store_true", help="overwrite an existing experiment directory"
    )
    args = parser.parse_args()

    if not re.match(EXPERIMENT_ID_RE, args.experiment):
        parser.error(f"--experiment {args.experiment!r} must match {EXPERIMENT_ID_RE}")
    experiment_dir = args.output_dir / args.experiment
    if experiment_dir.exists() and not args.force:
        parser.error(f"{experiment_dir} already exists; pass --force to overwrite")

    config = load_config(args.config_dir)
    episodes = (
        args.episodes if args.episodes is not None else config.evaluation.attempts_per_condition
    )
    timeout_s = min(config.task.timeout_seconds, config.robot.max_episode_seconds)

    robot = MockRobot(seed=config.evaluation.seed)
    policy = MockPolicy()
    judge = MockSuccessJudge(seed=config.evaluation.seed)

    write_manifest(
        experiment_dir / "manifest.yaml",
        RunManifest(
            experiment_id=args.experiment,
            created_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            git_revision=git_revision(),
            config_hash=config_hash(args.config_dir),
            seed=config.evaluation.seed,
            policy_name=policy.name,
            robot_implementation=config.robot.implementation,
            python_version=platform.python_version(),
            lerobot_version=lerobot_version(),
        ),
    )
    episodes_path = experiment_dir / "episodes.jsonl"
    # The episode logger appends, so a forced re-run starts from an empty log.
    episodes_path.unlink(missing_ok=True)
    logger = JsonlEpisodeLogger(episodes_path)

    results = []
    for index in range(episodes):
        result = run_episode(
            robot,
            policy,
            judge,
            control_hz=config.evaluation.control_hz,
            timeout_s=timeout_s,
            episode_id=f"{args.experiment}-{index:03d}",
        )
        logger.log(result)
        results.append(result)

    print(json.dumps(summarize(results), indent=2))


if __name__ == "__main__":
    main()
