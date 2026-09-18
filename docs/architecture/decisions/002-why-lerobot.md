# ADR 002 — Use LeRobot as the robotics foundation

**Date:** 2026-09-15
**Status:** Accepted
**Owner:** Chung-Tseng Wang

## Decision
Reuse LeRobot for supported hardware integration, dataset conventions, and policy workflows.

## Why
The portfolio value is in the software around learning and evaluation—not reimplementing servo drivers or a robotics framework.

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
