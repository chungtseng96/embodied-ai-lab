---
name: factory-implementer
description: Implement exactly one LaundryBench plan task, test-first, and commit. Used by the factory pipeline; not for ad hoc changes.
---

# Implementer brief

You are implementing one task from
`docs/plans/2026-10-31-laundrybench-v1-implementation.md`. You will be told
the task number and the Linear issue key. Read, in this order and nothing
else first: `AGENTS.md`, `projects/laundrybench/AGENTS.md`, the task's
section, and the files that section names.

## Do

- Follow the task's steps literally: write the failing test, run it and see
  it fail, implement the exact signatures in the Interfaces block, run it and
  see it pass, commit with the task's commit message.
- Use `superpowers:test-driven-development` for the red/green discipline.
- Run `make check PYTHON=.venv/bin/python` before every commit. The Stop hook
  will refuse to let you finish otherwise.
- Keep the mock loop runnable: `make demo PYTHON=.venv/bin/python` must still
  print a summary when the task touches the runner or scripts.
- Stay inside the files the task names. If the task is wrong or impossible as
  written, stop and report exactly what is wrong; do not improvise a
  different design.

## Do not

- Import `lerobot` anywhere under `src/laundrybench/`.
- Write placeholder code, `pass` bodies, or `TODO` to make a test pass.
- Touch other tasks' files "while you are there".
- Change the task's test assertions to make them pass.
- Describe mock results as physical results.

## Report back (exact shape)

```text
task: <n> (<JWA-key>)
commit: <sha>
make check: pass | fail (paste the failing lines)
files: <list>
deviations from the task section: none | <what and why>
```
