---
name: factory-pickup
description: Factory pickup for one Linear ticket: start or resume a run, claim the ticket, resolve its stack base, write the Factory state comment; or a write-nothing readiness-only check of a ticket.
user-invocable: true
---

# Pickup

Turn one ticket into a state record and a claimed branch on the right base,
or report where an earlier run stopped. This phase pushes only the claim
commit, plus any merges **Base** makes on a resume. Read the
[factory](../factory/SKILL.md) shared rules first.

**Readiness only.** `/factory-pickup <ticket> --readiness-only`, or invoking
text that says "readiness only": run steps 1 to 4's reading and extraction
(step 1's ticket read, step 2, step 3's base lookup, step 4's readiness
check), write nothing to Linear, git or GitHub (no watchdog flips, claim,
record or label), and print the extracted acceptance list, scope, kind,
hardware needs and base, and whether it would claim or what it would ask.
This is how the ticket author checks a ticket against the factory before
labeling it `ready`.

## Steps

1. **Read the ticket and every comment.**
   `python3 scripts/factory_linear.py issue $T` (the profile's **Linear**)
   returns the description, comments, labels, `branchName`, `blockedBy`,
   `blocks` and the existing `factoryState` comment. Later comments correct
   the description. Pick a run id (host session id, else
   `openssl rand -hex 4`), note the session start (**Turn budget**), and set
   up **Toolchain**. Then the **Watchdog**:
   `python3 scripts/factory_linear.py working $T` lists the project's other
   `working` tickets with their heartbeats; flip the ones over three hours
   old as the shared rule says. Then check the ticket's own PR:
   `gh pr list --repo $REPO --head $BRANCH --state merged --json number`;
   merged means finished (shared **Resume** rule), stop.

   If a `**Factory state**` comment exists, this is a resume:
   - Another run holds a live lease: stop without writing to the record. If
     the ticket says `ready`, set it back to `working` (the live run owns
     it). Reply in the **Reply** format, `blocked at factory-pickup`,
     needs-human "another run (<id>) holds this ticket".
   - It ends `blocked`: if a later comment answers the needs-human entry,
     record any waiver (**Resume** rule) and continue (at step 2 when no
     branch exists, else below); otherwise set the label back to
     `needs-human` and stop with the record in the **Reply** format.
   - Otherwise check the branch:
     ```bash
     git ls-remote --exit-code --heads origin $BRANCH
     git fetch origin $BRANCH
     git merge-base --is-ancestor <recorded head> origin/$BRANCH
     ```
     No remote branch: restart at step 4. Branch without the recorded head:
     resume at implement. Taking over (stale or missing lease): in one
     write, set `run: <your id> · heartbeat <now>`, add
     `Lease: takeover from <old id or none> at <time>`, and set the label
     `working`; leave the state line as it is, since it holds the resume
     point. Restore a workspace on this host, not the one the record names,
     per the profile's **Workspace** (restore on resume; a failed
     fast-forward there is a hard stop); rewrite the `Workspace:` line. Run
     **Base** on the record's base.
     Report the phase after the last `done`, and whether verify must run
     first because `origin/$BRANCH` differs from the recorded head. Skip to
     step 6.

