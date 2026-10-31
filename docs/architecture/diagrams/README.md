# Architecture diagrams

Source files are `.tldraw` documents (open with the tldraw desktop app). The
`.svg` next to each one is a render for review; regenerate it after editing
the source so the two never disagree.

| Diagram | What it shows |
| --- | --- |
| [`laundrybench-proposed-architecture`](laundrybench-proposed-architecture.svg) | Component view: evaluation runner, episode recorder, metrics and report, failure-driven data change, artifact layout, open questions, and the proposed mock-only vertical slice. Colour key: blue = LaundryBench owns, grey = reused from LeRobot, orange = swappable backend, violet = where it runs, red = open questions. |
| [`laundrybench-run-workflow`](laundrybench-run-workflow.svg) | One experiment run end to end (EXP-001), the inside of one episode, the EXP-001 to EXP-002 feedback loop, and the observability surfaces. Green = human does it, blue = software does it. |

Both diagrams are the design of record for the evaluation and evidence side
of LaundryBench. Where they disagree with the current code, the gap is tracked
in [`docs/plans/2026-10-31-laundrybench-design-review.md`](../../plans/2026-10-31-laundrybench-design-review.md).
