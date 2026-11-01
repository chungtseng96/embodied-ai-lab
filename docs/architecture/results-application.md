# Results and manual labeling

## Running it

From the repository root, create a virtual environment with
`python3 -m venv .venv`, then use `make install`, `make frontend-install`,
`make frontend-check`, `make web-demo`, then `make web`. Python 3.11+ and
Node.js 22+ are required. The app opens at `http://127.0.0.1:8765`.

The demo command executes the mock runner with an accelerated clock and seeded
judges to generate two synthetic runs. Their outcome differences are UI test
fixtures, not measured training improvements or physical robot performance.
Existing experiment folders and any labels are preserved.

For actual runs:

```bash
python projects/laundrybench/scripts/serve.py \
  --outputs-root /absolute/path/to/outputs \
  --frontend-dir projects/laundrybench/frontend/dist
```

The outputs directory must exist. Use a single writer server per directory.
The operator server binds only to loopback. It serves static assets and the
artifact API from one origin; this is a local operator app, not a public cloud
labeling service. Frontend development uses `. .venv/bin/activate` followed by
`npm run dev` from the root, after the same Python/frontend installation.
The development proxy must remain local;
it rewrites request-origin headers for the local Python API.

## Review workflow

1. Choose a run; inspect its provenance and whether execution is mock/unverified.
2. Optionally select another run as baseline. Comparisons are descriptive; check
   task, protocol and sample sizes before interpreting differences.
3. Search/filter the episode queue and inspect evidence beside the labeling panel.
4. Review success/failure, or exclude unusable evidence with a required reason.
5. Save the review. Pending/reviewed/excluded counts and reviewed-only metrics refresh.

The task defines success as autonomous: an assisted episode cannot count as
success. Intervention and failure reason are separate; for example an assisted
missed grasp keeps `missed_grasp`. Labels are post-episode verdicts, not
per-frame action annotations or live robot commands. Recorded video is registered
through the [media contract](media-contract.md); missing or unsupported media
remains explicit. Media registration does not capture new camera footage.

## Evidence and persistence

The API reads `manifest.yaml`, `episodes.jsonl`, `traces/steps.jsonl` and optional
`quality.json`. Manual labels are atomically stored in `labels.json` beside them.
Original episode and trace files are never overwritten by labeling. The frontend,
API, CLI JSON summaries and HTML reports use one shared label-aware calculation.
Only reviewed, non-excluded episodes enter outcome metrics; pending records and
exclusions remain visible as separate counts. A run with no reviewed episodes
has unavailable rates rather than a zero success rate. Labels include a schema
version and revision; legacy sidecars remain readable and migrate on the next
write. See the [outcome contract](outcome-contract.md).

Writes carry the expected run revision. Stale tabs receive HTTP 409 and must
reload before retrying; unsaved form edits remain available. Navigation warns
before discarding unsaved edits. Sidecars reload after server restarts.
Recorded quality flags remain the original check results, including any old
missing-label flag. They are deliberately not represented as recomputed checks.

Traces show recorded host timestamps and requested targets; the adapter's actual
possibly clipped commands are not yet captured by the runner. Missing/non-finite
samples appear as gaps. A robot implementation name alone does not verify
physical execution.

## Validation

`make check` verifies Python/HTTP persistence, conflicts, schema and path
boundaries. `make frontend-check` runs component behavior tests, typechecks and
builds production assets. The UI was also exercised against the real Python API
in a managed browser: labels saved, summary metrics changed, and labels survived
a page reload. No physical hardware or GPU training was exercised.
