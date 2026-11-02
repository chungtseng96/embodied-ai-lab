"""Export the curated synthetic static results showcase."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from laundrybench.web.showcase import export_showcase


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT / "frontend" / "dist",
        help="frontend build directory (default: projects/laundrybench/frontend/dist)",
    )
    parser.add_argument(
        "--source-commit",
        required=True,
        help="40-character lowercase git commit SHA used to build this showcase",
    )
    parser.add_argument(
        "--walkthrough-video",
        type=Path,
        help="optional explicit Playwright CI walkthrough recording (.webm or .mp4)",
    )
    args = parser.parse_args()
    manifest = export_showcase(
        args.output_dir,
        source_commit=args.source_commit,
        require_frontend=True,
        walkthrough_video=args.walkthrough_video,
    )
    print(
        f"exported synthetic showcase for {manifest['candidate_id']} vs "
        f"{manifest['baseline_id']} to {args.output_dir}"
    )


if __name__ == "__main__":
    main()
