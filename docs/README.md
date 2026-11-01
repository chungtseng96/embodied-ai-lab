# docs/ — pick the guide that matches what you're doing

| I want to... | Read |
|--------------|------|
| Learn or review a robotics concept | `fundamentals/` (one concept per file, uses `templates/learning-note.md`) |
| Look something up fast while debugging or interviewing | `cheatsheets/robotics.md`, `cheatsheets/lerobot.md` |
| Understand how V1 fits together | `architecture/v1-architecture.md` |
| Know why a design choice was made, or change it | `architecture/decisions/` (ADRs, immutable; add a new one to amend) |
| See what was learned when | `journal/` (dated entries) |
| Start a new experiment or learning note | `templates/experiment.md`, `templates/learning-note.md` |
| Prepare for hardware bring-up or cloud training | `plans/so101-readiness.md`, `architecture/robot-learning-development-environment.md`, then repository-root `skills/so101-bringup/SKILL.md` |
| Find a design or work plan | `plans/` (prefer date-prefixed names for new plans) |

Not under `docs/`: paper notes and study plans live in `notes/`; hands-on exercises in `labs/`;
LaundryBench code guides in `projects/laundrybench/AGENTS.md`.

## Conventions

- Prefer these headers for new docs: `**Date:** / **Status:** / **Owner:**`. Suggested status values:
  `Living document`, `Proposed`, `Accepted`, `Superseded by NNN`, `Planned`, `Draft`,
  `Exploration (not committed)`.
- Plans are `plans/YYYY-MM-DD-slug.md`. A design and its implementation plan are paired as
  `-design.md` / `-plan.md`.
- ADRs are `architecture/decisions/NNN-slug.md` with Status / Decision / Why / Tradeoff. Use a new ADR to amend an accepted decision.
