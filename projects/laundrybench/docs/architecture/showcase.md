# Curated static showcase

The hosted showcase is generated from exactly two fresh LaundryBench mock-runner
examples: `exp-901-mock-candidate` and `exp-900-mock-baseline`. It never reads
the operator's outputs directory or accepts run paths. Each run uses the same
task and protocol identifiers, while hypothetical checkpoint identities and
effective overrides make the comparison context explicit. These metadata are
illustrative; no checkpoint or training run is represented.

The generated labels are synthetic UI fixtures copied from the seeded
`MockSuccessJudge` outcomes. They let the shared reviewed-only summary and
comparison code exercise the same shape as a reviewed run. They are not human
annotations, robot performance, or evidence that a candidate improved over a
baseline. Small seeded samples are included only to demonstrate the results
workflow. The included three-second MP4 comes from ffmpeg's built-in `testsrc2`
pattern and contains no camera footage.

## Export contract

Build a fresh, read-only showcase frontend, then export its two synthetic runs:

```sh
VITE_SHOWCASE=1 npm run build --prefix projects/laundrybench/frontend -- --outDir dist-showcase
python projects/laundrybench/scripts/build_showcase.py \
  --output-dir projects/laundrybench/frontend/dist-showcase \
  --source-commit <40-character-lowercase-commit-sha> \
  --walkthrough-video /absolute/path/to/showcase-demo.webm
```

`VITE_SHOWCASE=1` is required so the static build disables all write requests.
`ffmpeg` must also be installed. Before generating media or writing files, the
exporter checks the output tree. It accepts an empty directory for library use,
or a fresh Vite tree containing only `index.html` and the hashed JS/CSS assets
referenced by that file. It rejects symlinks, unreferenced assets, stale
showcase data, and all other files without changing them. The CLI requires the
frontend tree to exist. If preflight rejects `dist`, inspect and preserve its
contents, then create a fresh Vite build before retrying.

The exporter adds API snapshots under `data/`: run index and detail,
per-episode trace and media manifests, plus compatible and acknowledged
comparisons. Media is written to `/media/<sha256>.mp4`; each manifest stream's
`url` points to that immutable content-addressed asset. `showcase.json` includes
the source repository and commit, selected candidate and baseline, synthetic
evidence marker, limitations, a null walkthrough URL until a CI-recorded clip
is available, and SHA-256 inventory entries for the static files.

## Optional software walkthrough recording

The Browser acceptance workflow records a browser-only UI tour in
`projects/laundrybench/e2e/tests/showcase.spec.ts`; its `page.video()` output is
saved as `showcase-demo.webm`. After a successful GitHub Actions run, open that
exact workflow run for the source commit and download the
`laundrybench-showcase-demo` artifact. The workflow keeps this run-associated
artifact for 14 days; it also contains the Playwright trace. Extract the
artifact and pass the recording's local path to `--walkthrough-video` as shown
above. That recording shows the software walkthrough only; it is not robot or
camera footage. The per-episode MP4 remains a separate ffmpeg-generated
synthetic test pattern.

The optional recording must be a regular, non-symlink local `.webm` or `.mp4`
file, non-empty and no larger than 50 MiB. It is copied byte-for-byte to
`/media/<sha256>.<suffix>`, and the manifest URL and SHA-256 inventory identify
that copy. When the option is omitted, `walkthrough_video_url` stays `null`.
Generated showcase media belongs in the build output and must not be committed.

No source run artifacts such as YAML manifests, JSONL logs, or labels sidecars
are copied as raw files. Exported detail JSON is produced through the shared
`RunStore`, including the canonical outcome summary and context. Trace and
media manifests also pass through the current readers before serialization.
