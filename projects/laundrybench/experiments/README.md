# LaundryBench Experiments

Experiments are first-class project artifacts. Each experiment should answer one question and preserve enough context to compare results later.

## Naming

```text
exp-001-baseline/
exp-002-targeted-failures/
exp-003-...
```

## Every experiment should capture

- `Hardware: mock | physical` in the header (mandatory; mock results are never robot results)
- question / hypothesis
- task and evaluation conditions
- policy/model version
- dataset version
- code/config version
- number of physical attempts
- success definition
- results and failure breakdown
- evidence: commit, command, raw output excerpt, log path, negative check
- conclusion and next step

Use `docs/templates/experiment.md` as the starting format.
