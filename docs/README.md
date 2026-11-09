# Engineering documentation

Shared contributor workflows and templates for Embodied AI Lab.
Project design, hardware procedures, and experiment plans live with the project.

| Document | Purpose |
| --- | --- |
| [Contributor instructions](../AGENTS.md) | Repository boundaries and required checks |
| [Agent guide](agent-guide.md) | Task routing, validation, and handoff evidence |
| [Factory](../skills/factory/README.md) | Ticket-to-PR pipeline: operator guide, repo profile, reviewer brief |
| [Factory operator guide](agents/factory.md) | Run, resume, dispatch and review factory output |
| [Plans](plans/) | Shared engineering process proposals |
| [Templates](templates/) | Experiment, architecture decision, plan, and handoff formats |
| [LaundryBench documentation](../projects/laundrybench/docs/README.md) | Architecture, operator playbooks, and project plans |

## Conventions

- Project documentation belongs under `projects/<project>/docs/`.
- Experiments belong under `projects/<project>/experiments/`; generated artifacts stay outside Git.
- Plans use `YYYY-MM-DD-slug.md` names and state their status explicitly.
- Architecture decisions use numbered records; add a new decision to supersede one.
- Distinguish implemented behavior, proposed design, and physical validation.
