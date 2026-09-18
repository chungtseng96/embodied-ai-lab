# ADR 003 — Keep the policy boundary model-agnostic

**Date:** 2026-09-15
**Status:** Accepted
**Owner:** James Wang

## Decision
LaundryBench should depend on a small `Policy` interface rather than ACT-, SmolVLA-, or vendor-specific code throughout the system.

## Why
We want to compare policies later without rewriting evaluation, observability, or task code.

```text
Observation -> Policy -> Action
                 |
         ACT / SmolVLA / future
```

## Tradeoff
Real policies may expose model-specific features. Adapters should translate those features at the policy boundary rather than leak them through the whole application.
