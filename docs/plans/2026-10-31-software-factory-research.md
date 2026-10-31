# Software factory for LaundryBench: research and proposed shape

**Date:** 2026-10-31
**Question:** how do we execute the V1 plan with more structure than ad hoc
subagents, without turning a one-person robotics repo into an enterprise SDLC?

## What the sources agree on

Every credible description of an "AI software factory" has the same skeleton.
The agent is not the factory; the system around it is.

| Stage | What it is | Who or what gates it |
| --- | --- | --- |
| Intake | A queue decides what is worth starting | Human writes the ticket; agent only picks from the queue |
| Spec and plan | Versioned markdown the agent implements against | Human approves before code |
| Isolation | One disposable workspace per task | Automatic (worktree or sandbox) |
| Implement | Fresh agent, one task, tests first | Deterministic checks run before anyone looks |
| Verify | Cheapest checks first: lint, tests, type check, then a reviewer that never saw the implementer's conversation | Automatic, then agent reviewer |
| Merge | Human accountable | Human, scaled to blast radius |
| Learn | Every recurring mistake becomes a line in `AGENTS.md`, a test, or a hook | Human curates |

Points that shaped the recommendation below:

- **Build the gates before the fleet.** Firecrawl's survey of production
  factories says successful teams "built the gates before the fleet" and
  recommends starting with one gate at the stage producing the most rework.
  Review capacity, not code generation, is the bottleneck; adding agents
  without changing review just moves it.
- **Verification must be something that can't lie.** Anthropic's guide: give
  Claude a pass/fail check; a `Stop` hook makes the harness enforce it, and
  `/code-review` runs in "a fresh subagent that never saw your conversation",
  so it "isn't swayed by the reasoning that produced the code". Geoffrey
  Huntley's Ralph loop calls the same thing "back pressure" from tests,
  builds, and type checkers.
- **Deterministic versus advisory.** Anthropic draws the line sharply:
  `CLAUDE.md` and skills are guidelines Claude may decide not to apply; hooks,
  deny rules, and CI are enforced every time. "If something has to happen
  every time, make it a hook." Keep the enforced set small.
- **One task per fresh context.** Ralph: "one thing per loop", fresh context
  each iteration, a plan file as shared memory, and the author's warning that
  it tends toward placeholder code and about 90% completion. Spec Kit
  formalizes the same thing as `specify → plan → tasks → implement → converge`.
- **Humans at two or three gates, not every step.** Anthropic's AI-native SDLC
  playbook: humans approve `spec.md` and `plan.md`, code owners approve PRs,
  and "keep approval prompts out of the build phase" because they put a
  person back on the critical path. Atlan's definition: humans keep intent,
  specification, and release; the agent keeps execution.
- **Passing tests is not merge-worthy.** METR found roughly half of PRs that
  pass SWE-bench would not be merged by maintainers; Faire still requires two
  human reviews on agent PRs. So a reviewer against the spec is not optional.

## What this repo already has

The plan and review documents written today are already the factory's
`spec.md` and `plan.md`. Specifically:

- **Queue:** Linear project "LaundryBench V1 contract hardening", issues
  JWA-5 to JWA-18, with blocking relations in dependency order.
- **Spec:** `2026-10-31-laundrybench-design-review.md` (findings with
  acceptance evidence) and the tldraw diagrams.
- **Plan:** `2026-10-31-laundrybench-v1-implementation.md`, one task per
  ticket, each with failing tests, exact signatures, and an Interfaces block
  a fresh agent can implement from without the conversation.
- **Deterministic check:** `make check` equals CI (pytest + ruff on stock
  Python 3.11).
- **Agent contract:** `AGENTS.md` with hardware limits and the rule that
  nothing under `src/laundrybench/` imports `lerobot`.
- **Isolation:** Superset worktrees already in use.

What is missing is the wiring between them: nothing moves a ticket, nothing
forces the check before a turn ends, and no reviewer is independent of the
implementer.

## Proposed shape: a per-ticket pipeline, nothing more

The smallest thing that is a factory rather than a chat session:

```text
Linear Todo (unblocked)                      human gate 0: ticket exists and plan section approved
   -> worktree per ticket
   -> implementer agent: reads AGENTS.md + its task section only; TDD; commits
   -> deterministic gate: make check (Stop hook) + "no lerobot import" test
   -> reviewer agent: fresh context, diff vs task Interfaces block + spec; may send back once
   -> PR per ticket, Linear -> In Review, evidence (test output, commit) in the ticket
   -> human gate 1: merge
   -> learn: any finding that recurs twice becomes an AGENTS.md gotcha, a test, or a hook
```

Rules that keep it light:

1. **Two human gates only:** plan approval (already done when PR #4 merges)
   and PR merge. No approvals inside the build.
2. **One ticket per run, fresh context per role.** Implementer and reviewer
   never share a conversation.
3. **Evidence, not claims.** A ticket moves to In Review only with the
   `make check` output and commit SHA pasted in. The review doc's status
   column is the loop state and is updated in the same commit.
4. **Hooks only for zero-exception rules.** Candidates: `make check` as a
   `Stop` hook; a `PreToolUse` hook blocking edits under `.venv-lerobot/`,
   calibration files, and `outputs/`. Nothing else until something recurs.
5. **Stop after three tickets per run**, then a human reads the PRs. Add
   parallelism "only while review is keeping up".
6. **Measure rework first.** Track, per ticket: reviewer send-backs, CI
   failures after push, human review comments. Add structure only where that
   number is highest.

## How to run it in Claude Code

Three options, cheapest first. All use the same plan, tickets, and gates.

| Option | What it is | When |
| --- | --- | --- |
| A. `superpowers:subagent-driven-development` | Built-in: fresh implementer subagent per task, fresh reviewer per task, whole-branch review at the end | Baseline. Lacks the queue, Linear updates, and enforced check |
| B. `Workflow` tool script | A deterministic JavaScript orchestrator that runs `implement → verify → review → fix` per ticket as a pipeline of subagents, with structured results | The recommended factory. It is Option A plus a real pipeline: the script, not the model, decides order and gates. Must be explicitly requested ("use a workflow") |
| C. Ralph-style outer loop | A shell loop that starts a fresh `claude -p` per ticket reading `AGENTS.md` and the plan, with a `Stop` hook enforcing `make check` | For unattended overnight runs later. Highest risk of placeholder code; Huntley expects about 90% completion |

Recommendation: **Option B for the nine Phase A tickets**, run three tickets at
a time, with the Stop hook from rule 4 added first so the deterministic gate
exists before the first agent runs. Pilot on JWA-5 alone, read the PR, then
decide whether to batch.

## Deliberately not doing

- No Jira-style status taxonomy beyond Todo / In Progress / In Review / Done.
- No separate "intent repo"; the playbook itself says that is only worth it
  across many repositories.
- No LLM judge in CI yet. One fresh reviewer per ticket is the judge.
- No auto-merge. One person owns this repo and the arm; the merge is the point
  where they look.
- No forty hooks. Two to start.

## Sources

- Anthropic, Claude Code best practices: <https://code.claude.com/docs/en/best-practices>
- Anthropic, The AI-native SDLC playbook: <https://claude.com/resources/articles/the-ai-native-sdlc-playbook>
- Firecrawl, How to build an AI software factory: <https://www.firecrawl.dev/blog/ai-software-factory>
- Geoffrey Huntley, Ralph Wiggum as a software engineer: <https://ghuntley.com/ralph/>
- GitHub, Spec Kit: <https://github.com/github/spec-kit>
- Atlan, Agentic software factory: <https://atlan.com/know/ai-agent/agentic-software-factory/>
