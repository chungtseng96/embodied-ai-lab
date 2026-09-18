# LaundryBench Evaluation Platform Architecture

## Purpose

LaundryBench is a physical laundry-sorting benchmark and a small evaluation
platform for robot-learning systems.

The platform should answer four questions for every experiment:

1. What exactly was evaluated?
2. Under which physical and software conditions?
3. What happened during each episode?
4. What should change next, and did that change help?

The first implementation should be local-first and simple. Files, typed
records, and deterministic reports are more important than a service-oriented
deployment.

## Architectural boundary

```text
                  experiment manifest
                          │
                          ▼
task / conditions ──► evaluation runner ◄── policy adapter
                          │                    ▲
                          │                    │
                          ▼                    │
                    robot adapter             │
                          │                    │
                          ▼                    │
                 physical / mock / sim        │
                          │                    │
                          └──── observations + actions
                                       │
                                       ▼
                              episode recorder
                                       │
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                  ▼
             quality checks      outcome labels      media/artifacts
                    │                  │                  │
                    └──────────────────┼──────────────────┘
                                       ▼
                              metrics + report
                                       │
                                       ▼
                         failure-driven data change
```

The policy and robot adapters are replaceable. The evaluation runner,
episode contract, protocol, reports, and iteration logic are the core
LaundryBench-owned system.

## Components

### 1. Task and condition protocol

Defines what an episode means and how the environment is prepared.

Examples of condition fields:

- task name and task version
- object identities and initial placements
- camera configuration
- lighting or background condition
- distractor/clutter level
- expected success criteria
- reset procedure
- whether manual intervention is allowed

Conditions should be represented in a manifest so the same condition set can
be replayed for a baseline and a candidate policy.

### 2. Experiment manifest

The manifest is the reproducibility boundary for a run. It should identify:

- experiment ID and protocol version
- policy name, checkpoint, and policy configuration
- dataset or demonstration revision
- robot implementation and hardware identifier
- calibration revision
- camera configuration
- repository commit
- random seed, when applicable
- requested conditions and number of episodes

The manifest should be saved with the run rather than reconstructed from
command-line history later.

### 3. Robot and policy adapters

The existing `Robot` and `Policy` protocols remain the narrow runtime
interfaces.

The first backend progression is:

```text
mock robot + mock policy
          ↓
replay/scripted or simulation backend
          ↓
LeRobot-backed SO-101 + ACT
          ↓
additional policy adapters
```

The runner should not need to know whether a policy is scripted, ACT,
Diffusion Policy, or a VLA.

### 4. Episode recorder

The current final-result logger should grow into a step-level recorder.

An episode should contain:

- episode identity and condition identity
- start/end timestamps and duration
- observations or references to observations
- actions and action timing
- robot state and camera/media references
- policy metadata and inference timing
- intervention events
- terminal outcome
- failure labels and annotator information

Large media should remain external artifacts referenced by the episode record.
The first storage implementation can be JSONL plus local files; it does not
need a database.

### 5. Quality checks

Quality checks should run before training and before trusting an evaluation.

Initial checks should include:

- missing or malformed metadata
- non-monotonic timestamps
- frame-count or stream-length mismatch
- camera freeze or missing frames
- NaN, clipped, frozen, or discontinuous actions
- impossible joint values or safety-limit violations
- incomplete episode traces
- missing outcome labels

Checks should produce machine-readable results and a human-readable report.

### 6. Outcome labeling and failure taxonomy

Success is not enough for LaundryBench. The first taxonomy should stay small
and observable:

- `success`
- `missed_grasp`
- `grasp_lost`
- `wrong_object`
- `wrong_destination`
- `dropped_object`
- `timeout`
- `human_intervention`
- `safety_stop`
- `other_or_unknown`

Labels should distinguish what was observed from what is inferred. For
example, `missed_grasp` can be a human label even if the system cannot yet
automatically detect contact failure.

### 7. Metrics and reports

The first report should include:

- episode count and success rate
- failure-category counts and rates
- intervention rate
- completion-time distribution
- per-condition breakdown
- confidence intervals or uncertainty for small samples
- links to episode media and traces
- comparison with a named baseline

The report should make it easy to answer “what got worse?” rather than only
displaying a single aggregate score.

### 8. Failure-driven data iteration

An iteration should record the connection between evidence and change:

```text
failure category
      ↓
selected episodes / conditions
      ↓
targeted demonstrations or configuration change
      ↓
new dataset / policy version
      ↓
same evaluation protocol
```

The system should preserve the baseline and candidate artifacts so a negative
result is still useful and reproducible.

## Proposed artifact layout

```text
outputs/
└── exp-001-baseline/
    ├── manifest.yaml
    ├── summary.json
    ├── episodes.jsonl
    ├── quality.json
    ├── report.html
    ├── media/
    └── traces/
```

This is a starting convention, not a commitment to a permanent storage
format.

## Testing strategy

### Unit tests

- metrics and aggregation
- protocol validation
- failure-label validation
- manifest serialization
- quality-check calculations

### Contract tests

- every robot backend satisfies reset/observe/apply/success behavior
- every policy adapter accepts the shared observation and returns an action
- every episode recorder emits a valid episode record

### Deterministic integration tests

- run the same mock condition manifest twice
- compare summaries and episode structure
- inject dropped frames, bad actions, timeouts, and interventions
- verify reports identify the injected problems

### Physical validation

Physical runs are required for robot-performance claims. Mock and simulation
backends validate software behavior and safety boundaries, not physical task
success.

## Initial vertical slice

Before adding a second policy or a full simulator, implement this slice:

1. Load a condition and experiment manifest.
2. Run the existing mock loop.
3. Record step-level traces.
4. Emit a local HTML/JSON report.
5. Compare two named mock policy versions.
6. Inject and classify at least one failure mode.
7. Preserve the artifacts needed to reproduce the report.

Then replace the mock robot/policy with the first LeRobot-backed physical
implementation while keeping the evaluation contract unchanged.

## Open questions

- Should the canonical episode schema be JSONL, Parquet, or an adapter around
  LeRobotDataset?
- Which camera/media references should be stored directly versus externally?
- How much of outcome labeling can be automated safely?
- Should condition manifests be generated from YAML, Python, or both?
- Which report format is most useful during hardware bring-up: static HTML,
  Rerun, or both?
