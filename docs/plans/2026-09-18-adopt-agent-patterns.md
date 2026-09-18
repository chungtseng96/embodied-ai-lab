# Adopt AI-agent-friendly repo patterns

**Date:** 2026-09-18
**Status:** Tiers 1 and 2 implemented 2026-09-18 on branch `adopt-agent-patterns`; Tier 3 is on demand
**Sources audited:** `Underdog-Inc/ranger`, `Underdog-Inc/ai-platform`, `Underdog-Inc/api` (local clones under `~/Desktop/repos/`)
**Scope:** this repo is a solo Python learning + robotics lab. Patterns built for large polyglot monorepos (CI aggregators, CODEOWNERS, Copilot sync hooks, risk gates) are deliberately left out. Only patterns that pay off at this size are listed.

## Where this repo stood before Tier 1

- No `AGENTS.md` / `CLAUDE.md`, no `.claude/`, no skills, no hooks.
- `Makefile` has 4 targets (`install`, `test`, `demo`, `lint`). CI re-implements them by hand instead of calling them.
- `docs/` has no index. ADRs 001-003 have no Status / Date / Consequences.
- Experiment template captures results but not *evidence* (command run, output, commit SHA, mock vs physical).
- Commit prefixes (`docs:`, `labs:`, `experiments:`, `test:`, `chore:`, `config:`, `ci:`) are consistent but unwritten.

## What made the three repos agent-friendly (the common core)

All three converge on the same skeleton, independently:

1. **One context file, two names.** `AGENTS.md` is the source; `CLAUDE.md` is a symlink (ranger, ai-platform) or the reverse (api). Zero drift between agent harnesses.
2. **Root file is a router, not a manual.** Short (api root is 31 lines, ai-platform says "orient in 60 seconds"). Depth lives in nested `AGENTS.md` files next to the code they describe.
3. **Copy-pasteable command block** and a promise that local commands equal CI byte-for-byte (api `ud verify`, ai-platform `make check`, ranger npm scripts mirrored in `ci.yml`).
4. **"Don'ts" / "Key Gotchas"**: a curated list of plausible-but-wrong moves, with the escape hatch named.
5. **Symptom → cause table** ("When something goes wrong") keyed on the exact error string.
6. **Evidence, not confidence.** ai-platform's `GATE-EVIDENCE.md` (Tested / Output / Why it passed / Post-deploy check) and negative-test proof; api's pre-PR hook captures the literal `N runs, N assertions` line; ranger's PR template asks "How is it tested?".
7. **Docs carry a status header** (Date / Status / Owner) and a task-shaped index ("pick the guide that matches what you're doing"). ai-platform explicitly splits *committed design* from *exploration record* so an agent never implements an abandoned plan.
8. **Domain context file** (`CONTEXT.md`): glossary, invariants ("violate = incident"), and a **"Known gaps / parked — do not guess"** section.
9. **Skills with trigger-phrase descriptions** in `.agents/skills/` (vendor-neutral) with `.claude/skills` symlinked to it.
10. **Loop state in files**: item / status / evidence / next, an explicit stop condition, and a separate "needs me" lane for human-only decisions (ai-platform `LOOP-STATE.md`; matches the loop-engineering rule in the global `CLAUDE.md`).
11. **Sanctioned scratch dir**, gitignored (`.claude/scratch/`, `.scratch/`).
12. **Hooks that close the loop at edit time** (ruff / shellcheck / markdownlint on every Write|Edit), returning the repro command and the fix.
13. **A named tiebreaker**: "if docs and code disagree, `mcps/workday/` wins" (ai-platform).

## Adoption list for this repo

### Tier 1 — do first (an afternoon, highest leverage)

| # | Item | Borrowed from | Notes for this repo |
|---|------|---------------|---------------------|
| 1 | Root `AGENTS.md` (< 80 lines) + `CLAUDE.md -> AGENTS.md` symlink | all three | Sections: what this repo is, layout (reuse README map), commands, test layout, commit prefixes, Key Gotchas, Further Reading. Router only. |
| 2 | Nested `projects/laundrybench/AGENTS.md` (deep guide) | api hierarchy, ai-platform per-subsystem | Robot/Policy boundary, where tests live, how to add a policy adapter, Don'ts (no model-specific code past `policies/base.py`, no LeRobot imports in core, never treat mock success rate as a result). |
| 3 | `make check` = lint + test, and CI calls `make check` | ai-platform `check.sh`/Makefile, api `ud verify`, ranger CI mirror | One command, prints `GATE PASS` / `GATE FAIL`. Removes the copy of the steps in `ci.yml`. |
| 4 | Key Gotchas + Don'ts section | ranger, ai-platform | Seed: mock ≠ physical; labs blocked on hardware; ADRs are decisions not tutorials; configs in `configs/*.yaml` are the source of truth. |
| 5 | `docs/README.md` task-shaped index + status header on every doc | ai-platform P32/P34, ranger gap #2 | "Learning a concept → fundamentals/; debugging → cheatsheets/; why we chose X → architecture/decisions/". Header: Date / Status / Owner. |
| 6 | `projects/laundrybench/CONTEXT.md`: glossary + invariants + parked | ai-platform CONTEXT.md | Glossary: episode, observation, action, intervention, success definition, baseline vs candidate. Invariants: model-agnostic boundary; mock results never reported as robot results. Parked: hardware, LeRobot adapter, real policy. |
| 7 | Experiment template gets an **Evidence** block | ai-platform GATE-EVIDENCE, api predicted-tests evidence | Fields: `Hardware: mock | physical`, command run, output excerpt, code/config commit SHA, negative check (what failed first). Make `Hardware` mandatory. |
| 8 | Gitignored scratch dir `.claude/scratch/` | api, ranger | Document it in `AGENTS.md`. |
| 9 | Write down commit prefixes and PR template (What / Why / How tested) | ranger #10, #44 | Prefixes already used: `docs: labs: experiments: test: chore: config: ci:`. Add `feat:` `fix:`. |

