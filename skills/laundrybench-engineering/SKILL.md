---
name: laundrybench-engineering
description: Work on LaundryBench Python code, configs, tests, scripts, and experiment artifacts while preserving its hardware/cloud boundaries.
---

# LaundryBench engineering

Use this skill for repository changes that affect LaundryBench code,
configuration, tests, CLI scripts, documentation tied to implementation, or
experiment records.

## Workflow

1. Inspect `git status --short` and read the applicable `AGENTS.md` files.
2. Identify the boundary being changed: robot, policy, data, evaluation,
   observability, script, config, or documentation.
3. Keep the mock implementation usable unless the task explicitly concerns
   physical hardware.
4. Prefer a versioned script plus explicit config over an interactive-only
   workflow.
5. Run the smallest relevant checks. For Python changes, use the default
   Python so results match CI:

   ```bash
   make check
   ```

6. If LeRobot environment behavior changed, also run `make lerobot-check` with
   the selected Python.
7. Report limitations such as missing CUDA, Docker daemon access, cameras, or
   robot hardware instead of silently treating them as passing results.

## Design constraints

- LeRobot remains the source of truth for low-level SO-101 control, recording,
  datasets, and policy execution.
- LaundryBench owns task definitions, adapters, evaluation protocols,
  metrics, structured evidence, and experiment history.
- Cloud training must be invocable from a CLI command and a checked-in config.
- A notebook can support exploration, but it cannot be the only reproduction
  path for a result.
- Keep secrets, datasets, checkpoints, videos, and local calibration files out
  of git.
