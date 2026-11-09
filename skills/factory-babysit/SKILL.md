---
name: factory-babysit
description: "Factory babysit for a factory PR to drive to merge-ready, or any stacked PR whose base or parent moved: conflicts, restack, reviewer findings with a fresh re-review each round, CI at the exact head, proof-of-done packet, `factory-ready`."
user-invocable: true
---

# Babysit

Drive one PR to merge-ready and stop there. Merge-ready: CI green at the
current head, every reviewer finding answered at that head, zero open
blocking findings, no conflict with the base, body current. Clear blockers
in this order: conflicts, review findings, CI. Read the
[factory](../factory/SKILL.md) shared rules first.

After any push, set `SHA` again from `gh pr view`; earlier CI and review
results are void unless step 5 carried them over on an unchanged patch-id.

**Reviewer.** One, as the profile's **Reviews** installs it: a fresh-context
subagent that never saw this session, briefed with the reviewer brief, the
ticket's acceptance criteria, the base and head SHAs and the diff, which
runs the checks itself and posts its verdict on the PR at the exact head.
This run requests it (verify requests the first; step 7 requests one if
none exists for the final head). A review must exist for the final head,
unless a human waived it (**Resume** rule). A finding is **closed** when
its thread holds a reply naming the fix commit, or a disproof recorded as
`dismissed:` in the record, or when the reviewer's next verdict at a later
head no longer lists it.

**Review rounds.** Round 1 is the review of the first head. Every
hand-edited push, whether it fixes a review finding or CI, plus the
re-review it requests, is one more round; a clean base merge is not a round
and is never limited. Three rounds is the cap, so at most two fix pushes:
after round 3 no hand-edited push happens, and any open blocking finding or
red CI ends the run `blocked` with the list in needs-human. **Blocking
findings** are the severities the profile's **Reviews** marks blocking; the
others are answered but never block.

