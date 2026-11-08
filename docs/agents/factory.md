# Factory operator guide

## Index

Current-state files, kept true in the same PR as a behavior change. This
guide covers running, resuming, dispatch and the review of what comes out.

- [factory](../../skills/factory/SKILL.md): invoke-only `/factory JWA-<n>`;
  one Linear ticket to a merge-ready PR; holds the factory shared rules;
  never merges, never touches hardware.
- [factory-pickup](../../skills/factory-pickup/SKILL.md): factory step:
  claim the ticket, resolve the stack base, split operator-run criteria
  out, write the Factory state comment.
- [factory-implement](../../skills/factory-implement/SKILL.md): factory
  step: failing test, then the smallest change inside Files.
- [factory-simplify](../../skills/factory-simplify/SKILL.md): factory step:
  behavior-preserving pass against the repo profile's **Standards**.
- [factory-verify](../../skills/factory-verify/SKILL.md): factory step: the
  checks, the PR, one CI wait, the proof ledger.
- [factory-babysit](../../skills/factory-babysit/SKILL.md): factory step:
  drive a PR to merge-ready at the exact head, label `factory-ready`.
- [factory-packet](../../skills/factory-packet/SKILL.md): factory step, also
  standalone on any PR: proof-of-done packet with linked evidence, impact,
  self-review and the weakest point.
- [reviewer.md](../../skills/factory/reviewer.md): the brief the
  fresh-context reviewer subagent runs from.
- [factory-bounces.md](factory-bounces.md): why a human sent a factory PR
  back, and which phase should have caught it.
- [factory-repo.md](factory-repo.md): the repo profile: every repo-specific
  value the skills cite by section name; the only file a repository edits to
  adopt the factory.
- `scripts/factory_linear.py`: Linear reads and writes (labels, state
  comment, watchdog, cascade). `scripts/factory_dispatch.py`: the poll that
  starts runs. `scripts/factory_base.py`: the shared **Base** rule for
  stacked PRs. `scripts/verify_candidate.py` and
  `scripts/watch_pr_checks.py`: the **CI wait**. Tests: `make factory-test`.

## Overview

The factory takes one Linear ticket to a merge-ready, evidence-backed PR
without a human in the loop. The [factory](../../skills/factory/SKILL.md)
skill runs five step skills in order, in one session: pickup, implement,
simplify, verify and babysit; babysit ends with the
[factory-packet](../../skills/factory-packet/SKILL.md) proof-of-done. Each
step also runs alone, for example `/factory-verify` or `/factory-babysit`
on any PR. A run ends with a PR labeled `factory-ready`, or `blocked` with a
needs-human entry that says why.

This is the exchange-bidder factory's process, ported whole. Three things
are different here, all recorded in the [repo profile](factory-repo.md):
the checks are `make` targets on a Python 3.11 project; the reviewer is a
fresh-context subagent (no review bot is installed on this repository); and
there is no agent platform, so Linear is reached through a script and runs
start from a scheduled poll instead of a webhook. One thing is added: the
factory never runs hardware. A ticket's physical criteria are split out at
pickup as **Operator-run**, built on the software side, and handed to the
human in the packet and the needs-human list. Every evidence line a run
writes says `mock`.

The rules a run follows (state record, lease, labels, base, push rule, CI
wait, hard stops, what it never does) live once, in the factory skill's
**Shared rules**.

## The ticket shape it expects

The factory reads a ticket by role, not by heading: the acceptance list (any
checklist of verifiable outcomes, which the current `JWA` tickets write
under "Acceptance:"), the scope (a Files section, else every path or
boundary the ticket names to change), the Protected paths it says must
stay unchanged, the Constraints (risks, "do not" sentences, Out of Scope,
hardware-safety sentences, kept as acceptance), the kind (an `R` or `B`
title marker; none means `B`) and the operator-run criteria (anything that
needs the arm, a camera, a GPU or a person present). A `blockedBy`
relation, not the prose, picks the base.

`/factory-pickup JWA-<n> --readiness-only` prints what pickup would extract
and ask, writing nothing, and is how to check a ticket before labeling it
`ready`. A ticket with no verifiable outcome, an outcome a later comment
contradicts, a scope path that does not exist, an open design decision
(task definition, success judge, hardware limit, dependency), or nothing
but operator-run criteria stops `blocked` with its open questions in the
record and the label `needs-human`. Answer them in a ticket comment, then
set `ready`.

A ticket blocked by a parent branches from and targets the parent's branch
as soon as that branch is on origin, so children build on upstream code
before it is reviewed or merged, and PRs form a stack whose bottom targets
`main`. Every phase checks the parent before touching the base; once a
parent is merged into `main`, `scripts/factory_base.py` moves the child
onto `main` and retargets its PR. A ticket with two parents runs only once
every parent is merged into `main`, and a human releases it then.

## Run it

Locally, from a worktree in Claude Code: `/factory JWA-<n>`. Pickup creates
(or, when the dispatcher pre-created it, enters) the worktree at
`.claude/worktrees/<slug>`, gives it its own `.venv`, and every later phase
runs inside it. Claude Code's Bash tool kills a command at two minutes by
default; every `make` gate, the CI wait and the bounded watches get the
ten-minute timeout. Headless, from the repository root:

