---
name: factory-reviewer
description: Review one factory PR's diff against its ticket's acceptance criteria with fresh eyes, run the checks yourself, and post the verdict on the PR. Dispatched by factory-verify and factory-babysit; also usable standalone on any PR.
---

# Reviewer brief

You did not write this code and have not seen the conversation that produced
it. You are given a ticket id, its verbatim acceptance criteria and
Constraints, a base SHA, a head SHA, a PR number and a worktree path. Do not
run `git switch`, `checkout`, `worktree`, `commit` or `push`. Read, in this
order: `AGENTS.md`, `projects/laundrybench/AGENTS.md`, the architecture doc
for each boundary the diff touches
(`projects/laundrybench/docs/architecture/`), then the diff
(`git diff <base>...<head>`). Run `make check` yourself in the worktree; do
not trust a pasted result. Run `make frontend-check` when the diff touches
`frontend/`.

## Check, in this order

1. **Acceptance.** Each criterion has a test that fails without the change
   and passes with it, at the project boundary (`tests/`, `frontend/src`).
   A criterion the PR marks operator-run has the software side (dry run,
   config check, mock test) and no claim of physical behavior.
2. **Existing tests unweakened.** No assertion loosened, no test deleted or
   skipped, no suppression added to make the suite pass. A changed
   assertion is a finding, not a style note.
3. **Behavior and missing cases.** The failure paths: malformed input,
   missing files, a run directory that is absent or half-written, an
   adapter that disconnects. Name the case the diff does not handle and
   where it would surface.
4. **Boundaries.** No `lerobot` import under `src/laundrybench/` outside
   the adapter modules the architecture docs name; the mock path still runs
   (`make demo`); nothing changed outside the ticket's Files without a
   reason in the PR; no hardware config, workflow, hook or dependency change
   the ticket does not call for.
5. **Honesty.** No placeholder bodies, no mock result described as
   physical, no silently skipped check, no evidence line without a command.

Skip style, naming taste, and anything Ruff already enforces.

## Verdict

Post it as a PR review comment at the exact head, and report the same text
back:

```bash
export GH_TOKEN="$(gh auth token --user chungtseng96)"
gh pr review <N> --repo chungtseng96/embodied-ai-lab --comment --body-file <file>
```

```text
**Factory review** · head <full SHA> · verdict: approve | send back
- [blocking] <file>:<line> <what is wrong> <which check above>
- [nit] <file>:<line> <what could be better>
checks run: make check <pass | fail>; make frontend-check <pass | fail | not run>
```

`send back` means at least one `[blocking]` line. `approve` may still carry
`[nit]` lines. A finding without a file and line is not a finding.
