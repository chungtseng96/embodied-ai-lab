from __future__ import annotations

import argparse
import json
from pathlib import Path

from laundrybench.config import load_config
from laundrybench.evaluation.judge import MockSuccessJudge
from laundrybench.evaluation.metrics import summarize
from laundrybench.evaluation.runner import run_episode
from laundrybench.observability.logger import JsonlEpisodeLogger
from laundrybench.policies.mock import MockPolicy
from laundrybench.robot.mock import MockRobot


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LaundryBench mock evaluation.")
    parser.add_argument("--config-dir", type=Path, default=Path("configs"))
    parser.add_argument(
        "--episodes",
        type=int,
        default=None,
        help="number of episodes (default: evaluation.attempts_per_condition)",
    )
    parser.add_argument("--output", type=Path, default=Path("outputs/mock-episodes.jsonl"))
    args = parser.parse_args()

    config = load_config(args.config_dir)
    episodes = (
        args.episodes if args.episodes is not None else config.evaluation.attempts_per_condition
    )
    timeout_s = min(config.task.timeout_seconds, config.robot.max_episode_seconds)

    robot = MockRobot(seed=config.evaluation.seed)
    policy = MockPolicy()
    judge = MockSuccessJudge(seed=config.evaluation.seed)
    logger = JsonlEpisodeLogger(args.output)

    results = []
    for _ in range(episodes):
        result = run_episode(
            robot, policy, judge, control_hz=config.evaluation.control_hz, timeout_s=timeout_s
        )
        logger.log(result)
        results.append(result)

    print(json.dumps(summarize(results), indent=2))


if __name__ == "__main__":
    main()
