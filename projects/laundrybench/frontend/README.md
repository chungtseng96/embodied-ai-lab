# LaundryBench experiment review and operator UI

A React + TypeScript operator frontend for the local Python artifact server.
It reads actual experiment artifacts, compares runs, inspects per-episode
traces, and saves human review labels. It also has a read-only `/operator`
route that displays the follower arm's live joint telemetry from LeLab. Robot
motion and camera control remain in LeLab; this frontend never sends movement
commands.

## Run the complete application

From the repository root:

```bash
python3 -m venv .venv
make install
npm ci --prefix projects/laundrybench/frontend
npm run build --prefix projects/laundrybench/frontend
.venv/bin/python projects/laundrybench/scripts/serve.py \
  --outputs-root projects/laundrybench/outputs \
  --frontend-dir projects/laundrybench/frontend/dist
```

Open the URL printed by the Python server. Generate a mock experiment with
`make demo` if the outputs directory is empty. Mock results are clearly marked
and have no physical-performance meaning.

## Live operator telemetry

Start LeLab first, then open the built or development frontend at
`/operator`. The dashboard defaults to `http://127.0.0.1:8000` for LeLab; use
`/operator?lelab=http%3A%2F%2F127.0.0.1%3A8000` to make the endpoint explicit.
It shows the six follower joint positions, WebSocket freshness, LeLab status,
and a bring-up checklist. A live frame is only available while LeLab
teleoperation is active. The dashboard is intentionally read-only.

For frontend development, keep the API server on port 8765 and run
`npm run dev --prefix projects/laundrybench/frontend` in a second terminal.
Vite forwards `/api` to the loopback-only backend. The development proxy rewrites
Origin to the backend's local origin; production uses one Python origin for
both the built frontend and API. Do not expose the development proxy publicly.

## Validation

```bash
npm run build --prefix projects/laundrybench/frontend
npm test --prefix projects/laundrybench/frontend
```

The build type-checks TypeScript before bundling. Tests exercise label payloads,
revision conflicts, network failures, and empty data. Browser QA should include
real backend artifacts on desktop and mobile widths, saved-label persistence
after reload, baseline selection, episode filters, and trace inspection.

## Data and labeling

- `/api/runs` lists artifact-backed runs. No network error falls back to fake data.
- `/api/runs/:id` supplies manifest, metrics, episodes, quality, and label revision.
- `/api/runs/:id/episodes/:episode/trace` supplies recorded joint samples.
- `PUT /api/runs/:id/episodes/:episode/label` saves a label with the expected run
  revision. A conflict preserves form edits and offers an explicit reload.
- The backend stores labels separately from original episode evidence; refreshed
  run metrics use the label overlay. Original outcomes remain visible.
- An intervention is a failed episode. Selecting
  intervention sets a failed outcome and defaults its category when needed; the
  operator can retain a more specific failure reason. Selecting success clears
  intervention.
- Video is explicitly unavailable until the evidence contract supports media.
- Known mock implementations are labeled `MOCK DATA`. Other implementations are
  unverified; naming a robot adapter does not prove physical execution.

The UI uses browser-native SVG for traces, system fonts, and no external chart
service or asset CDN. The built application works without external assets.