2. **Extract the shape by role, not by heading name.** Record
   `branchName`, the `blockedBy` list, and these inputs:
   - **Acceptance list:** any checklist or bullet list of verifiable
     outcomes, under whatever heading ("Acceptance", "Done when",
     "Acceptance Criteria", "Definition of done", bare checkbox items, or
     none). Record it verbatim as the acceptance criteria.
   - **Writable scope**, two lists. **Files:** the ticket's Files section
     when present; otherwise every repository path the ticket names anywhere
     (Scope, Problem, Risks, the agent guide's route table for the boundary
     it names) as a thing to change or create, recorded as
     `Files (derived)`. A component named without a path is resolved to
     its directory first, per the profile's **Files**; one that does not
     resolve goes under Open questions, never into the path check.
     **Protected:** every path the ticket says must stay unchanged or must
     not be weakened, or lists under an Out of Scope heading (a contract
     test, an architecture doc, a config example). A ticket that names no
     path to change has unknown scope: implement's out-of-scope check then
     writes informational needs-human entries, never a stop; Protected
     still holds.
   - **Path resolution.** A named path absent at `origin/$BASE` as written
     is searched as a suffix, since tickets often write project-relative
     paths (examples in the profile's **Files**):
     ```bash
     git ls-tree -r --name-only "origin/${BASE}" | grep -E "(^|/)<path>$"
     ```
     One match resolves it (record the resolved path). Several matches, or
     none for a path the ticket does not create, is a readiness question.
     A path the ticket creates resolves its parent directory the same way
     and is recorded as `<resolved dir>/<new file> (new)`.
   - **Prose dependencies:** a sentence of the kind "depends on step n" or
     "after PR #n" names work the base must already hold; find what that
     step produces; record the mapping (`step <n> → <module or PR>`). If
     the work is not on the base, it is a readiness question ("ticket says
     it depends on <x>, which is not on <base>; confirm or add a
     blockedBy"), never a claim.
   - **Constraints:** everything under headings or sentences of the kind
     "How this step differs", "Known risks", "Out of Scope", "must keep / do
     not weaken", and every hardware-safety sentence ("do not execute
     hardware motion without authorization"), verbatim. A human reads these
     as acceptance criteria even when the ticket does not label them so;
     implement and simplify treat them that way.
   - **Measurements:** line numbers and counts the ticket cites, each noted
     "stale until measured"; implement re-measures them on the base.
   - **Kind:** `R` or `B`, per the profile's **Ticket kinds** (title
     marker, default, pure-move rule).
   - **Hardware:** per the profile's **Hardware**, split the acceptance
     list into criteria a mock or offline test can prove and criteria that
     need a physical arm, camera, GPU or operator. The physical ones are
     recorded under **Operator-run** and are never claimed by the run.

3. **Resolve the base.** For each `blockedBy` parent (its `branchName` from
   `factory_linear.py issue <parent>`):
   ```bash
   gh pr list --repo $REPO --head <parent branchName> --state all --json number,state,headRefOid,baseRefName,mergedAt
   git ls-remote --exit-code --heads origin <parent branchName>
   ```
   - No parent, or every parent merged into `main`: base `main`, record
     `Parent: none` (name merged parents only in the table's evidence), so
     **Base** never merges a stale parent head into a `main`-based branch.
   - Exactly one parent, not merged into `main`, with its branch on origin
     and no closed-unmerged PR: base is that branch, PR or not. Record the
     parent ticket, PR number (or `none yet`) and the full head SHA of
     `origin/<parent branch>`. The branch only grows (push rule), so
     babysit's restack picks up what it adds later.
   - Anything else is a hard stop: an unmerged parent with no branch on
     origin, a closed unmerged PR, a merge into a base other than `main`,
     two parents not merged into `main`, or one parent merged into `main`
     while another is not (its diff would carry `main`'s changes until the
     other parent syncs).

4. **Check readiness, then claim.** `git fetch origin $BASE`. Not ready only
   when no verifiable outcome could be found at all, an outcome contradicts a
   later comment, a literal scope path (Files, derived or Protected; never
   an unresolved component name) is absent at `origin/$BASE`
   (`git cat-file -e "origin/${BASE}:<path>"`; the quotes keep zsh from
   reading `:<path>` as a modifier) after step 2's suffix search and the
   ticket does not create it, a prose dependency is not on the base, a
   B-kind decision is still open (**Ticket kinds**), or every acceptance
   criterion is **Operator-run** (nothing a mock test can prove, so the
   factory has nothing to build). Write a **Readiness** section that shows
   the extraction by role, so a human can see a misread:
   `Acceptance (from: <heading or "checkboxes">)`, `Scope (Files | derived)`,
   `Protected`, `Constraints`, `Kind`, `Operator-run`, resolved paths,
   prose dependencies, stale measurements, then Complexity
   `<small|medium|large> · n files, m <unit>` (the unit from the profile's
   **Files**), Evidence read, Open questions. A ticket that is not ready
   skips the claim: write step 5's record without a `run:` line and with
   the state line `phase: factory-pickup · blocked · head <origin/base short sha>`,
   needs-human "answer the readiness questions on the ticket, then set
   factory:ready"; set the label `needs-human`; reply.

   Ready: create the branch per the profile's **Workspace**. If the
   worktree or local branch already exists here (a restart at this step, or
   a second local run), enter the existing worktree and `git switch $BRANCH`
   instead; never delete another run's worktree. If `git log $BRANCH`
   already holds a `factory claim` commit with another run id, take the
   Rejected path below instead of committing a second claim on top of it.
   **Claim:** one empty commit carrying your run id, then the push. Two runs
   that both branch from `origin/$BASE` push different commits, so a push
   without `--force` creates the ref for exactly one of them; without the
   commit both would push the same SHA and both succeed.
   ```bash
   git -C <path> commit --allow-empty -m "factory claim <run id>"
   git -C <path> rev-parse --abbrev-ref HEAD
   git -C <path> push -u origin HEAD:refs/heads/$BRANCH
   ```
   Created: go to step 5, whose first write sets `run:` and the label
   `working` together.

   Rejected (the ref exists): `git fetch origin $BRANCH` and re-read the
   record. A live lease: stop quietly as in step 1. No record, and the tip
   of `origin/$BRANCH` is younger than 30 minutes: the winner is between its
   push and its record; stop quietly the same way. No record, tip older than
   30 minutes, and no `factory claim` commit in `git log origin/$BRANCH`:
   a human's branch under Linear's default name, hard stop ("branch exists
   without a factory record"). Otherwise take over:
   `git switch -C $BRANCH origin/$BRANCH`, write `run:`, `Lease:` and the
   label `working` in one write, re-read `run:` (**Lease** rule), and
   continue from the record's phase (no record: write step 5's record with
   the branch head and continue at implement).

   Every later command runs inside the worktree, per the profile's
   **Workspace**.

5. **Write the state record** and swap the label (`ready` off, `working`
   on, one `set-label working` call) in the same breath, editing an
   existing comment:
   ```markdown
   **Factory state**

   Ticket: <T> (<R|B>) · Base: `<base>` · Branch: `<branchName>` · PR: none
   Parent: <id> · PR #<n or none yet> · head `<40-hex>` (or: none)
   Workspace: <worktree path> on <host>
   run: <run id> · heartbeat <ISO time>

   **Acceptance criteria** (verbatim)
   - <criterion>

   **Operator-run** (physical criteria the run never claims)
   - <criterion, or none>

   **Files** (or **Files (derived)**, or "unknown: no path named")
   - <path> (resolved from `<as written>` when the suffix search found it)

   **Protected**
   - <path, or none>

   **Constraints** (verbatim; read as acceptance)
   - <constraint, or none>

   **Readiness**
   - Acceptance (from: <heading or "checkboxes">): <n> criteria · <m> operator-run
   - Scope (<Files | derived | unknown>): <one line> · Protected: <n> paths
   - Constraints: <n> items · from <headings>
   - Kind: <R | B> · <pure move | behavior change | refactor> (<title marker or "no marker">)
   - Prose dependencies: <x (step <n> → <module or PR>) on base | not on base | none>
   - Stale until measured: <cited lines or counts, or none>
   - Complexity: <small | medium | large> · <n> files, <m> <unit from **Files**>

   | Phase | Head | Evidence |
   |---|---|---|
   | factory-pickup | `<short sha>` | base `<base>`; <parent or no parent> |

   **Needs human**
   - none

   phase: factory-pickup · done · head <short sha> · <ISO time>
   ```
   Later phases add sections above **Needs human**, a table row, and rewrite
   the last line.

6. **Report** ticket, kind, base, branch, parent, label, operator-run
   criteria, and the phase to continue from, or what blocked it: in prose
   inside a factory run, in the **Reply** format when standalone or when
   the run stops here.

## Done when

Fresh claim: the record exists with lease, criteria, Operator-run, Files,
Readiness and parent; `BRANCH` is on `origin` on the right base with this
run's claim commit; the ticket carries `working`; the state line reads
`factory-pickup · done`. Resume or takeover: `run:` and the label `working`
are this run's, the workspace is restored on the recorded base (or `main`
after **Base**), and the state line is unchanged except for its head and
names the phase to continue from.