```bash
.venv/bin/python scripts/factory_dispatch.py run --dry-run   # what would start
.venv/bin/python scripts/factory_dispatch.py run             # start the oldest ready ticket
```

Before the first run on a fresh clone: `make install`, then
`.venv/bin/python scripts/factory_linear.py ensure-labels` (idempotent).

## Labels: the ticket's factory state

The `Factory` label group on team `JWA` is single-select. It answers "who
acts next":

| Label | Set by | Means |
|---|---|---|
| `factory:ready` | a human on root tickets; a paused run on its own ticket; the cascade on children | start, or resume, a run |
| `factory:working` | every run as it writes its `run:` line (claim, resume, takeover) | a run holds the ticket; phase and head are in the Factory state comment |
| `factory:needs-human` | any `blocked` ending: babysit's Close, pickup's readiness stop, the watchdog | answer the needs-human entry in a comment, then set `ready` |
| `factory:human-ready` | babysit's Close, `merge-ready` mode | the PR carries `factory-ready`; a human reads the packet, runs operator-run criteria, merges |

The factory sets nothing else in Linear: no status, no other label. Moving
the ticket between statuses stays a human's call.

## Dispatch

Adding `factory:ready` is the trigger. A human adds it only to the root
tickets of a project: when a run opens its PR, and again when it closes, it
sets `ready` on the tickets blocked by its ticket alone, so a chain in the
`blockedBy` graph schedules itself. A child with two or more parents is
released by a human once every parent is merged into `main`.

The exchange-bidder factory is started by a Ranger automation that
receives Linear's label webhook. This repository has no Ranger tenant, so
the trigger is a **poll**: `scripts/factory_dispatch.py` lists the team's
`factory:ready` tickets, oldest first, skips any whose branch is already on
origin (a claim in flight), and starts one run. The run swaps the label to
`working` as it claims, so the next poll does not start it twice; a lock
file keeps two polls from starting two sessions. Three schedulers can run
the poll; all read the Linear key from `~/.config/linear/embodied-ai-lab.key`
and push as `chungtseng96` through the repo-local credential helper.

1. **launchd on the laptop (the default).**
   [`scripts/com.embodied-ai-lab.factory-dispatch.plist`](../../scripts/com.embodied-ai-lab.factory-dispatch.plist)
   runs `.venv/bin/python scripts/factory_dispatch.py run` from the shared
   checkout every 15 minutes. The dispatcher launches
   `claude -p "/factory <id>" --permission-mode bypassPermissions` in the
   ticket's worktree and exits when the run does; its log is
   `.claude/worktrees/factory-dispatch.log`. The install and removal
   commands are in the plist's header comment. It is not installed by this
   PR: installing it starts unattended runs, which is the owner's call
   after the checklist below. The laptop must be awake and logged in.
2. **Superset automation**, when the Superset plan allows automations
   (they need the Pro plan; the free plan refused the create on
   2026-11-08). A scheduled agent session in the `embodied-ai-lab` Superset
   project whose prompt is
   [factory-dispatch-prompt.md](factory-dispatch-prompt.md): run the poll;
   if it names a ticket, follow `skills/factory/SKILL.md` for it; otherwise
   stop. The automation is the session, so there is no nested `claude -p`:
   ```bash
   superset automations create --name "LaundryBench factory" \
     --prompt-file docs/agents/factory-dispatch-prompt.md \
     --rrule "FREQ=HOURLY;BYMINUTE=15" --project 0e032561-0663-4525-a8b2-236149f9b3f3 \
     --tag factory
   ```
3. **A cloud routine** (Claude Code's `/schedule`) or a GitHub Actions
   cron with `anthropics/claude-code-action`, when the laptop should not be
   the host: both need the Linear key and a GitHub token for
   `chungtseng96` stored as secrets, and `--add-dir` or a checkout of the
   repository. Not set up; documented so the choice is visible.

Whatever starts the run, the state record and labels are the same, so a
run started by hand and one started by the poll resume each other.

## Reviews

No review bot is installed on `chungtseng96/embodied-ai-lab`. The reviewer
is a fresh-context subagent the run dispatches from the
[reviewer brief](../../skills/factory/reviewer.md); it reads the diff
against the ticket's acceptance criteria, runs `make check` itself, and
posts one PR review at the exact head whose first line is
`**Factory review** · head <sha> · verdict: approve | send back`. Verify
requests the first review when it opens the PR; babysit requests one after
every fix push. Three rounds is the cap: the first head's review, then at
most two fix pushes with their re-reviews. Merge-ready needs zero open
`[blocking]` findings; `[nit]` lines are answered, not required. A finding
closes with the fix commit or a recorded disproof, or when the next
review at a later head drops it. If a blocking finding is still open after
round 3, babysit stops `blocked` with the list rather than calling the PR
merge-ready.

Installing the Claude Code GitHub app for PR review would add a second,
independent reviewer; the profile's **Reviews** section is where it would
be recorded.

## Limits and resuming

Claude Code caps a command at ten minutes and has no turn cap. A timed-out
CI wait pauses the run: the phase stays `started`, the lease is cleared,
`ready` is set, and the reply says `paused at <phase>`; the next poll
starts a fresh session that resumes from the record. The third CI timeout
on the same phase and head stops `blocked` instead of pausing again.

The state record is the Linear comment whose first line is
`**Factory state**`; its last line, such as
`phase: factory-verify · done · head 1a2b3c4 · 2026-11-08T18:20Z`, says where
the run stands. To resume, set `ready` on the ticket. `blocked` resumes only
after a human answers the needs-human entry in a later ticket comment.

Ownership is the claim commit on the remote branch: of two fresh runs
started together, exactly one proceeds; two resumes started together are
last-writer-wins on the record, and the loser sees it on its re-read. The
record's `run:` line is the log of who holds it, and every ending clears
it; to free a ticket by hand, delete that line. A ticket left `working`
with a heartbeat older than three hours is stuck: every run's pickup lists
its project's `working` tickets and flips a stuck one to `needs-human`
("run went silent at <phase>"). Nothing else sweeps for stuck tickets.

Code that changes after review goes back through review: `factory-ready`
comes off before every push and returns only when verify, CI, goldens and
the reviewer's verdict name the new head (or a head with the same
patch-id).

