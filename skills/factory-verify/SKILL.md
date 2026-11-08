---
name: factory-verify
description: Factory verify for a branch with commits to prove, or after any fix to one: the verification gate, the PR, one CI observation, the proof ledger.
user-invocable: true
---

# Verify

An ordered wrapper over the profile's **Verification**, which wins where
they differ, except that the factory's shared **CI wait** (its `verdict`,
bounded re-observations, the pause) replaces any other CI observation rule
inside a factory run. Read the [factory](../factory/SKILL.md) shared rules
first. Every check passes as written: a check that cannot pass without
weakening or skipping it stops the run `blocked`.

## Steps

1. **Pick the checks from the actual diff**, including untracked files.
   **Base** first (a parent may have merged), then:
   ```bash
   git fetch origin $BASE
   git status --short
   git diff --name-only origin/$BASE...HEAD
   ```

2. **Focused regression and positive control.** Run the acceptance test from
   the state record and a positive control where the change could block good
   behavior, at the real boundary with the mock robot and fixtures. Record
   each as `mock`.

3. **Component checks** for the touched components: the profile's
   **Component checks** as the diff needs, after preparing only their
   prerequisites (the profile's **Verification**,
   make-the-test-environment-ready-first). A check whose environment this
   host lacks (no LeRobot venv, no FFmpeg, no browser harness) is recorded
   under **Not verified** with the missing prerequisite named, never
   skipped silently.

4. **The pre-push gate**: the profile's **Pre-push gate** lines for the
   kinds of path the diff touches. A local failure is fixed in its own
   commit and the gate reruns from step 2.

5. **`R` ticket: output unchanged.** The suite the ticket names (the
   profile's **Goldens**). Any difference is a defect. No suite named:
   record it under **Not verified**.

6. **Push and open the PR.** `gh pr list --repo $REPO --head $BRANCH --state open --json number`
   first: an existing PR loses `factory-ready` before the push (push rule).
   Then the push rule, with `-u` so the upstream is `BRANCH`, not the
   parent's branch.
   No PR: write the body from the profile's **PR body** (the repository's
   pull request template, filled from this skill's steps 2 to 4, with the
   CI line `pending for <SHA>` until step 7 and the **Factory run** note),
   and open it ready for review (a draft runs no CI here):
   ```bash
   gh pr create --repo $REPO --base $BASE --head $BRANCH --title "<ticket>: <title>" --body-file <file>
   ```
   Write `PR: #<n>` into the state record's header. Apply the profile's
   **Goldens** PR-label rule if it has one.

   Then **request the first review** per the profile's **Reviews**: a
   fresh-context reviewer at this exact head, whose verdict is posted on
   the PR so it outlives the session. Record `round 1 · review requested
   @<sha>`; the review overlaps the CI wait.

   Then, on every pass through this step, the **Cascade** (shared rules):
   `python3 scripts/factory_linear.py children $T`; for each row with
   `onlyParent` true and `factoryLabel` null, `set-label <child> ready`.
   Record `released: <ids or none>`.

7. **One CI wait**: `SHA=$(gh pr view <n> --repo $REPO --json headRefOid --jq .headRefOid)`,
   then the shared **CI wait** command and its `verdict`. A CI failure is
   recorded with the failing check and run link and the phase still ends
   `done`; babysit owns the repair. Where the profile's **Goldens**
   workflow runs on the PR, also read its check for `SHA`; for an `R`
   ticket that is the golden result.

8. **Write the proof ledger** as a **Verify** section in the state record,
   above any earlier one, which stays marked `stale @<its sha>`:
   ```markdown
   **Verify** · head `<full SHA>` · base `<base>` · patch-id `<git diff origin/$BASE...HEAD | git patch-id --stable>`
   - Verified (mock): <claim> — <command and the output line that proves it>
   - Not verified: <path or criterion> — <why: operator-run, missing prerequisite, no suite>
   - CI: `verdict` <verdict> at `<full SHA>` · <run link>
   - Goldens (`R` only; the profile's **Goldens**): <suite> <passed | failed | pending> at `<full SHA>`
   ```
   Every **Operator-run** criterion from the record sits under **Not
   verified** as `operator-run`. A change to the profile's **Impact** risk
   surface accounts for it in one list or the other. An empty **Not
   verified** claims you exercised everything, which a factory run on a
   ticket with physical criteria can never claim.

## Done when

Every changed path from step 1 sits in **Verified** or **Not verified**, CI
at the head has the `verdict` green or failed, an `R` golden result names the
head or sits under **Not verified**, the PR exists with a review requested
at its head, and the state line reads `factory-verify · done`.