**Docs-only diff** (as the profile's **Conventions** define it): check mode.
Steps 1 to 4; steps 5 and 6 only if steps 1 to 4 made a commit (a **Base**
merge included); then 7 and 8. Step 7's waits still apply, and a newly
posted review sends you back to step 4 once; no second fix push.

## Steps

1. **Pin the PR.**
   ```bash
   gh pr view $N --repo $REPO --json state,isDraft,baseRefName,headRefName,headRefOid,mergeStateStatus,reviewDecision
   git rev-parse --abbrev-ref HEAD
   ```
   `headRefName` and the current branch must both be `$BRANCH`. Merged: the
   ticket is finished (**Resume** rule). Closed unmerged: stop `blocked`.
   The baseline is the patch-id in the record's latest **Verify** ledger,
   not one taken now, so a push made in another session is seen. Then run
   **Base**.

2. **Restack on parent movement** (skip with no parent). **Base** in step 1
   already handled a parent merged into `main`. Otherwise the parent is
   *open*: its branch is on origin and its PR, if any, shows `state` `OPEN`
   in Base's query. `$BRANCH` must differ from the parent's
   branch: pushing a child onto its parent makes GitHub mark the child
   merged. Parent open and moved past the recorded parent head:
   `git fetch origin <parent branch>`, `git merge --no-ff origin/<parent branch>`
   (**Mechanical conflict** rule); record the new parent SHA after step 5's
   push carries the merge.

3. **Clear conflicts.** `mergeStateStatus` `DIRTY` or `BEHIND`:
   `git fetch origin $BASE`, `git merge --no-ff origin/$BASE`, under the
   **Mechanical conflict** rule (a `main` or base merge: every content
   conflict is a hard stop).

4. **Answer every reviewer finding.**
   ```bash
   gh api repos/$REPO/pulls/$N/reviews --paginate --jq '.[] | "\(.id) \(.user.login) \(.commit_id) \(.state)"'
   gh api repos/$REPO/pulls/$N/comments --paginate --jq '.[] | "\(.id) \(.in_reply_to_id) \(.user.login) \(.body)"'
   gh api repos/$REPO/issues/$N/comments --paginate --jq '.[] | "\(.id) \(.user.login) \(.body)"'
   ```
   The reviewer's verdict is the review (or issue comment) whose body
   starts with the profile's **Reviews** verdict marker; its findings are
   the bullet list under it, each with a file and line. Each finding is a
   claim to verify against the code at `SHA`. Real defect: smallest scoped
   fix (**Commit rule**), reply naming the commit after the push. Wrong:
   reply with a concrete disproof, file and line, leave the code as it is,
   and add a `dismissed: <reviewer> · <claim> · <disproof>` line to the
   record; a dismissal that recurs across PRs belongs where the profile's
   **Conventions** send it, never in this run's diff. Needs one of the
   profile's **Impact** human calls: needs-human entry. Count passes per
   finding and rounds per PR in the record; a third pass on one finding
   escalates it to needs-human. Reply as a comment on the PR
   (`gh pr comment $N --repo $REPO --body-file <file>`, one comment per
   round quoting each finding) and leave the verdict as it is for its
   author.

5. **Push once per pass.** Run verify steps 1 to 4 on the candidate first
   (a local fix they make is itself a hand-edited commit). Then classify
   every unpushed commit as a *clean base merge* (a merge of base or parent
   with no hand-edited hunk) or a *hand-edited change*, and take the
   patch-id (`git diff origin/$BASE...HEAD | git patch-id --stable`) to
   compare with the ledger's. Any hand-edited change makes this a new
   round; if it would be round 4, do not push, go to step 8 in `blocked`
   mode.

   Then the push rule (which drops `factory-ready`),
   `SHA=$(gh pr view $N --repo $REPO --json headRefOid --jq .headRefOid)`
   checked against the local head (**CI wait** `moved`), and the state
   line's head rewritten. A push rejected as non-fast-forward is a foreign
   push: hard stop. Heartbeat.

   Patch-id equal to the ledger's: the Verify, Review and **Goldens** lines
   stay valid, marked `patch-id unchanged @<new sha>`; step 6 still reads
   CI once at the new head because GitHub runs it anyway. Patch-id
   different, whoever pushed the difference: mark those lines
   `stale @<old sha>` and re-run verify's ledger (with its new patch-id) at
   the new head before step 7.

   After a hand-edited push, request the re-review per the profile's
   **Reviews** (a fresh subagent at the new head) and record
   `round <n> · review requested @<sha>`. Step 4 runs again when it posts.

6. **Drive CI at the exact head.** One **CI wait** observation, acted on
   by its `verdict` (the `R` **Goldens** wait is part of it). A failure this
   PR caused is fixed in its own commit and goes back to step 5 as a round.
   A failure in code the diff does not touch that does not reproduce on
   `main` is reported, not fixed: stop `blocked`, needs-human "rerun
   needed"; an identical second failure is not flake. `R` ticket: the
   profile's **Goldens** result must hold for `SHA`.

7. **Check merge-ready.** All of (a `waived:` line for this head satisfies
   the gate it names):
   - `mergeStateStatus` `CLEAN`; `BLOCKED` only by a required human review;
     or `UNSTABLE` only from a check that is not the profile's **CI**
     required check and not an `R` ticket's **Goldens** workflow. CI green
     at `SHA`.
   - Verify, CI and **Goldens** lines name `SHA` or carry
     `patch-id unchanged @SHA`.
   - A reviewer verdict exists for `SHA` or for a head with `SHA`'s
     patch-id (the profile's **Reviews** query), and every blocking finding
     it lists is closed. No verdict for this head and none requested for it
     (a push from verify, a human push, a dismissal with no push): request
     one now per **Reviews** and record it; this is not a round.
   - Every reviewer finding on `SHA` answered (a verdict newer than your
     step 4 read sends you back to step 4); zero open blocking findings.
   - `R` ticket: the profile's **Goldens** result holds at `SHA` where its
     workflow runs on the PR; otherwise the Verify ledger lists them under
     **Not verified**.

   A review that has not posted gets one bounded watch after the CI wait
   (`timeout` is coreutils; `gtimeout` on macOS; Claude Code gets the
   600000 ms Bash timeout): the profile's **Reviews** bounded watch. Still
   missing after the watch: stop `blocked`, needs-human "review not posted
   at <sha>"; a human re-requests or waives it on the ticket. Any other
   check that fails without a hard stop (CI not `green` after its
   re-observation) also ends `blocked` with the check named.

   Add a **Babysit** section: `SHA`, `mergeStateStatus`, the
   `verify_candidate` `verdict`, base and parent merges with SHAs, each
   pushed commit's class, rounds, reviews requested and received, findings
   answered.

8. **Close.** Runs in `merge-ready` mode when step 7 holds, and in `blocked`
   mode for any hard stop in any phase.
   - With a PR: run the **Cascade** once more; in `merge-ready` mode write
     the proof-of-done packet with
     [factory-packet](../factory-packet/SKILL.md); in both modes rewrite
     the PR body per the profile's **PR body** (the template, its checks
     and CI line from the record, and the **Factory run** note):
     `gh pr edit $N --repo $REPO --body-file <file>`.
     Without a PR (a stop in pickup or implement): skip both.
   - `merge-ready`: create the PR label once if absent
     (`gh label create factory-ready --repo $REPO --color 0E8A16 --description "Factory output: merge-ready, awaiting human review"`),
     then, immediately before adding it, re-read
     `gh pr view $N --json headRefOid`: a head other than `SHA` is a
     foreign push, hard stop (Close again in `blocked` mode); otherwise
     `gh pr edit $N --repo $REPO --add-label factory-ready`.
     `blocked` with a PR that carries `factory-ready`:
     `gh pr edit $N --repo $REPO --remove-label factory-ready`.
   - Ticket label (**Labels** rule): `human-ready` in `merge-ready` mode,
     `needs-human` in `blocked` mode.
   - Final record: PR link, full needs-human list (every **Operator-run**
     criterion appears there in `merge-ready` mode too, so the human knows
     what the PR does not prove), the state line
     `factory-babysit · merge-ready`, or `<stopping skill> · blocked` so
     resume returns to the phase that stopped, and `run:` cleared as the
     last write.
   - Reply in the [factory](../factory/SKILL.md) **Reply** format.

## Done when

The PR carries `factory-ready` and the **Factory run** note, the ticket
carries `human-ready` and a **Proof of done** comment, and the record ends
`factory-babysit · merge-ready` with no `run:` line; or the record ends
`<stopping skill> · blocked` with no `run:` line, the PR (if any) lacks
`factory-ready`, the ticket carries `needs-human`, and the record names what
stopped it.
