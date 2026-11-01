from __future__ import annotations

import json
from html import escape
from pathlib import Path
from string import Template

import yaml

from laundrybench.evaluation.outcomes import (
    LABEL_FILE,
    summarize_outcomes,
    validate_episode_records,
    validate_labels,
    wilson_interval,  # noqa: F401 - retained as a public compatibility export
)


def _read_episodes(path: Path) -> list[dict]:
    results = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            results.append(json.loads(line))
    return results


def build_summary(experiment_dir: Path, baseline_dir: Path | None = None) -> dict:
    """Summarize one experiment directory into the ``summary.json`` payload.

    Headline metrics use reviewed, non-excluded labels from ``labels.json``;
    unreviewed original outcomes remain provisional. Quality counts and manifest
    fields are added when present. A baseline delta is unavailable if either run
    has no reviewed episodes.
    """

    experiment_dir = Path(experiment_dir)
    records = validate_episode_records(_read_episodes(experiment_dir / "episodes.jsonl"))
    labels_path = experiment_dir / LABEL_FILE
    try:
        stored_labels = (
            json.loads(labels_path.read_text(encoding="utf-8"))
            if labels_path.exists()
            else {"revision": 0, "labels": {}}
        )
        labels = validate_labels(stored_labels, {record["episode_id"] for record in records})
    except (TypeError, ValueError) as error:
        raise ValueError(f"{labels_path}: {error}") from error
    summary: dict = summarize_outcomes(
        records, labels["labels"], label_revision=labels["revision"]
    )

    quality_path = experiment_dir / "quality.json"
    if quality_path.exists():
        quality = json.loads(quality_path.read_text(encoding="utf-8"))
        summary["quality"] = {"episodes": quality["episodes"], "flagged": quality["flagged"]}

    manifest = yaml.safe_load((experiment_dir / "manifest.yaml").read_text(encoding="utf-8"))
    summary["manifest"] = manifest or {}

    if baseline_dir is not None:
        baseline = build_summary(baseline_dir)
        counts = summary["failure_category_counts"]
        baseline_counts = baseline["failure_category_counts"]
        summary["delta"] = {
            "success_rate": (
                summary["success_rate"] - baseline["success_rate"]
                if summary["success_rate"] is not None and baseline["success_rate"] is not None
                else None
            ),
            "failure_category_counts": {
                category: counts.get(category, 0) - baseline_counts.get(category, 0)
                for category in sorted(set(counts) | set(baseline_counts))
            },
        }
    return summary


