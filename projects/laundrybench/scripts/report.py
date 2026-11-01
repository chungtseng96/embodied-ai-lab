from __future__ import annotations

import argparse
import json
from pathlib import Path

from laundrybench.evaluation.report import build_summary, render_html


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write summary.json and report.html for one experiment directory."
    )
    parser.add_argument(
        "--experiment-dir",
        type=Path,
        required=True,
        help="experiment directory, e.g. outputs/exp-001-baseline",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="optional baseline experiment directory: a second report column and summary delta",
    )
    args = parser.parse_args()

    for directory in (args.experiment_dir, args.baseline):
        if directory is not None and not (directory / "episodes.jsonl").exists():
            parser.error(f"{directory} has no episodes.jsonl; run scripts/evaluate.py first")

    summary = build_summary(args.experiment_dir, baseline_dir=args.baseline)
    baseline = build_summary(args.baseline) if args.baseline is not None else None

    summary_path = args.experiment_dir / "summary.json"
    report_path = args.experiment_dir / "report.html"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(render_html(summary, baseline=baseline), encoding="utf-8")
    print(f"wrote {summary_path} and {report_path}")


if __name__ == "__main__":
    main()
