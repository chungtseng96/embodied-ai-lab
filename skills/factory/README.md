# Factory: how one ticket becomes one PR

The factory is a fixed pipeline, not a conversation. A script decides the
order; agents are nodes it calls; `make check` is the judge it trusts; a
human merges. Background and sources:
[`docs/plans/2026-10-31-software-factory-research.md`](../../docs/plans/2026-10-31-software-factory-research.md).

```text
Linear ticket (Todo, unblocked)
  -> worktree for the ticket
  -> implementer   (brief: implementer.md)   one task, TDD, commits
  -> make check    (Stop hook enforces it; CI repeats it)
  -> reviewer      (brief: reviewer.md)      fresh context, diff vs task spec
  -> implementer again, once, if the reviewer sends it back
  -> PR titled "JWA-<n> <task title>", ticket -> In Review with evidence
  -> human merges  (the only approval inside the loop)
```

## Rules

1. One ticket per pipeline run. The ticket's plan section is the spec; no
   other prompt is written per ticket.
2. Implementer and reviewer never share a context. The reviewer sees the
   diff, the task section, and `AGENTS.md`, not the implementer's reasoning.
3. Evidence before status. A ticket moves to In Review only with the
   `make check` output and the commit SHA in a comment.
4. Hooks only for zero-exception rules. Today: `make check` on stop when
   Python changed; no edits under `outputs/`, venvs, calibration,
   checkpoints, media, or the hooks themselves (`.claude/settings.json`).
5. At most three tickets per run, then a human reads the PRs. Parallel lanes
   only while review keeps up.
6. A reviewer finding that recurs twice becomes an `AGENTS.md` gotcha, a
   test, or a hook. Nothing else is added to the factory until something
   recurs.

## Rework tally

Keep in the Linear ticket, one line: `send-backs: n | CI after push: pass|fail | human comments: n`.
Structure is added only where this number is highest across tickets.
