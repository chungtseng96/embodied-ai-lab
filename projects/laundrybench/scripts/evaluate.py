from __future__ import annotations

import argparse
import json
from pathlib import Path

from laundrybench.evaluation.metrics import summarize
from laundrybench.evaluation.runner import run_episode
from laundrybench.observability.logger import JsonlEpisodeLogger
from laundrybench.policies.mock import MockPolicy
from laundrybench.robot.mock import MockRobot


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LaundryBench mock evaluation.")
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--output", type=Path, default=Path("outputs/mock-episodes.jsonl"))
    args = parser.parse_args()

    robot = MockRobot(seed=7)
    policy = MockPolicy()
    logger = JsonlEpisodeLogger(args.output)

    results = []
    for _ in range(args.episodes):
        result = run_episode(robot, policy)
        logger.log(result)
        results.append(result)

    print(json.dumps(summarize(results), indent=2))


if __name__ == "__main__":
    main()