## What to look at after a run

Start from the tickets labeled `factory:human-ready` (their PRs carry
`factory-ready`) and read each stack bottom-up; `factory:needs-human`
tickets are the ones waiting on an answer. For each, read the ticket's
**Proof of done** comment first: one row per criterion with linked
evidence, impact, self-review, and the run's own weakest point. Rows marked
`operator-run` are yours: run them under the
[home playbook](../../projects/laundrybench/docs/playbooks/so101-home-feedback-loop.md)
and record the result under the physical evidence contract before the PR's
claim is complete. A missing or thin packet is an automatic bounce; the
diff is read line by line only for hardware configs, workflows, hooks,
dependencies and anything that touches the profile's **Impact** risk
surface. The PR body's **Factory run** note is the short form. A line
marked `stale @<sha>` came from an earlier head; a criterion under **Not
verified** was not exercised.

Every bounce gets one line in [factory-bounces.md](factory-bounces.md): the
reason and the phase that should have caught it. A reason that recurs
graduates into an `AGENTS.md` line, a test, a hook, or a check in the
reviewer brief.

Merging is a human's call, by hand. The PR template's "Review and
ownership" section is where the human decision is written.

## Before the first unattended run

Nothing has run end to end here yet. Run these on one small software-only
ticket first, with `/factory JWA-<n>` in a session you can watch.

0. **Labels exist.** `factory_linear.py ensure-labels` prints
   `"created": []` on its second run, and the `Factory` group shows as
   single-select in Linear's team label settings.
1. **Readiness read.** `/factory-pickup JWA-<n> --readiness-only` extracts
   the acceptance list, Files and operator-run criteria you expect from a
   current-style ticket.
2. **Competing pickups.** Two runs on one ticket within seconds. Pass:
   exactly one proceeds; the other replies `blocked at factory-pickup`,
   wrote nothing to the record, and left the ticket at `working`.
3. **Interrupted resume.** Kill a run after implement reports `done`,
   delete the record's `run:` line, set `ready`, run the dispatcher. Pass:
   it resumes from the record, finds the pushed branch at the recorded
   head, swaps the label to `working`, and continues at simplify.
4. **Reviewer posts.** The subagent's review appears on the PR at the head
   SHA with the verdict marker, and babysit reads it back with the
   profile's **Reviews** query.
5. **Babysit fix loses readiness.** On a merge-ready PR, have babysit fix a
   reviewer finding. Pass: `factory-ready` is gone before the push and comes
   back only when verify, CI and the reviewer's verdict name the new head.
6. **The poll starts a run.** With one ticket `ready`,
   `make factory-dispatch` from the shared checkout starts a headless
   session that claims it; then install the launchd agent.

## Adopting the factory in another repo

1. Copy `skills/factory*` and the `.claude/skills/factory*` symlinks to
   them, plus `skills/factory/reviewer.md`.
2. Copy `scripts/factory_linear.py`, `scripts/factory_dispatch.py`,
   `scripts/factory_base.py`, `scripts/verify_candidate.py` and
   `scripts/watch_pr_checks.py`, with their tests.
3. Write `docs/agents/factory-repo.md` for that repository, keeping the
   section names the skills cite.
4. Edit `REQUIRED_CHECK` in `watch_pr_checks.py` to that repository's
   required check, and `DEFAULT_TEAM` and the key path in
   `factory_linear.py`.
5. Run `factory_linear.py ensure-labels` for that team.
6. Point a scheduler at `factory_dispatch.py` (see **Dispatch**).

## Not covered yet

No sweep flips stuck `working` tickets; runs do it when they read one. The
Superset automation's turn cap, if any, is unmeasured; if a run is killed
mid-phase, the record's `started` phase re-runs on the next poll. The
reviewer is one subagent from one brief; a second independent reviewer
would be a bot the repository does not yet have.
