# Experiment context and run comparisons

LaundryBench keeps generated run evidence immutable and stores optional human
context in a versioned `experiment.json` sidecar beside `manifest.yaml`,
`episodes.jsonl`, and `labels.json`. This preserves run IDs and the original
manifest hash while allowing an operator to explain why a run exists and link
its evidence.

## Sidecar schema

`experiment.json` is schema version 1. Its revision starts at zero and advances
on each successful CLI update. `name`, `hypothesis`, and `what_changed` are
optional human-readable strings. Task and protocol identifiers and versions
are explicit fields; dataset identity and revision, checkpoint identity, and
effective configuration overrides are recorded separately. Evidence links
carry a label and an `http` or `https` URL without embedded credentials.
Unknown fields, unsupported schema versions, malformed types, non-finite
numbers, and unsafe URLs are rejected.

The manifest's `config_hash` continues to describe the original source
configuration bytes. `effective_overrides` describes runtime overrides applied
to that source and does not replace or rewrite the source hash. The sidecar is
not a source of robot commands and is never written by the web server.

Create a sidecar with:

```bash
python projects/laundrybench/scripts/set_run_metadata.py \
  --run-dir outputs/exp-001-baseline --metadata-file /tmp/context.json
```

For an update, pass `--expected-revision N` using the revision returned by the
previous write. Creation refuses to replace an existing file; updates reject a
missing or stale expected revision. The command writes through a temporary
file and atomically replaces the sidecar. `manifest.yaml` and episode evidence
are not changed. Updates are serialized with an advisory file lock using
`fcntl`, available on the project's Linux and macOS development hosts.

## Compatibility and outcomes

Run detail and list responses include `experiment`, which is a normalized
sidecar object or `null` for older runs. Run IDs remain the stable identifiers.
The API route
`GET /api/runs/{candidate}/compare/{baseline}` returns both runs' current
reviewed outcome summaries and a compatibility status:

The response also includes both normalized human context objects (or `null`)
and the label revision used for each summary. An explicit acknowledgment can
be sent as `?acknowledge_incompatible=1`; the response still retains its
compatibility status and reasons, while returning descriptive differences.

| Status | Meaning | Delta |
| --- | --- | --- |
| `matched` | Task and protocol IDs and versions are present and equal. Other differences are returned as context advisories. | Included |
| `mismatched` | A task ID/version or protocol ID/version differs. | `null` |
| `unknown` | A required task or protocol ID/version is missing from either run, unless another required value already mismatches. | `null` |

The comparison uses the shared reviewed, non-excluded outcome summaries from
`evaluation.outcomes`; provisional recorded outcomes are not treated as
reviewed. The delta contains reviewed counts, successes, rates, and failure
category count differences. A zero-reviewed rate stays `null`. Dataset,
checkpoint, source config hash, and effective override differences are reported
as advisories because callers must describe evaluation condition changes
through the protocol version. Without acknowledgment, mismatched or unknown
comparisons never expose computed deltas. No episodes are paired automatically;
clients can offer explicit episode selection using the episode IDs and
evidence returned by run detail. These are descriptive comparisons, not
statistical significance claims.

The local web viewer is intended for an operator on a trusted machine. Evidence
URLs may be visible to anyone who can read the run artifacts; only public or
otherwise shareable links should be recorded.
