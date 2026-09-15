# LaundryBench Experiments

Experiments are first-class project artifacts. Each experiment should answer one question and preserve enough context to compare results later.

## Naming

```text
exp-001-baseline/
exp-002-targeted-failures/
exp-003-...
```

## Every experiment should capture

- question / hypothesis
- task and evaluation conditions
- policy/model version
- dataset version
- code/config version
- number of physical attempts
- success definition
- results and failure breakdown
- conclusion and next step

Use `docs/templates/experiment.md` as the starting format.