_PAGE = Template(
    """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LaundryBench report: $experiment_id</title>
<style>
:root { color-scheme: light; font-family: system-ui, sans-serif; color: #172c35; }
* { box-sizing: border-box; }
body { margin: 0; background: #f3f6f5; line-height: 1.5; }
main { max-width: 1120px; margin: auto; padding: 48px 24px; }
.eyebrow { color: #47676b; font-size: .78rem; font-weight: 750; letter-spacing: .13em; }
h1 { font-size: clamp(2rem, 5vw, 3.2rem); line-height: 1.15; margin: 14px 0; }
h2 { margin: 0 0 18px; font-size: 1.15rem; }
.subtitle, .note { color: #526971; }
.subtitle { max-width: 680px; margin-bottom: 28px; }
.run-id { overflow-wrap: anywhere; }
.badge { display: inline-block; border-radius: 99px; padding: 5px 12px;
  font-size: .75rem; font-weight: 750; background: #fff1cc; color: #6e4900; }
.cards { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }
.card, section, details { background: #fff; border: 1px solid #dce5e3; border-radius: 16px; }
.card { padding: 22px; min-width: 0; }
.card-label { font-size: .82rem; color: #526971; }
.value { font-size: 2rem; font-weight: 750; letter-spacing: -.04em; margin: 8px 0; }
.card small { display: block; color: #526971; }
.delta { margin-top: 10px; font-weight: 650; color: #174b58; }
section, details { margin-top: 24px; padding: 24px; }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: .9rem; }
th, td { border-bottom: 1px solid #e5ecea; padding: 13px 12px;
  text-align: left; vertical-align: top; overflow-wrap: anywhere; }
th { color: #526971; font-weight: 650; }
tbody tr:last-child td { border-bottom: 0; }
.bar { display: inline-block; height: .65rem; border-radius: 4px;
  background: #167c80; margin-right: .6rem; max-width: 60%; }
summary { cursor: pointer; font-weight: 700; }
summary:focus-visible { outline: 3px solid #167c80; outline-offset: 5px; }
details .scroll { margin-top: 18px; }
footer { margin: 24px 0 0; color: #526971; font-size: .8rem; }
@media (max-width: 850px) { .cards { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 480px) {
  main { padding: 28px 16px; } .cards { grid-template-columns: 1fr; }
  section, details { padding: 18px; } .card { padding: 20px; }
}
</style>
</head>
<body>
<main>
<header>
<div class="eyebrow">LAUNDRYBENCH / EXPERIMENT REVIEW</div>
<h1>Measure. Inspect. Improve.</h1>
<div class="run-id">$experiment_id</div>
<p>$provenance_badges</p>
<p class="subtitle">A reproducible view of policy outcomes, failure patterns, and evidence quality.
$evidence_note</p>
</header>
<div class="cards" aria-label="Candidate metrics">$cards</div>
<section aria-labelledby="metrics-heading">
<h2 id="metrics-heading">$metrics_title</h2>
<div class="scroll"><table>
$metric_rows
</table></div>
<p class="note">Success rate includes a 95% Wilson confidence interval when available.
Completion time includes reviewed successes only.</p>
</section>
<section aria-labelledby="failures-heading">
<h2 id="failures-heading">Where episodes failed</h2>
<div class="scroll"><table>
$failure_rows
</table></div>
<p class="note">Quality flags are recorded as captured; they are not recomputed from
review labels.</p>
</section>
<details><summary>Reproduction details &amp; provenance</summary>
<div class="scroll"><table>$manifest_rows</table></div>
</details>
<footer>Generated from LaundryBench run artifacts. Compare runs under the same task and protocol.
This report does not establish statistical significance or hardware readiness.</footer>
</main>
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
    denominator = summary.get("metric_episodes", summary["episodes"])
    if not denominator or summary["success_rate"] is None:
        return "— (no reviewed episodes)"
    interval = summary.get("success_rate_ci")
    ci = (
        f"95% CI {_percent(interval[0])} to {_percent(interval[1])}"
        if interval is not None
        else "95% CI unavailable"
    )
    return (
        f"{_percent(summary['success_rate'])} "
        f"({summary['successes']}/{denominator} reviewed; "
        f"{ci})"
    )


def _quality(summary: dict) -> str:
    quality = summary.get("quality")
    if quality is None:
        return "n/a (no quality.json)"
    return f"{quality['flagged']} of {quality['episodes']} recorded episodes flagged"


def _failure_cell(counts: dict[str, int], category: str, scale: int) -> str:
    count = counts.get(category, 0)
    width = round(10 * count / scale) if scale else 0
    return f'<span class="bar" style="width: {width}rem"></span>{count}'


def _provenance(summary: dict) -> tuple[str, str]:
    """Label only explicit manifest evidence; never infer physical execution."""
    implementation = str(summary.get("manifest", {}).get("robot_implementation", ""))
    if implementation in {"mock", "MockRobot"}:
        return "MOCK DATA", "Synthetic software validation; not physical robot performance."
    return "EXECUTION UNVERIFIED", "Physical execution is not established by this report."


def _cards(summary: dict, baseline: dict | None) -> str:
    interval = summary["success_rate_ci"]
    ci_detail = (
        f"95% CI {_percent(interval[0])}–{_percent(interval[1])}"
        if interval is not None
        else "95% CI unavailable"
    )
    quality = summary.get("quality")
    cards = [
        ("Success rate", _percent(summary["success_rate"])
         if summary["success_rate"] is not None else "—",
         (f"{summary['successes']} / {summary['metric_episodes']} reviewed · "
          f"{ci_detail}")
         if summary["metric_episodes"] else
         "No reviewed episodes; confidence interval unavailable"),
        ("Median completion", f"{summary['median_completion_time_s']:.2f}s"
         if summary["successes"] and summary["median_completion_time_s"] is not None else "—",
         "Successful episodes only" if summary["successes"] else "No successful episodes"),
        ("Intervention rate", _percent(summary["intervention_rate"])
         if summary["intervention_rate"] is not None else "—", "Reviewed episodes only"),
        ("Recorded quality flags", str(quality["flagged"]) if quality else "—",
         f"of {quality['episodes']} recorded episodes"
         if quality else "No quality report available"),
    ]
    rendered = []
    for index, (label, value, detail) in enumerate(cards):
        delta = ""
        candidate_n = summary.get("metric_episodes", summary["episodes"])
        baseline_n = baseline.get("metric_episodes", baseline["episodes"]) if baseline else 0
        if index == 0 and baseline is not None and candidate_n and baseline_n:
            difference = 100 * (summary["success_rate"] - baseline["success_rate"])
            delta = f'<div class="delta">{difference:+.1f} pp vs baseline</div>'
        rendered.append(
            f'<article class="card"><div class="card-label">{escape(label)}</div>'
            f'<div class="value">{escape(value)}</div><small>{escape(detail)}</small>'
            f'{delta}</article>'
        )
    return "".join(rendered)


def render_html(summary: dict, baseline: dict | None = None) -> str:
    """Render a self-contained static HTML report; adds a baseline column when given."""

    # Preserve rendering support for callers that construct pre-contract summary
    # dictionaries directly. build_summary always emits these v2 fields.
    summary = dict(summary)
    summary.setdefault("metric_episodes", summary.get("reviewed_episodes", summary["episodes"]))
    summary.setdefault("reviewed_episodes", summary["metric_episodes"])
    summary.setdefault("reviewed_rate", 1.0 if summary["episodes"] else None)
    summary.setdefault("success_rate_ci", None)
    summary.setdefault("pending_episodes", 0)
    summary.setdefault("excluded_episodes", 0)
    summary.setdefault("label_revision", 0)
    summary.setdefault("outcome_schema_version", None)
    if baseline is not None:
        baseline = dict(baseline)
        baseline.setdefault(
            "metric_episodes", baseline.get("reviewed_episodes", baseline["episodes"])
        )
        baseline.setdefault("reviewed_episodes", baseline["metric_episodes"])
        baseline.setdefault("reviewed_rate", 1.0 if baseline["episodes"] else None)
        baseline.setdefault("success_rate_ci", None)
        baseline.setdefault("pending_episodes", 0)
        baseline.setdefault("excluded_episodes", 0)
        baseline.setdefault("label_revision", 0)
        baseline.setdefault("outcome_schema_version", None)

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
        (
            "Reviewed episodes",
            lambda s: f"{s.get('reviewed_episodes', s['episodes'])} / {s['episodes']}",
        ),
        ("Pending episodes", lambda s: str(s["pending_episodes"])),
        ("Excluded episodes", lambda s: str(s["excluded_episodes"])),
        ("Reviewed rate", lambda s: _percent(s["reviewed_rate"])
         if s["reviewed_rate"] is not None else "— (no episodes recorded)"),
        ("Label revision", lambda s: str(s["label_revision"])),
        ("Outcome schema version", lambda s: str(s["outcome_schema_version"] or "n/a")),
        ("Median completion time (s)", lambda s: f"{s['median_completion_time_s']:.3f}"
         if s["successes"] and s["median_completion_time_s"] is not None
         else "— (no successful episodes)"),
        ("Intervention rate", lambda s: _percent(s["intervention_rate"])
         if s["intervention_rate"] is not None else "— (no reviewed episodes)"),
        ("Recorded quality flags", _quality),
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
        metric_episodes = summary.get("metric_episodes", summary["episodes"])
        message = "No reviewed failures." if metric_episodes else (
            "No reviewed episodes." if summary["episodes"] else "No episodes recorded."
        )
        failure_rows = [_row([message])]

    badge, note = _provenance(summary)
    provenance_badges = f'<span class="badge">Candidate: {badge}</span>'
    if baseline is not None:
        baseline_badge, baseline_note = _provenance(baseline)
        provenance_badges += f' <span class="badge">Baseline: {baseline_badge}</span>'
        if baseline_note != note:
            note += " Baseline: " + baseline_note

    return _PAGE.substitute(
        experiment_id=escape(str(summary.get("manifest", {}).get("experiment_id", "unknown"))),
        manifest_rows="\n".join(manifest_rows),
        metric_rows="\n".join(metric_rows),
        failure_rows="\n".join(failure_rows),
        cards=_cards(summary, baseline),
        provenance_badges=provenance_badges,
        evidence_note=escape(note),
        metrics_title="Candidate vs baseline" if baseline is not None else "Run metrics",
    )
