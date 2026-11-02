# Embodied AI Lab

Robotics systems for manipulation, policy evaluation, and reproducible experimentation.

The lab builds complete experimental workflows: collect demonstrations, train a policy,
execute on hardware, inspect episode evidence, and evaluate a targeted change. Projects
own their implementation and operating documentation; shared engineering conventions
live at the repository root.

## Projects

| Project | Scope | Status |
| --- | --- | --- |
| [LaundryBench](projects/laundrybench/README.md) | SO-101 laundry manipulation with demonstration recording, ACT training, supervised rollout, and an evidence review application | Software implemented and tested offline; physical acceptance and task performance pending |

## LaundryBench

The first benchmark is a controlled sock-versus-non-sock sorting task with one SO-101
arm and a fixed camera. LaundryBench owns task definitions, evaluation protocols,
experiment identity, telemetry, and human-reviewed outcomes. LeRobot provides hardware,
dataset, and policy mechanics.

[Project overview](projects/laundrybench/README.md) ·
[Architecture](projects/laundrybench/docs/architecture/v1-architecture.md) ·
[Operator playbook](projects/laundrybench/docs/playbooks/so101-home-feedback-loop.md) ·
[Milestones](projects/laundrybench/ROADMAP.md)

## Run locally

Requirements: Python 3.11+; Node.js 22+ for the results application. From the repository root:

```bash
python3 -m venv .venv
make install
make check
make demo
```

To open the results application with synthetic experiments:

```bash
make frontend-install
make frontend-check
make web-demo
make web
```

Open `http://127.0.0.1:8765`. Synthetic runs verify software behavior; they do not
establish robot performance. For recording, training, and physical rollout, follow
the [operator playbook](projects/laundrybench/docs/playbooks/so101-home-feedback-loop.md).

## Repository structure

| Path | Responsibility |
| --- | --- |
| [`projects/`](projects/README.md) | Robotics projects, each with its own code, configuration, tests, experiments, and documentation |
| [`docs/`](docs/README.md) | Shared engineering workflow and document templates |
| [`skills/`](skills/factory/README.md) | Repository-local engineering and hardware workflows for coding agents |
| [`AGENTS.md`](AGENTS.md) | Contributor boundaries, validation commands, and hardware requirements |
| [`Makefile`](Makefile) | Common development and validation entry points |

Project-specific dependencies stay within the project. Shared packages are extracted
only when multiple projects need the same tested interface.

## Engineering standards

- Bind results to source, configuration, dataset, checkpoint, and evaluation protocol.
- Preserve episode evidence and distinguish original observations from review labels.
- Compare baseline and candidate under compatible conditions.
- Require supervised, explicitly configured hardware execution.
- Publish physical task results only when supported by recorded hardware evidence.
