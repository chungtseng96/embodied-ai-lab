# Experiment: <name>

**Date:** YYYY-MM-DD
**Status:** Planned | Running | Complete | Abandoned
**Hardware:** mock | physical
**Owner:** <name>

<!-- All four header fields are checked by tests/test_experiment_docs.py. Hardware must be exactly
     `mock` or `physical`. Mock results are never robot results (see CONTEXT.md). -->

## Question

What are we trying to learn?

## Hypothesis

What do we expect to happen and why?

## Baseline

- policy/model:
- dataset:
- code/config version:
- evaluation conditions:

## Change

Change one primary variable when possible.

## Evaluation protocol

- number of attempts:
- held-out conditions:
- success definition:
- intervention policy:

## Results

| Metric | Baseline | Candidate |
|---|---:|---:|
| Success rate | | |
| Median completion time | | |
| Human interventions | | |

## Failure breakdown

## Evidence

- code/config commit:
- command run:
- output excerpt (raw, not paraphrased):
- episode log path:
- negative check (what would have failed if the change did nothing?):

## Conclusion

## What to try next
