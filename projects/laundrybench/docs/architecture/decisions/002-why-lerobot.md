# ADR 002 — Use LeRobot as the robotics foundation

## Decision
Reuse LeRobot for supported hardware integration, dataset conventions, and policy workflows.

## Why
LaundryBench owns task protocols, experiment provenance, and evaluation. Reusing
LeRobot keeps servo drivers, dataset mechanics, and policy implementations behind
a maintained integration boundary.

## We own
- task definitions
- experiment configuration
- evaluation protocol
- outcome/failure logging
- comparison reports
- model/data iteration workflow

## We reuse
- hardware connectivity where supported
- dataset tooling
- training/policy implementations where appropriate
