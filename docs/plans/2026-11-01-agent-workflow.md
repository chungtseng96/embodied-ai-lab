# Agent-assisted engineering: evidence before more orchestration

Date: 2026-11-01. Status: proposed follow-up work; this document is not an implemented orchestration service.

## Target outcome

A reviewer should be able to follow one real change from a scoped Linear issue,
through agent implementation and independent review, to a reproducible result.
The useful signal is a reliable product improvement with visible engineering
judgment. More instruction files or a larger fleet are not acceptance criteria.

## Engineering objectives

| Objective | Evidence |
| --- | --- |
| Product operation | Results UI that explains experiments and supports failure inspection |
| Data quality | Demonstration inspection, explicit exclusions, dataset and configuration identity |
| Reproducibility | Traceable ACT runs, checkpoint identity, bounded evaluation and comparison |
| Reliable integration | SO-101 adapter, camera/joint contracts, failure handling |
| Agent-assisted delivery | Scoped changes with review findings and actual validation |

## Existing foundation to retain

- Root and project AGENTS.md define ownership and hardware boundaries;
  CLAUDE.md points to the same root contract.
- The LaundryBench engineering and bring-up skills describe repeatable work.
- Factory implementer/reviewer briefs already separate responsibilities.
- Versioned plans, tests, config, manifests, and CI supply durable context.
- Claude hooks guard selected file edits and check uncommitted Python changes.
- The factory README already asks for reviewer send-backs and CI outcomes.

Do not create competing copies of these instructions.

## Reconcile the older agent-pattern proposal

The reconciliation of [PR #3](https://github.com/chungtseng96/embodied-ai-lab/pull/3)
retains documentation routing, experiment metadata checks and useful templates.
Its stale task_success, unloaded-config and missing-report descriptions are
excluded; the current main agent guides and hooks remain authoritative.
The evidence and independent-review PR template added alongside this plan is
preserved. The shared `make check` command includes script smoke checks and is
used by CI; it does not print a GATE PASS marker.

## Verified gaps

1. **The orchestration is described, not checked in.** The factory README
   describes a script-controlled pipeline, but the current source tree has
   briefs and hooks rather than a runnable coordinator. Describe the current
   process as agent-assisted until a runner exists and is exercised.
2. **Local hook coverage is limited.** The Stop hook inspects working-tree,
   staged, and untracked Python paths. After a commit those diffs can be empty;
   it is not proof that the final commit passed. The edit-path guard handles
   Edit/Write calls, not every shell command. CI is the shared verification
   gate; hooks are local assistance, not a security boundary.
3. **Evidence needs consistent adoption.** A default PR template now records
   validation, independent findings and human decisions. The JWA-16/17/23
   implementation in [PR #35](https://github.com/chungtseng96/embodied-ai-lab/pull/35)
   is the shipped pilot; the [engineering case study](../agent-guide.md#case-study-pr-35)
   links its implementation and check definitions. The PR's [check results](https://github.com/chungtseng96/embodied-ai-lab/pull/35/checks)
   are the source for CI status; this plan does not infer a result from the local checkout.
4. **The factory briefs are tied to one historical plan.** Generalizing them
   should follow the next actual task, using an issue's acceptance criteria and
   touched boundaries. A good reviewer should check behavior and missing cases,
   not merely match prescribed test assertions.

These are observations from the source tree on the review date, not claims
that a historical agent run was unreviewed or that a hook failed in practice.

## Smallest useful next steps

| Order | Change | Acceptance evidence |
| --- | --- | --- |
| Implemented | Concise PR evidence template | A new PR records issue/spec, commands, limitations and agent/human responsibilities |
| Implemented | Pilot the evidence template on the recording, ACT training, and rollout change | [PR #35](https://github.com/chungtseng96/embodied-ai-lab/pull/35), check links and concrete edge cases in the [case study](../agent-guide.md#case-study-pr-35) |
| Next hardware change | Pilot on adapter or recording wrapper | Dry-run/config tests plus an explicitly operator-run hardware check; no fabricated hardware pass |
| After hardware pilot | Review whether another brief case study would add evidence | Current software pilot is summarized in the [PR #35 case study](../agent-guide.md#case-study-pr-35); add only verified hardware evidence and measured data |
| Only if handoffs are recurring work | Add a small deterministic runner | Resumable state, bounded retry, final-SHA checks, isolated worktree and explicit human merge gate |

Use the existing factory rework tally; add elapsed time, model/version, or
token/cost data only when measured. Missing telemetry is stated as unknown.
Do not claim speedup without a comparison. Keep transcripts and credentials
out of the public repo; publish concise decisions and evidence.

For independent review, start a fresh context with the issue/spec, base/head
SHAs, applicable instructions and diff. Re-run relevant checks, challenge
failure paths, and report concrete findings. An agent review is advisory;
deterministic checks and human judgment still apply.

## Optional later demonstration of LLM product engineering

A read-only experiment assistant could answer questions from a run's manifest,
summary and quality files, citing exact artifacts and episode IDs. It should
never issue robot motion commands. Start only after the core results UI is
useful, with a small fixed evaluation set covering correct answers, missing
data and invented citations. This is a possible extension, not current scope.

## Definition of done for the pilot

A reader can reproduce the result from the documented inputs and revision,
see whether it is mock or physical, inspect one meaningful review decision,
and understand what the human owned. Keep the evidence attached to the shipped
feature rather than building a separate agent demo.
