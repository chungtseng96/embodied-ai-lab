# <task> — loop state

Copy to `LOOP-STATE.md` at the repo root (gitignored). Read it FIRST every run.
One row per item. Evidence means a command and its output, a file path, or a
test name, not "done". Keep this file durable across context changes: record
the actual base and head SHAs, tested SHA, worktree state, environment, and
remaining work. A dirty worktree is not a tested commit.

**Base:** <branch/ref and SHA>
**Head:** <branch/ref and SHA>
**Tested SHA:** <SHA, or `working tree` with dirty paths listed>
**Worktree:** <path; clean | dirty: exact paths>
**Environment:** <Python path/version, relevant optional packages, OS/device; note unavailable hardware>
**Commands:** <exact commands and result/output location>

**Stop condition:** <all items done or blocked | N items this run>

| Item | Status | Evidence / what changed | Next |
|------|--------|-------------------------|------|
| <item> | todo | | |
| <item> | in progress | | |
| <item> | done | `make check` → exit 0, <actual pytest summary> | |
| <item> | blocked | why, and what was tried | |
| Needs me | ready | decisions only a human can make: spend money, delete data, move the robot, change the evaluation protocol | |

**Remaining work / blockers:** <specific next action, or `none`>

Status values: `todo`, `in progress`, `done`, `blocked`, `ready` (Needs me row only).
