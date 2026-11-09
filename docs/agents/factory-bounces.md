# Factory bounce log

A bounce is a human sending a factory PR back at review, or waiving a
dismissed reviewer finding that turned out to be real. One line each, newest
first. The factory reads this file: `factory-simplify` opens it before judging
a diff, and `factory-babysit` points recurring dismissals here.

A reason that appears twice graduates: into a line in `AGENTS.md`, a test, a
hook under `.claude/hooks/`, or a check in
[`skills/factory/reviewer.md`](../../skills/factory/reviewer.md). Mark the
entry `graduated: <path>` when it does. Roles only, no names.

| Date | Ticket · PR | Bounce reason | Phase that should have caught it | Graduated |
|---|---|---|---|---|
| | | | | |