### Tier 2 — implemented 2026-09-18 (see notes for deviations)

| # | Item | Borrowed from | Notes |
|---|------|---------------|-------|
| 10 | `.claude/settings.json`: allow `make *`, `pytest`, `ruff`; PostToolUse hook running `ruff check --fix` on `.py` edits | ranger hooks, api permissions | Hook is one small self-gating script (read stdin JSON, no-op on non-.py). |
| 11 | ADR template (Status / Context / Decision / Consequences / Amends) + index `docs/architecture/decisions/README.md`; backfill 001-003 headers | ranger ADRs, api immutable ADRs | Keep "immutable, amend with a new file" rule. |
| 12 | `docs/plans/` convention: date-prefixed, `-design` / `-plan` pairs, "For agentic workers" header, checkbox steps | ranger superpowers plans, ai-platform docs/plans | This file is the first instance. |
| 13 | `docs/templates/loop-state.md`: Item / Status / Evidence / Next table + stop condition + `Needs James` row; gitignore `LOOP-STATE.md` | ai-platform LOOP-STATE.md, orchestration design §7 | Matches the global loop-engineering rule. |
| 14 | Repo-local skills, discoverable by Claude Code | ai-platform `.agents/skills` + `.claude/skills` symlink | `skills/so101-bringup` and `skills/laundrybench-engineering` arrived via the SO-101 readiness PR and are kept; `.claude/skills -> ../skills` makes Claude Code load them. A `running-an-experiment` skill was tested and **not** added: an agent with no docs only omitted header fields and evidence, and the experiment template plus `test_experiment_docs.py` closed every gap on re-run. Skills here are for multi-step procedures (hardware bring-up), not for slots a template can hold. |
| 15 | "When something goes wrong" table in `laundrybench/AGENTS.md` | ai-platform P12 | Done in Tier 1. Populate further as hardware bring-up produces real errors. |
| 16 | Tiebreaker rule: `policies/base.py` and `robot/base.py` win over any doc; `mock.py` is the reference implementation | ai-platform P31 | Done in Tier 1. |
| 17 | `tests/test_experiment_docs.py`: every `experiments/exp-*/README.md` has the required headings and a `Hardware:` line | api docs-check, ai-platform validate-datadog | Folded into `make check` rather than a separate target. Written red-first: failed on EXP-001/002 until their headers were added. |
| 18 | Maintenance clause in nested AGENTS.md ("if you change the Robot/Policy contract, update this file and CONTEXT.md") | api pack CLAUDE.md "Maintenance" | Done in Tier 1. |

### Tier 3 — on demand, triggered by a real miss

Not scheduled. Tier 2 showed that guessing at failures produces work the template already covers.
Add an item here only after an agent actually fails at it in this repo. Item 19 is seeded now
because the table costs one edit and the pins already exist.

| # | Item | Borrowed from | Notes |
|---|------|---------------|-------|
| 19 | Pinned-versions table with a "key constraint" column | api frontend CLAUDE.md, ai-platform phoenix-docs-explorer | Seeded in `laundrybench/AGENTS.md` with today's pins; add a LeRobot / torch row the day they become a dependency. |
| 20 | Version-pinned docs-research subagent for LeRobot | ai-platform `.claude/agents/phoenix-docs-explorer.md` | Only after a LeRobot API-version mismatch actually costs time. |
| 21 | Read-only review subagent for the safety-critical path | ai-platform `collector-allowlist-reviewer` | Only once a real motion-limits module exists. Until then `require_manual_supervision: true` and the Don'ts cover it. |
| 22 | Skill evals | api sportradar evals | No skills exist (item 14). Nothing to eval. |

### Deliberately not adopting

CI success aggregators, CODEOWNERS, Copilot instruction sync, hound-dog risk gate, session-log upload, scheduled agentic workflows, devcontainer, packwerk-style boundaries. All solve multi-team or multi-language problems this repo does not have.

## Defects spotted in the source repos (FYI, not this repo's work)

- `ranger/AGENTS.md` has committed merge-conflict markers (`<<<<<<< Updated upstream` ... `>>>>>>> Stashed changes`) that deleted the "there are no lower environments / lscg is production" section.
- `ranger/CONTRIBUTING.md` links two docs that don't exist (`docs/adr/0001-...`, `docs/provider-contribution-checklist.md`).
- `ranger/.claude/hooks/lint-agents.sh` only matches `*CLAUDE.md`, so editing `AGENTS.md` by name bypasses it.
- `ai-platform/docs/mcp-platform/build-mcp.md` says `pnpm mcp:new` appends a CODEOWNERS line, but no CODEOWNERS file exists.
