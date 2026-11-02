# Results UI

## Current implementation

The existing `scripts/report.py` command produces a self-contained experiment
review page from run artifacts. The report has responsive KPI cards, candidate
and baseline comparison, a success-rate delta in percentage points, failure
bars, and collapsible reproduction details. It works offline without a server
or external assets.

The report explicitly labels the known `mock` / `MockRobot` implementation as
mock data. Other values show execution as unverified: an adapter name alone
does not prove a physical run. A future physical-run evidence contract should
precede any physical-performance badge.

Generate a report after evaluation:

```bash
cd projects/laundrybench
python scripts/report.py --experiment-dir outputs/exp-000-mock-smoke
```

Add `--baseline PATH` to compare an experiment against an existing run. The
CLI writes `summary.json` and `report.html` beside the source artifacts.

## Next increments

1. Add an episode table with failed/flagged filtering, backed by the existing
   episode and quality artifacts. Keep aggregate and per-episode results aligned.
2. Add evidence drilldown with synchronized video and action/joint traces after
   the video-capture and media-reference contracts are implemented. Current
   traces record camera slot names, not actual video files.
3. Add a project overview page with a short task demonstration, architecture,
   reproducible command, and an honest baseline/candidate improvement story
   once physical evidence exists.

## Acceptance criteria

- Single-run and comparison reports remain self-contained and work offline.
- Mock execution remains visibly identified; unknown provenance is explicit.
- Numbers come from artifacts, with sample size and confidence interval shown.
- Small screens retain readable cards and horizontally scrollable tables.
- No physical success rate or improvement claim is fabricated for presentation.
- Python checks pass and mobile/desktop rendering is reviewed before release.

The redesign is an experiment artifact, not a multi-run dashboard or labeling
application. Those surfaces should be added when real workflows justify them.
