"""Create or update a versioned experiment context sidecar."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from laundrybench.evaluation.metadata import MetadataError, write_experiment_metadata


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Atomically write human context to experiment.json without changing manifest.yaml."
        )
    )
    parser.add_argument("--run-dir", type=Path, required=True, help="one completed run directory")
    parser.add_argument(
        "--metadata-file", type=Path, required=True, help="JSON object with context fields"
    )
    parser.add_argument(
        "--expected-revision",
        type=int,
        help="required when updating; omit only when creating a new experiment.json",
    )
    args = parser.parse_args()
    try:
        value = json.loads(args.metadata_file.read_text(encoding="utf-8"))
        result = write_experiment_metadata(
            args.run_dir, value, expected_revision=args.expected_revision
        )
    except (OSError, json.JSONDecodeError, MetadataError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
