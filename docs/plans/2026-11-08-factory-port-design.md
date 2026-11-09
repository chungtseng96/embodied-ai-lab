# Factory port: the exchange-bidder factory in this repository

**Date:** 2026-11-08
**Status:** implemented in this PR; nothing has run end to end yet (see the
operator guide's [Before the first unattended run](../agents/factory.md#before-the-first-unattended-run)).

## Intent

Bring the exchange-bidder "software factory" (one Linear ticket to a
merge-ready, evidence-backed PR, no human in the loop) to this repository
with its core process unchanged, and make it specific to LaundryBench. The
one hard constraint from the request: there is no Ranger automation here,
so the Linear label automation needs a different trigger.

The 2026-10-31 [research note](2026-10-31-software-factory-research.md)
proposed a lighter per-ticket pipeline; the 2026-11-01
[agent-workflow plan](2026-11-01-agent-workflow.md) found that the pipeline
was described, not checked in. This port replaces both the old
`skills/factory/{README,implementer,reviewer}.md` briefs and the "small
deterministic runner" placeholder with the proven process.

## What is kept exactly

Everything in the exchange-bidder factory's shared rules and phase order:
five phases (pickup, implement, simplify, verify, babysit ending in the
packet); the state record as a Linear comment with an append-only table and
a state line; the claim commit as the lock and the `run:` lease as the log;
the single-select label group as the state machine (`ready`, `working`,
`needs-human`, `human-ready`); the cascade on `blockedBy` children; the
watchdog for silent runs; the Base rule for stacked PRs
(`scripts/factory_base.py`, copied verbatim with its tests); the push rule,
the one bounded CI wait (`verify_candidate.py` over `watch_pr_checks.py`,
copied with only the required-check constant changed); hard stops; the
three-round review cap; the proof-of-done packet; the bounce log; the
Reply format; and the rule that the repo profile is the only file a
repository edits to adopt the factory.

## What is specific to this repository

All of it is in [`docs/agents/factory-repo.md`](../agents/factory-repo.md),
section by section, so the skills stay portable. The decisions:

| Exchange-bidder | Here | Why |
| --- | --- | --- |
| `just` recipes, Rust toolchain, per-worktree test database | `make check`, `make frontend-check`, `make web-demo`, a per-worktree `.venv` (Python 3.11 via `uv`) | the project's existing checks; CI runs the same targets |
| Two review bots (Claude Code Review, Codex) with `@codex review` re-requests | one fresh-context reviewer subagent from `skills/factory/reviewer.md`, posting a `**Factory review**` verdict on the PR at the exact head | no bot is installed on the repository; the research note's requirement is a reviewer that never saw the implementer's conversation, which a subagent satisfies |
| Ranger Linear tools (`save_issue`, comments) | `scripts/factory_linear.py` (GraphQL over the personal API key) | no MCP server for the personal workspace; the claude.ai connector is the work workspace and must not be used |
| Ranger `linear_event` automation as dispatcher | `scripts/factory_dispatch.py` polled by a Superset automation (default), launchd/cron, or a cloud routine | no webhook receiver exists; a poll every 15 minutes is the same contract with a bounded delay |
| Turn budget at 40 minutes for Ranger's one-hour cap | inactive; the profile's **Host** section is where a cap goes if a capped host is added | Claude Code locally has no turn cap |
| Hard-stop paths: Helm, migrations, workflows | `.github/`, `.claude/`, robot and camera configs, `Dockerfile.train`, dependency lists, anything under `calibration`, `outputs/`, data directories | the paths that move the arm, change CI, or add permanent dependencies |
| Open B-kind decision: price, margin, risk, enablement | task definition, success judge, evaluation protocol, hardware limit, new dependency, dependent schema | the calls a human owns in a robotics repo |
| Goldens: `rfq-e2e` subset | `make demo` summary or `make web-demo` output, when an `R` ticket names one | the two reproducible outputs the project has |
| Confidential market data rule | mock versus physical rule: a run only ever writes `mock`; physical criteria are split out at pickup as **Operator-run**, built on the software side, and handed to the human | `AGENTS.md`: never describe mock results as physical; hardware commands need an operator present |

Added, not in the original: the **Hardware** profile section and the
**Operator-run** list in the state record, the ledger and the packet. A
ticket whose every criterion is operator-run stops at pickup; one with a
mix is built for its software side and lists the rest under **Not
verified** as `operator-run`.

## Goals, non-goals, anti-goals

- **Goals:** a human labels a ticket `factory:ready` and later reads a PR
  with a packet; the process is the exchange-bidder's so lessons transfer
  both ways; everything is versioned (skills, scripts, profile, tests).
- **Non-goals:** auto-merge; a webhook receiver; a second reviewer bot; a
  stuck-ticket sweep beyond what runs do; hardware acceptance by an agent.
- **Anti-goals:** a run that moves the arm; a packet row that says
  `physical`; a label set outside the `Factory` group; a push to `main`.

## Layout

```text
skills/factory/SKILL.md              router + shared rules      (/factory JWA-<n>)
skills/factory-{pickup,implement,simplify,verify,babysit,packet}/SKILL.md
skills/factory/reviewer.md           fresh-context reviewer brief
skills/factory/README.md             index
.claude/skills/factory*              symlinks so Claude Code offers them as slash commands
docs/agents/factory.md               operator guide (run, labels, dispatch, review)
docs/agents/factory-repo.md          the repo profile (the only adoption file)
docs/agents/factory-bounces.md       bounce log
docs/agents/factory-dispatch-prompt.md   the Superset automation's prompt
scripts/factory_linear.py            Linear CLI            + test_factory_linear.py
scripts/factory_dispatch.py          dispatcher poll       + test_factory_dispatch.py
scripts/factory_base.py              stacked-PR base rule  + test_factory_base.py       (ported)
scripts/verify_candidate.py          CI wait wrapper       + test_verify_candidate.py   (ported)
scripts/watch_pr_checks.py           CI watcher            + test_watch_pr_checks.py    (ported; REQUIRED_CHECK = "check")
Makefile                             factory-test, factory-dispatch
.github/workflows/ci.yml             runs make factory-test
```

## Calls made without the owner present

These are the builder's calls; each is reversible and marked here so the
owner can check them while reading.

1. **Label group name `Factory`**, not `LSCG Factory`: a different Linear
   workspace, so reusing the exchange-bidder group was impossible, and the
   repo-specific prefix would be noise in a one-team workspace. Created
   with `factory_linear.py ensure-labels`.
2. **launchd as the default dispatcher**, shipped as a plist and not
   installed. It runs where the Linear key and the `chungtseng96` GitHub
   login already are. A Superset automation was the first choice (the same
   agent session a human would start) but needs the Pro plan; it and a
   cloud routine are documented as alternatives.
3. **Reviewer as a subagent**, with its verdict posted to the PR so the
   record outlives the session. Installing a review bot later only changes
   the profile's **Reviews** section.
4. **Factory tests in CI** as their own step (`make factory-test`), not
   inside `make check`, so the local Stop hook stays fast. The pre-push
   gate runs them when `scripts/` is touched.
5. **`.claude/worktrees/` ignored** and used for factory worktrees, as in
   the exchange-bidder repository; Superset worktrees stay for humans.
6. The old `implementer.md` brief is removed: `factory-implement` is its
   successor. The old `reviewer.md` is rewritten from the plan-task brief
   to a ticket-acceptance brief, which the agent-workflow plan asked for.

## Left to the owner

- Install the launchd agent (or upgrade Superset and create the
  automation) after the first supervised run.
- Decide whether to install the Claude Code GitHub app as a second
  reviewer.
- Run the checklist in the operator guide on one small software-only
  ticket before the first unattended run.
