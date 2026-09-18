# <task> — loop state

Copy to `LOOP-STATE.md` at the repo root (gitignored). Read it FIRST every run. One row per
item. Evidence means a command and its output, a file path, or a test name, not "done".

**Stop condition:** <all items done or blocked | N items this run>

| Item | Status | Evidence / what changed | Next |
|------|--------|-------------------------|------|
| <item> | todo | | |
| <item> | in progress | | |
| <item> | done | `make check` → `GATE PASS`, 6 passed | |
| <item> | blocked | why, and what was tried | |
| Needs me | ready | decisions only a human can make: spend money, delete data, move the robot, change the evaluation protocol | |

Status values: `todo`, `in progress`, `done`, `blocked`, `ready` (Needs me row only).
