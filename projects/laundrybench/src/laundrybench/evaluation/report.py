from __future__ import annotations

import json
import math
from html import escape
from pathlib import Path
from string import Template

import yaml

from laundrybench.evaluation.metrics import summarize
from laundrybench.types import EpisodeResult, FailureCategory


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion; ``(0.0, 0.0)`` when ``n == 0``."""

    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half_width = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return (max(0.0, center - half_width), min(1.0, center + half_width))


def _read_episodes(path: Path) -> list[EpisodeResult]:
    results = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            category = record.get("failure_category")
            results.append(
                EpisodeResult(
                    episode_id=record["episode_id"],
                    success=record["success"],
                    duration_s=record["duration_s"],
                    intervention=record.get("intervention", False),
                    failure_category=FailureCategory(category) if category is not None else None,
                    metadata=record.get("metadata", {}),
                )
            )
    return results


def build_summary(experiment_dir: Path) -> dict:
    """Summarize one experiment directory into the ``summary.json`` payload.

    Combines ``summarize()`` over ``episodes.jsonl`` with the Wilson interval for the
    success rate, the ``quality.json`` counts (when that file exists), and the
    ``manifest.yaml`` fields under ``"manifest"``.
    """

    experiment_dir = Path(experiment_dir)
    results = _read_episodes(experiment_dir / "episodes.jsonl")
    summary: dict = dict(summarize(results))
    summary["success_rate_ci"] = list(wilson_interval(summary["successes"], summary["episodes"]))

    quality_path = experiment_dir / "quality.json"
    if quality_path.exists():
        quality = json.loads(quality_path.read_text(encoding="utf-8"))
        summary["quality"] = {"episodes": quality["episodes"], "flagged": quality["flagged"]}

    manifest = yaml.safe_load((experiment_dir / "manifest.yaml").read_text(encoding="utf-8"))
    summary["manifest"] = manifest or {}
    return summary


_PAGE = Template(
    """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>LaundryBench report: $experiment_id</title>
<style>
body { font-family: system-ui, sans-serif; margin: 2rem; color: #222; }
table { border-collapse: collapse; margin-bottom: 1.5rem; }
th, td { border: 1px solid #ccc; padding: 0.3rem 0.6rem; text-align: left; vertical-align: top; }
th { background: #f3f3f3; }
.bar { display: inline-block; height: 0.8rem; background: #4a7bd0; margin-right: 0.4rem; }
</style>
</head>
<body>
<h1>LaundryBench report: $experiment_id</h1>
<h2>Manifest</h2>
<table>
$manifest_rows
</table>
<h2>Metrics</h2>
<table>
$metric_rows
</table>
<h2>Failure categories</h2>
<table>
$failure_rows
</table>
</body>
</html>
"""
)


def _row(cells: list[str], header: bool = False) -> str:
    tag = "th" if header else "td"
    return "<tr>" + "".join(f"<{tag}>{cell}</{tag}>" for cell in cells) + "</tr>"


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _success_rate(summary: dict) -> str:
    low, high = summary["success_rate_ci"]
    return (
        f"{_percent(summary['success_rate'])} "
        f"({summary['successes']}/{summary['episodes']}; 95% CI {_percent(low)} to {_percent(high)})"
    )


def _quality(summary: dict) -> str:
    quality = summary.get("quality")
    if quality is None:
        return "n/a (no quality.json)"
    return f"{quality['flagged']} of {quality['episodes']} episodes flagged"


def _failure_cell(counts: dict[str, int], category: str, scale: int) -> str:
    count = counts.get(category, 0)
    width = round(10 * count / scale) if scale else 0
    return f'<span class="bar" style="width: {width}rem"></span>{count}'


def render_html(summary: dict, baseline: dict | None = None) -> str:
    """Render a self-contained static HTML report; adds a baseline column when given."""

    summaries = [summary] if baseline is None else [summary, baseline]
    labels = ["Candidate"] if baseline is None else ["Candidate", "Baseline"]
    header = _row(["", *labels], header=True)

    manifest_keys = sorted({key for s in summaries for key in s.get("manifest", {})})
    manifest_rows = [header] + [
        _row([escape(key), *(escape(str(s.get("manifest", {}).get(key, ""))) for s in summaries)])
        for key in manifest_keys
    ]

    metrics = [
        ("Success rate", _success_rate),
        ("Median completion time (s)", lambda s: f"{s['median_completion_time_s']:.3f}"),
        ("Intervention rate", lambda s: _percent(s["intervention_rate"])),
        ("Quality flags", _quality),
    ]
    metric_rows = [header] + [
        _row([escape(name), *(escape(render(s)) for s in summaries)]) for name, render in metrics
    ]

    categories = sorted({c for s in summaries for c in s["failure_category_counts"]})
    scale = max((count for s in summaries for count in s["failure_category_counts"].values()),
                default=0)
    if categories:
        failure_rows = [header] + [
            _row([escape(c), *(_failure_cell(s["failure_category_counts"], c, scale)
                               for s in summaries)])
            for c in categories
        ]
    else:
        failure_rows = [_row(["No failed episodes."])]

    return _PAGE.substitute(
        experiment_id=escape(str(summary.get("manifest", {}).get("experiment_id", "unknown"))),
        manifest_rows="\n".join(manifest_rows),
        metric_rows="\n".join(metric_rows),
        failure_rows="\n".join(failure_rows),
    )
