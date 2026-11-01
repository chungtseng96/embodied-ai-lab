# LaundryBench outcome and review contract

**Status:** Implemented for local API and offline reports.

`episodes.jsonl` is immutable run evidence. A recorded `success` value is a
provisional outcome; it is useful for inspection but does not establish a human
review. Review annotations live in `labels.json`, and readers resolve the two
sources at request or report time. API responses and CLI-generated
`summary.json` / `report.html` use the shared rules in
`laundrybench.evaluation.outcomes`.

The evaluator's immediate terminal summary is based on its recorded automatic
`EpisodeResult` values. It describes the recorded run output, not reviewed
human-labeled performance. The report CLI reads `labels.json`; until episodes
are reviewed, its headline metrics remain unavailable and its pending count is
shown explicitly.

## Sidecar formats

Legacy v1 remains readable without modifying it:

```json
{"revision": 1, "labels": {"episode-001": {
  "success": true,
  "intervention": false,
  "failure_category": null,
  "notes": "operator review",
  "revision": 1,
  "updated_at": "2026-11-01T00:00:00+00:00"
}}}
```

V1 labels are interpreted as reviewed. A successful write upgrades the
sidecar envelope to v2; it does not change `episodes.jsonl`:

```json
{"schema_version": 2, "revision": 2, "labels": {
  "episode-001": {
    "status": "reviewed",
    "success": true,
    "intervention": false,
    "failure_category": null,
    "notes": "operator review",
    "revision": 1,
    "updated_at": "2026-11-01T00:00:00+00:00"
  },
  "episode-002": {
    "status": "excluded",
    "exclusion_reason": "trace is incomplete",
    "revision": 2,
    "updated_at": "2026-11-01T00:01:00+00:00"
  }
}}
```

The API continues to accept the original reviewed PUT body:

```json
{"success": false, "intervention": false,
 "failure_category": "timeout", "notes": "task did not finish",
 "expected_revision": 0}
```

It is equivalent to `status: "reviewed"`. Exclusion uses a separate compact
body and requires a nonblank reason:

```json
{"status": "excluded", "exclusion_reason": "trace is incomplete",
 "expected_revision": 1}
```

Both operations use the existing optimistic global sidecar revision. A stale
revision is rejected. Reviews obey the task-success rule: success cannot be
combined with intervention or a failure category, and a failure requires a
category. Exclusion records no replacement outcome and leaves the recorded
outcome visible as the effective value.

## Resolved outcomes and metrics

Every API episode includes `original_outcome`, `effective_outcome`,
`review_status`, and `outcome_source`. Status is `provisional`, `reviewed`, or
`excluded`; source is `recorded` or `label`. The legacy `annotation.status`
remains `unlabelled`, `labelled`, or `excluded` for existing UI consumers.

Summary `episodes` remains the total number of recorded episodes. The explicit
counts are `reviewed_episodes`, `pending_episodes`, `excluded_episodes`, and
`metric_episodes`. Headline metrics use reviewed, non-excluded labels only;
pending recorded outcomes never silently become human-reviewed results.
`successes`, `success_rate`, `intervention_rate`, completion time, and failure
counts use that denominator. `reviewed_rate` is reviewed / recorded. When
`metric_episodes` is zero, rates and the Wilson interval are `null` (Python
`None`, serialized to JSON `null`) rather than a misleading zero. Summary metadata includes
`outcome_schema_version` and the current `label_revision`.

Quality flags remain separately recorded quality evidence. They are not
rewritten or used to infer review status or outcome labels.
