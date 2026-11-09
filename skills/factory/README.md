# Factory: how one ticket becomes one PR

The factory takes one Linear ticket to a merge-ready, evidence-backed PR
without a human in the loop, and stops there: a human runs hardware and
merges. It is the exchange-bidder factory's process, ported; what differs
for this repository is in one file, the repo profile.

- Operator guide (run, resume, labels, dispatch, the Monday review):
  [`docs/agents/factory.md`](../../docs/agents/factory.md)
- Repo profile (every repo-specific value the skills cite):
  [`docs/agents/factory-repo.md`](../../docs/agents/factory-repo.md)
- Router and shared rules: [`SKILL.md`](SKILL.md) (`/factory JWA-<n>`)
- Step skills: [pickup](../factory-pickup/SKILL.md),
  [implement](../factory-implement/SKILL.md),
  [simplify](../factory-simplify/SKILL.md),
  [verify](../factory-verify/SKILL.md),
  [babysit](../factory-babysit/SKILL.md),
  [packet](../factory-packet/SKILL.md)
- Reviewer brief for the fresh-context subagent: [`reviewer.md`](reviewer.md)
- Bounce log: [`docs/agents/factory-bounces.md`](../../docs/agents/factory-bounces.md)
- Scripts: `scripts/factory_linear.py` (Linear), `scripts/factory_dispatch.py`
  (the poll that starts runs), `scripts/factory_base.py` (stacked PRs),
  `scripts/verify_candidate.py` and `scripts/watch_pr_checks.py` (CI wait).

```text
Linear ticket labeled factory:ready
  -> dispatcher poll (launchd; Superset automation on a Pro plan) or a human: /factory JWA-<n>
  -> pickup     claim commit, base, Factory state comment, label factory:working
  -> implement  failing test first, smallest change inside Files
  -> simplify   behavior-preserving pass against AGENTS.md and the architecture docs
  -> verify     make check, PR from the template, one CI wait, proof ledger
  -> babysit    fresh-context reviewer (up to 3 rounds), CI green at the exact head
  -> packet     Proof of done comment; PR label factory-ready; ticket factory:human-ready
  -> human      reads the packet, runs any operator-run criteria, merges
```

Background and sources for the shape:
[`docs/plans/2026-10-31-software-factory-research.md`](../../docs/plans/2026-10-31-software-factory-research.md);
the port's design and decisions:
[`docs/plans/2026-11-08-factory-port-design.md`](../../docs/plans/2026-11-08-factory-port-design.md).
