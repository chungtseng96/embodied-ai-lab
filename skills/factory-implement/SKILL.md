---
name: factory-implement
description: "Factory implement for a ticket with a state record: write the failing behavior test, then the smallest change inside the ticket's Files list."
user-invocable: true
---

# Implement

Build the change, test first, inside Files, and push at the end of the phase.
Read the [factory](../factory/SKILL.md) shared rules first. Inputs: the state
record and its workspace path. Confirm `git rev-parse --abbrev-ref HEAD`
prints `BRANCH` before anything else, then read the record's **Constraints**:
each is part of the acceptance, even when the ticket did not label it so.
Read the record's **Operator-run** list too: those criteria get code and a
mock or offline test where one is possible, never a claim.

## Steps

1. **Find what already exists.** Grep for the module, config key, script
   flag, endpoint or contract the ticket names, not the feature's name; read
   the owner and its real callers, and the architecture doc for that
   boundary (the profile's **Standards**). Name the code the change extends,
   with file and line. Re-measure every line number and count the record
   marks "stale until measured" on `origin/$BASE` before planning, and
   record the measured values.

2. **Define the outcome** per the profile's **Verification**
   (define-the-smallest-complete-outcome): one sentence a test can decide,
   and the command that decides it. A change of the kinds the profile's
   **Conventions** name gets a plan or an experiment record at the path
   given there; that file is in scope even when Files omits it. A small
   reversible change gets one acceptance sentence and its check in the
   state record.

3. **Write the failing test first**, at the real boundary (the project's
   `tests/` for Python, `frontend/src/*.test.tsx` for the UI), using the
   mock robot and fixtures, and keep the command and failing output. For an
   `R` ticket the behavior is "output unchanged": record the before-run of
   the suite the ticket names, add no behavior, and treat any golden
   difference as a defect to fix in code; the golden stays as it is.

4. **Write the smallest code that passes**, in small commits that each pass
   the profile's **Standards** build check (**Commit rule** before each).
   Reuse or narrow existing code over a new path. Every existing test stays
   as strict as it was: pass by changing code, never by deleting or
   weakening a test or adding a suppression. Keep the mock path runnable
   (`make demo` must still print a summary when the runner or scripts
   change). Never import LeRobot into `src/laundrybench/` core modules to
   make something work; the adapter boundary is the profile's **Standards**.
   An edit outside Files gets a needs-human entry naming the file and why; a
   B-kind decision (**Ticket kinds**) or a hardware command (the profile's
   **Hardware**) is a hard stop.

5. **Check scope.** **Base** first, then:
   ```bash
   git fetch origin $BASE
   git diff --name-only origin/$BASE...HEAD
   ```
   Every path is in Files, is the plan or experiment record, or has a
   needs-human entry (with unknown scope every path is one, informational
   only). An edit to a **Protected** path is a hard stop, never an
   informational entry, and so is any other hard-stop path.

6. **Push once and record.** Push rule, then an **Implement** section in the
   state record: plan path or acceptance sentence, the failing-then-passing
   test command with its output line (marked `mock`), commit SHAs, pushed
   head, needs-human entries.

## Done when

Acceptance tests pass locally, every commit passes the build check, every
changed path passes step 5, `git rev-parse origin/$BRANCH` equals the
recorded head, and the state line reads `factory-implement · done`.
