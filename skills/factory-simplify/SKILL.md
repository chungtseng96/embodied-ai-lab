---
name: factory-simplify
description: "Factory simplify, after implement or on any branch whose diff should shrink: a behavior-preserving pass against the repo profile's **Standards**."
user-invocable: true
---

# Simplify

Read the diff once more, as the reviewer who will see it cold. The
implementer solved the ticket; this phase removes what it rationalised on the
way. Behavior is frozen: the acceptance tests pass before and after every
commit here. Read the [factory](../factory/SKILL.md) shared rules first.

## Steps

1. **Read the whole diff**, not the last commit. **Base** first, then:
   ```bash
   git fetch origin $BASE
   git diff origin/$BASE...HEAD
   ```
   Then open what the diff is judged against: the profile's **Standards**
   (the instruction files, the architecture doc for each boundary the diff
   touches, and the bounce log entries naming this phase or these files). A
   path that does not exist at `origin/$BASE` is recorded as absent and
   skipped. Read the record's **Constraints** and **Protected** paths too:
   they are acceptance.

2. **Look for these, in this order.**
   - **A Constraint the diff breaks**, or any change to a Protected path.
     Fix it in code; one that cannot be fixed without changing behavior is
     a hard stop.
   - **A rule the diff breaks.** Check every changed hunk against each
     instruction file and architecture doc opened in step 1 and name the
     file and bullet for every violation; a rule is checkable, so a
     violation has a line. Fix what a rule names; a boundary the diff bends
     without breaking a rule is fixed when the fix preserves behavior,
     otherwise it goes to the record as a needs-human entry.
   - **Something that already existed.** A helper, conversion, fixture,
     config loader or test helper the diff adds that the project already
     has. Grep for the shape, not the name. Use the existing one; delete the
     new one.
   - **A second path beside the first.** A new function or branch that does
     what an existing one does for one more case. Extend the existing one.
   - **Growth past a limit.** A function the diff made longer, deeper or
     wider in parameters, or that was over a limit and grew. Extract the part
     the diff touched into a named step; the rest keeps its shape.
   - **Comments and names that explain the mechanism instead of the
     intent.** Rename or delete; a comment that restates the code goes.
   - **Scope that is not the ticket.** A drive-by edit outside the change's
     reason. Revert it, unless Files or a needs-human entry already covers it.

   Leave as they are: formatting the diff did not touch, code outside the
   diff, anything whose change would alter behavior or test output.

3. **Change in small commits** (**Commit rule** before each), one kind of
   simplification each, running the acceptance test from the state record's
   **Implement** section after each. On an `R` ticket also keep the recorded
   before-run output identical. Drop any simplification that changes a
   test's expectation.

4. **Push and record.** Push rule. Add a **Simplify** section to the state
   record: the instruction files, architecture docs and bounce entries
   checked (or `absent`), each violation found with its rule and the commit
   that fixed it, then each other commit with one line of what it removed,
   or `no change` with the one sentence saying what was checked.

## Done when

All six kinds in step 2 were checked against the whole diff, every rule
violation found is fixed, the acceptance test and the profile's
**Standards** full build check (plus its **Component checks** as the diff
needs) pass at the new head, the diff is no larger than before except for
lines a rule fix required, `git rev-parse origin/$BRANCH` equals the
recorded head, and the state line reads `factory-simplify · done`.
