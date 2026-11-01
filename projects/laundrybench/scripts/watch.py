from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from laundrybench.config import ConfigError, load_config
from laundrybench.observability.status import format_status
from laundrybench.types import EpisodeResult, FailureCategory


def _parse_episode(line: str) -> EpisodeResult:
    record = json.loads(line)
    category = record.get("failure_category")
    return EpisodeResult(
        episode_id=record["episode_id"],
        success=record["success"],
        duration_s=record["duration_s"],
        intervention=record.get("intervention", False),
        failure_category=FailureCategory(category) if category is not None else None,
        metadata=record.get("metadata", {}),
    )


def _resolve_total(total: int | None, config_dir: Path) -> int | None:
    """``--total`` if given, else ``evaluation.attempts_per_condition``, else ``None``."""

    if total is not None:
        return total
    try:
        return load_config(config_dir).evaluation.attempts_per_condition
    except ConfigError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tail an experiment's episodes.jsonl and print a one-line status per episode."
    )
    parser.add_argument(
        "--experiment-dir",
        type=Path,
        required=True,
        help="experiment directory, e.g. outputs/exp-001-baseline",
    )
    parser.add_argument(
        "--total",
        type=int,
        default=None,
        help="expected episode count (default: evaluation.attempts_per_condition)",
    )
    parser.add_argument("--config-dir", type=Path, default=Path("configs"))
    parser.add_argument(
        "--interval", type=float, default=0.5, help="polling interval in seconds (default: 0.5)"
    )
    args = parser.parse_args()
    if args.total is not None and args.total <= 0:
        parser.error("--total must be positive")
    if args.interval <= 0:
        parser.error("--interval must be positive")

    total = _resolve_total(args.total, args.config_dir)
    path = args.experiment_dir / "episodes.jsonl"
    results: list[EpisodeResult] = []
    offset = 0
    pending = ""
    print(format_status(results, total), flush=True)
    try:
        while True:
            if path.exists():
                with path.open(encoding="utf-8") as handle:
                    handle.seek(offset)
                    chunk = handle.read()
                    offset = handle.tell()
                pending += chunk
                # Only parse complete lines; a partial trailing line waits for the next poll.
                *lines, pending = pending.split("\n")
                for line in lines:
                    if line.strip():
                        results.append(_parse_episode(line))
                        print(format_status(results, total), flush=True)
            if total is not None and len(results) >= total:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
