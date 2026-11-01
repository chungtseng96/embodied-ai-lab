# Agent-assisted engineering: evidence before more orchestration

Date: 2026-11-01. Status: proposed follow-up work; this document is not an implemented orchestration service.

## Target outcome

A reviewer should be able to follow one real change from a scoped Linear issue,
through agent implementation and independent review, to a reproducible result.
The useful signal is a reliable product improvement with visible engineering
judgment. More instruction files or a larger fleet are not acceptance criteria.

## Role alignment

The linked [Standard Bots Senior Software Engineer, AI Team role](https://jobs.ashbyhq.com/standardbots/9425d9a4-5ebb-46ef-835b-a46fea2e32ed)
was reviewed on 2026-11-01. It covers AI-adjacent infrastructure and customer
product surfaces, with approximately 70% backend and 30% frontend work. Data
pipelines, training/evaluation infrastructure, and perception integration are
listed areas of ownership. React/TypeScript and Python are in its stack.

That specific posting does not explicitly require an LLM coding workflow.
Agent-assisted delivery supports the case; an attractive results experience
and a working data-to-evaluation loop remain the primary portfolio evidence.

| Hiring signal | Repository evidence to build |
| --- | --- |
| Product ownership | Results UI that explains an experiment and helps an operator inspect failures |
| Data quality | Demonstration inspection, explicit exclusions, dataset and configuration identity |
| ML infrastructure | Reproducible ACT run, checkpoint identity, bounded evaluation and comparison |
| Reliable integration | SO-101 adapter, camera/joint contracts, failure handling |
| Efficient LLM use | One traceable, reviewed change with measured rework and actual validation |

## Existing foundation to retain

- Root and project AGENTS.md define ownership and hardware boundaries;
  CLAUDE.md points to the same root contract.
- The LaundryBench engineering and bring-up skills describe repeatable work.
- Factory implementer/reviewer briefs already separate responsibilities.
- Versioned plans, tests, config, manifests, and CI supply durable context.
- Claude hooks guard selected file edits and check uncommitted Python changes.
- The factory README already asks for reviewer send-backs and CI outcomes.

Do not create competing copies of these instructions.

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
3. **The evidence is hard to discover.** There is no default PR template.
   Validation, rejected approaches, independent findings, and human decisions
   can disappear into chats.
4. **The factory briefs are tied to one historical plan.** Generalizing them
   should follow the next actual task, using an issue's acceptance criteria and
   touched boundaries. A good reviewer should check behavior and missing cases,
   not merely match prescribed test assertions.

These are observations from the source tree on the review date, not claims
that a historical agent run was unreviewed or that a hook failed in practice.

## Smallest useful next steps

| Order | Change | Acceptance evidence |
| --- | --- | --- |
| Now | Add a concise PR evidence template | A new PR records issue/spec, commands, limitations and agent/human responsibilities |
| Next product change | Pilot the template on results UI work | Screenshot, regenerated report from declared mock input, checks on final SHA, independent review findings |
| Next hardware change | Pilot on adapter or recording wrapper | Dry-run/config tests plus an explicitly operator-run hardware check; no fabricated hardware pass |
| After two pilots | Capture a short engineering case study | Links to issue, commits, review findings, corrected defect and result; actual time/cost only if available |
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
