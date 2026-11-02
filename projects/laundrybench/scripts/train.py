"""Plan or explicitly start a native LeRobot ACT training run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from laundrybench.training.act import (
    TrainingError,
    finalize_checkpoint,
    fingerprint_dataset,
    run_training,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "configs" / "training.example.yaml",
        help="strict training YAML (default: checked-in example)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="run LeRobot training; without this flag only validate and print the plan",
    )
    parser.add_argument(
        "--lerobot-python",
        type=Path,
        help="Python executable in the actual LeRobot 0.6.1 environment (execute only)",
    )
    parser.add_argument(
        "--fingerprint-dataset",
        type=Path,
        metavar="ROOT",
        help="print a local-sha256 revision for a complete local LeRobot dataset tree",
    )
    parser.add_argument(
        "--finalize-checkpoint",
        type=Path,
        metavar="PRETRAINED_MODEL",
        help="bind a downloaded completed HF Jobs ACT checkpoint to this run's contract",
    )
    parser.add_argument(
        "--confirm-remote-complete",
        action="store_true",
        help="confirm native HF Jobs logs show the remote run completed",
    )
    parser.add_argument(
        "--remote-model-revision",
        help="full Hub commit SHA of the completed model repo revision you downloaded",
    )
    args = parser.parse_args()
    if args.fingerprint_dataset is not None:
        if args.execute or args.finalize_checkpoint is not None:
            parser.error("--fingerprint-dataset cannot be combined with execution/finalization")
        try:
            revision = fingerprint_dataset(args.fingerprint_dataset)
        except TrainingError as exc:
            parser.error(str(exc))
        print(
            json.dumps(
                {
                    "dataset_root": str(args.fingerprint_dataset.expanduser().resolve()),
                    "dataset_revision": revision,
                },
                indent=2,
            )
        )
        return
    if args.finalize_checkpoint is not None:
        if args.execute:
            parser.error("--finalize-checkpoint cannot be combined with --execute")
        if not args.remote_model_revision:
            parser.error("--finalize-checkpoint requires --remote-model-revision")
        try:
            result = finalize_checkpoint(
                args.config,
                args.finalize_checkpoint,
                confirm_remote_complete=args.confirm_remote_complete,
                remote_model_revision=args.remote_model_revision,
            )
        except TrainingError as exc:
            parser.error(str(exc))
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    try:
        result = run_training(args.config, execute=args.execute, lerobot_python=args.lerobot_python)
    except TrainingError as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    if result.get("status") in {"failed", "submission_error"}:
        raise SystemExit(1)
    if result.get("status") in {"interrupted", "detached"}:
        raise SystemExit(130)


if __name__ == "__main__":
    main()
