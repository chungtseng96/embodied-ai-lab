# LaundryBench V1 Contract Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the LaundryBench software contracts (robot, policy, judge, loop timing, configs, evidence) strong enough that the first physical experiment only has to fill in hardware values, not redesign interfaces.

**Architecture:** Keep the existing `Protocol`-based boundaries and mock-first workflow. Move the success oracle off the robot into a `SuccessJudge`, make the episode loop time-bounded and paced, load the checked-in YAML through one validated config module, and write a run manifest plus per-step records next to the episode log. LeRobot stays outside the core package.

**Tech Stack:** Python 3.11+ (CI) / 3.12 (LeRobot hosts), dataclasses, `typing.Protocol`, PyYAML, pytest, ruff.

**Spec:** [`2026-10-31-laundrybench-design-review.md`](2026-10-31-laundrybench-design-review.md) (findings F1-F13), with
[`../architecture/robot-learning-development-environment.md`](../architecture/robot-learning-development-environment.md),
[`../architecture/decisions/003-policy-abstraction.md`](../architecture/decisions/003-policy-abstraction.md), and
[`so101-readiness.md`](so101-readiness.md) as the governing design.

## Tracking

Linear project: **LaundryBench V1 contract hardening** (team `JWA`,
<https://linear.app/jwang-embodied-ai-lab/team/JWA/active>). One issue per task;
update the issue when the task's commit lands.

| Task | Issue | Task | Issue |
| --- | --- | --- | --- |
| 1 SuccessJudge | JWA-5 | 6 Manifest + artifact layout | JWA-10 |
| 2 reset/stop | JWA-6 | 7 Observation contract | JWA-11 |
| 3 Timed loop | JWA-7 | 8 Step logging | JWA-12 |
| 4 Taxonomy + metrics | JWA-8 | 9 Plan of record + Makefile | JWA-13 |
| 5 Config loading | JWA-9 | Deferred hardware items | JWA-14 to JWA-18 |
| 10 Quality gate | JWA-19 | 11 Summary + report | JWA-20 |
| 12 Comparison + faulty fixture | JWA-21 | 13 Terminal view | JWA-22 |

## Global Constraints

- `requires-python = ">=3.11"`; CI runs stock Python 3.11 with no LeRobot installed. Nothing under `src/laundrybench/` may import `lerobot`.
- Every task leaves the mock loop runnable: `make demo PYTHON=.venv/bin/python` prints a summary.
- Validation for every task: `make check PYTHON=.venv/bin/python` (pytest + `ruff check`, line length 100). Create the venv once with `python3.11 -m venv .venv && .venv/bin/python -m pip install -e "projects/laundrybench[dev]"`.
- All paths below are relative to `projects/laundrybench/` unless they start with `docs/`, `ROADMAP.md`, `README.md`, or `Makefile`.
- No datasets, checkpoints, videos, calibration files, or credentials in git. `outputs/` is already ignored.
- Mock results are never described as physical results, in code comments or docs.
- Commit after each task with a conventional message (`feat:`, `fix:`, `docs:`).

## Review Focus

1. **Policy raises mid-episode.** `run_episode` must call `robot.stop()` and re-raise; the arm must not keep its last target. Test in Task 2.
2. **Clock that never advances, or `control_hz <= 0` / `timeout_s <= 0`.** Must raise `ValueError` before the loop, never spin forever. Test in Task 3.
3. **YAML with an unknown key or a missing file.** `load_config` must raise `ConfigError` naming the file and key. Test in Task 5.
4. **Observation with joint count different from joint names.** Must raise `ValueError` at construction. Test in Task 7.
5. **Manifest written where `git` is unavailable or the directory is not a repo.** `git_revision()` returns `"unknown"`, never raises. Test in Task 6.

---

### Task 1: Move the success oracle into a `SuccessJudge`

Fixes F1. Records the decision as ADR 004.

**Files:**
- Create: `src/laundrybench/evaluation/judge.py`
- Create: `docs/architecture/decisions/004-success-judge.md`
- Modify: `src/laundrybench/robot/base.py` (remove `task_success`)
- Modify: `src/laundrybench/robot/mock.py` (remove `task_success`, `_rng`, `_success_after_steps`)
- Modify: `src/laundrybench/evaluation/runner.py`
- Modify: `scripts/evaluate.py`
- Test: `tests/test_judge.py`, `tests/test_runner.py`

**Interfaces:**
- Produces:
  ```python
  class SuccessJudge(Protocol):
      def is_success(self, observation: Observation) -> bool: ...   # called after every step; True ends the episode as a success
      def on_timeout(self, observation: Observation) -> bool: ...   # final verdict when time runs out
  class MockSuccessJudge:
      def __init__(self, seed: int = 0, success_after_steps: int = 4, success_probability: float = 0.8) -> None
  def run_episode(robot: Robot, policy: Policy, judge: SuccessJudge, *, max_steps: int = 20) -> EpisodeResult
  ```
  `MockSuccessJudge.is_success` reads `observation.metadata["step"]` (already set by `MockRobot.observe`), returns `False` below `success_after_steps`, otherwise `rng.random() < success_probability`. `on_timeout` returns `False`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_judge.py
def test_mock_judge_is_false_before_threshold():
    judge = MockSuccessJudge(seed=0, success_after_steps=3)
    assert judge.is_success(Observation(0.0, [0.0] * 6, metadata={"step": 2})) is False

def test_mock_judge_is_deterministic_for_seed():
    obs = Observation(0.0, [0.0] * 6, metadata={"step": 5})
    a = [MockSuccessJudge(seed=1).is_success(obs) for _ in range(5)]
    b = [MockSuccessJudge(seed=1).is_success(obs) for _ in range(5)]
    assert a == b

def test_mock_judge_on_timeout_is_false():
    assert MockSuccessJudge().on_timeout(Observation(0.0, [0.0] * 6)) is False
```

Update `tests/test_runner.py` so both tests pass a judge: `run_episode(MockRobot(seed=0), MockPolicy(), MockSuccessJudge(seed=0, success_after_steps=1), max_steps=5)` and `success_after_steps=100` for the failing case. Add:

```python
def test_robot_protocol_has_no_task_success():
    assert not hasattr(MockRobot(), "task_success")
```

- [ ] **Step 2: Run tests, expect ImportError on `laundrybench.evaluation.judge`**

Run: `.venv/bin/python -m pytest projects/laundrybench/tests -q`

- [ ] **Step 3: Implement `judge.py`, strip `task_success` from `Robot` and `MockRobot`, thread `judge` through `run_episode` and `evaluate.py`**

In the runner, replace `if robot.task_success():` with `if judge.is_success(observation):` where `observation` is the one returned by `robot.observe()` after `robot.apply(action)`; call `robot.observe()` again after `apply` so the judge sees post-action state. On exhausting `max_steps`, set `success=judge.on_timeout(last_observation)` and keep `failure_category="timeout_or_task_failure"` only when that is `False`.

- [ ] **Step 4: Write ADR 004**

`docs/architecture/decisions/004-success-judge.md`, same shape as ADR 003: Decision (success is judged by a `SuccessJudge`, not the robot), Why (a real arm cannot observe task outcome; `evaluation.yaml` requires a manual label; keeps the robot adapter a pure I/O boundary), Tradeoff (one more object to wire; a manual judge blocks on the operator, which is intended).

- [ ] **Step 5: Run `make check PYTHON=.venv/bin/python` and `make demo PYTHON=.venv/bin/python`, expect pass and a JSON summary**

- [ ] **Step 6: Commit** `feat: move success judgment off the robot into SuccessJudge (ADR 004)`

---

### Task 2: `Policy.reset()` and `Robot.stop()` with guaranteed shutdown

Fixes F2, F3.

**Files:**
- Modify: `src/laundrybench/policies/base.py`, `src/laundrybench/policies/mock.py`
- Modify: `src/laundrybench/robot/base.py`, `src/laundrybench/robot/mock.py`
- Modify: `src/laundrybench/evaluation/runner.py`
- Test: `tests/test_runner.py`

**Interfaces:**
- Produces: `Policy.reset(self) -> None` (called once per episode before the first `act`); `Robot.stop(self) -> None` (halt motion and hold; idempotent; called in `finally` every episode). `MockPolicy.reset_calls: int`, `MockRobot.stopped: bool` for tests.

- [ ] **Step 1: Write failing tests**

```python
def test_runner_resets_policy_each_episode():
    policy = MockPolicy()
    robot = MockRobot()
    judge = MockSuccessJudge(success_after_steps=1)
    run_episode(robot, policy, judge, max_steps=3)
    run_episode(robot, policy, judge, max_steps=3)
    assert policy.reset_calls == 2

def test_runner_stops_robot_when_policy_raises():
    class ExplodingPolicy:
        name = "boom"
        def reset(self): ...
        def act(self, observation): raise RuntimeError("boom")
    robot = MockRobot()
    with pytest.raises(RuntimeError):
        run_episode(robot, ExplodingPolicy(), MockSuccessJudge(), max_steps=3)
    assert robot.stopped is True

def test_runner_stops_robot_after_normal_episode():
    robot = MockRobot()
    run_episode(robot, MockPolicy(), MockSuccessJudge(success_after_steps=1), max_steps=3)
    assert robot.stopped is True
```

- [ ] **Step 2: Run tests, expect AttributeError on `reset_calls` / `stopped`**

- [ ] **Step 3: Add `reset()` to `Policy` and `MockPolicy` (increment `reset_calls`), `stop()` to `Robot` and `MockRobot` (set `stopped = True`; `reset()` sets it back to `False`), wrap the runner loop in `try: ... finally: robot.stop()` and call `policy.reset()` right after `robot.reset()`**

- [ ] **Step 4: Run `make check PYTHON=.venv/bin/python`, expect pass**

- [ ] **Step 5: Commit** `feat: add Policy.reset and Robot.stop with guaranteed shutdown in run_episode`

---

### Task 3: Time-bounded, paced episode loop

Fixes F4. Replaces `max_steps` with `control_hz` and `timeout_s`.

**Files:**
- Modify: `src/laundrybench/evaluation/runner.py`
- Modify: `scripts/evaluate.py`
- Create: `tests/conftest.py` (fake clock)
- Test: `tests/test_runner.py`

**Interfaces:**
- Produces:
  ```python
  def run_episode(
      robot: Robot, policy: Policy, judge: SuccessJudge, *,
      control_hz: float, timeout_s: float,
      clock: Callable[[], float] = time.perf_counter,
      sleep: Callable[[float], None] = time.sleep,
  ) -> EpisodeResult
  ```
  Raises `ValueError` if `control_hz <= 0` or `timeout_s <= 0`. Each iteration: observe, act, apply, observe, judge; then `sleep(max(0.0, next_tick - clock()))` where `next_tick` advances by `1 / control_hz`; a successful judge verdict returns before that sleep. Stops when `clock() - start >= timeout_s`. `EpisodeResult.metadata` gains `"control_hz"` and keeps `"steps"`. `duration_s` is measured with `clock`.
- Test helper in `conftest.py`:
  ```python
  class FakeClock:
      def __init__(self): self.t = 0.0
      def now(self) -> float: return self.t
      def sleep(self, dt: float) -> None: self.t += dt
  @pytest.fixture
  def fake_clock(): return FakeClock()
  ```

- [ ] **Step 1: Write failing tests (replace the `max_steps` tests)**

```python
def test_episode_times_out_at_timeout_s(fake_clock):
    result = run_episode(MockRobot(), MockPolicy(), MockSuccessJudge(success_after_steps=10_000),
                         control_hz=10, timeout_s=2.0, clock=fake_clock.now, sleep=fake_clock.sleep)
    assert result.success is False
    assert result.metadata["steps"] == 20
    assert result.duration_s == pytest.approx(2.0)

def test_episode_paces_at_control_hz(fake_clock):
    result = run_episode(MockRobot(), MockPolicy(), MockSuccessJudge(success_after_steps=4, success_probability=1.0),
                         control_hz=5, timeout_s=10.0, clock=fake_clock.now, sleep=fake_clock.sleep)
    assert result.success is True
    assert result.metadata["steps"] == 4
    assert result.duration_s == pytest.approx(0.6)  # success returns before the 4th pacing sleep

@pytest.mark.parametrize("kwargs", [{"control_hz": 0, "timeout_s": 1}, {"control_hz": 10, "timeout_s": 0}])
def test_episode_rejects_non_positive_timing(kwargs):
    with pytest.raises(ValueError):
        run_episode(MockRobot(), MockPolicy(), MockSuccessJudge(), **kwargs)
```

Keep `test_runner_stops_robot_when_policy_raises` and the reset test, switching them to `control_hz=10, timeout_s=1.0` with `fake_clock`.

- [ ] **Step 2: Run tests, expect TypeError on unexpected keyword `control_hz`**

- [ ] **Step 3: Implement the new signature in `runner.py`; in `evaluate.py` pass `control_hz=30, timeout_s=30.0` for now (Task 5 moves these into config)**

- [ ] **Step 4: Run `make check PYTHON=.venv/bin/python` and `make demo PYTHON=.venv/bin/python`; the demo must finish in under 2 seconds because the mock judge succeeds by step 4 at 30 Hz**

- [ ] **Step 5: Commit** `feat: pace run_episode at control_hz and bound it by timeout_s`

---

### Task 4: Failure taxonomy and aligned metrics

Fixes F5, F10. Names follow the run-workflow diagram (D2).

**Files:**
- Modify: `src/laundrybench/types.py`
- Modify: `src/laundrybench/evaluation/metrics.py`
- Modify: `src/laundrybench/evaluation/runner.py` (use the enum)
- Modify: `src/laundrybench/observability/logger.py` (serialize enum as its value)
- Modify: `configs/evaluation.yaml` (metric names)
- Test: `tests/test_metrics.py`, `tests/test_logger.py`

**Interfaces:**
- Produces in `types.py`:
  ```python
  class FailureCategory(str, Enum):
      MISSED_GRASP = "missed_grasp"; GRASP_LOST = "grasp_lost"; WRONG_OBJECT = "wrong_object"
      DROPPED = "dropped"; MISSED_BASKET = "missed_basket"; TIMEOUT = "timeout"
      INTERVENTION = "intervention"; HARDWARE_FAULT = "hardware_fault"
      FROZEN_CAMERA = "frozen_camera"; UNSPECIFIED = "unspecified"
  ```
  `EpisodeResult.failure_category: FailureCategory | None`.
- `summarize(results) -> dict[str, object]` returns exactly these keys: `episodes`, `successes`, `success_rate`, `median_completion_time_s` (median `duration_s` over **successful** episodes, `0.0` if none), `intervention_rate` (interventions / episodes, `0.0` if empty), `failure_category_counts` (dict of `category.value -> int` over failed episodes; a failed episode with `None` counts as `"unspecified"`).
- `configs/evaluation.yaml` `metrics:` list becomes those four names: `success_rate`, `median_completion_time_s`, `intervention_rate`, `failure_category_counts`.
- Runner timeout path sets `failure_category=FailureCategory.TIMEOUT`.

- [ ] **Step 1: Write failing tests**

```python
def test_summarize_counts_failure_categories_and_rates():
    results = [
        EpisodeResult("a", True, 1.0),
        EpisodeResult("b", True, 3.0),
        EpisodeResult("c", False, 5.0, intervention=True, failure_category=FailureCategory.MISSED_GRASP),
        EpisodeResult("d", False, 6.0, failure_category=None),
    ]
    s = summarize(results)
    assert s["success_rate"] == 0.5
    assert s["median_completion_time_s"] == 2.0
    assert s["intervention_rate"] == 0.25
    assert s["failure_category_counts"] == {"missed_grasp": 1, "unspecified": 1}

def test_summarize_empty_results():
    s = summarize([])
    assert s["episodes"] == 0 and s["success_rate"] == 0.0
    assert s["failure_category_counts"] == {}

# tests/test_logger.py
def test_jsonl_logger_serializes_failure_category_as_string(tmp_path):
    logger = JsonlEpisodeLogger(tmp_path / "e.jsonl")
    logger.log(EpisodeResult("x", False, 1.0, failure_category=FailureCategory.TIMEOUT))
    payload = json.loads((tmp_path / "e.jsonl").read_text().strip())
    assert payload["failure_category"] == "timeout"
```

Update `test_runner.py` timeout assertion to `result.failure_category is FailureCategory.TIMEOUT`.

- [ ] **Step 2: Run tests, expect ImportError on `FailureCategory`**

- [ ] **Step 3: Implement the enum, the new `summarize`, the runner change, and `json.dumps(..., default=lambda o: o.value if isinstance(o, Enum) else str(o))` in the logger; edit the YAML metric names**

- [ ] **Step 4: Run `make check PYTHON=.venv/bin/python`, expect pass**

- [ ] **Step 5: Commit** `feat: add FailureCategory taxonomy and align summarize with evaluation.yaml`

---

### Task 5: Load and validate the checked-in configs

Fixes F6. `evaluate.py` stops hardcoding values.

**Files:**
- Create: `src/laundrybench/config.py`
- Modify: `configs/evaluation.yaml` (add `control_hz: 30`, `seed: 7`; remove `max_steps`)
- Modify: `scripts/evaluate.py`
- Test: `tests/test_config.py`; add to `tests/conftest.py`: `REPO_CONFIGS = Path(__file__).resolve().parents[1] / "configs"` and `def copy_configs(src: Path, dst: Path) -> None` (copies the four YAML files). Task 6 reuses both.

**Interfaces:**
- Produces:
  ```python
  class ConfigError(ValueError): ...
  @dataclass(frozen=True) class RobotConfig: implementation: str; hardware_target: str; follower_port: str | None; leader_port: str | None; max_episode_seconds: float; require_manual_supervision: bool
  @dataclass(frozen=True) class CameraConfig: implementation: str; device_index: int; width: int; height: int; fps: int; placement: str
  @dataclass(frozen=True) class TaskConfig: name: str; description: str; timeout_seconds: float; success_criteria: tuple[str, ...]; environment: dict[str, object]
  @dataclass(frozen=True) class EvaluationConfig: attempts_per_condition: int; control_hz: float; seed: int; record_video: bool; record_joint_state: bool; record_policy_metadata: bool; require_manual_success_label: bool; metrics: tuple[str, ...]
  @dataclass(frozen=True) class LaundryBenchConfig: robot: RobotConfig; camera: CameraConfig; task: TaskConfig; evaluation: EvaluationConfig
  def load_config(config_dir: Path) -> LaundryBenchConfig
  ```
  Each YAML has one top-level key matching its file stem (`robot`, `camera`, `task`, `evaluation`); `robot.safety.*` flattens into `RobotConfig`. Unknown keys at any level under a dataclass raise `ConfigError(f"{file}: unknown key '{key}'")`; a missing file raises `ConfigError(f"missing config file: {path}")`; missing required key raises `ConfigError(f"{file}: missing key '{key}'")`.
- `evaluate.py` arguments: `--config-dir` (default `configs`), `--episodes` (default from `evaluation.attempts_per_condition`), `--output` (default `outputs/mock-episodes.jsonl`). It builds `MockRobot(seed=config.evaluation.seed)`, `MockSuccessJudge(seed=config.evaluation.seed)`, and passes `control_hz=config.evaluation.control_hz`, `timeout_s=min(config.task.timeout_seconds, config.robot.max_episode_seconds)`.

- [ ] **Step 1: Write failing tests**

```python
from conftest import REPO_CONFIGS, copy_configs

def test_load_repo_configs():
    cfg = load_config(REPO_CONFIGS)
    assert cfg.task.name == "sock_sorting_v1"
    assert cfg.evaluation.control_hz == 30
    assert cfg.robot.max_episode_seconds == 30

def test_unknown_key_raises(tmp_path):
    copy_configs(REPO_CONFIGS, tmp_path)
    (tmp_path / "task.yaml").write_text("task:\n  name: x\n  bogus: 1\n")
    with pytest.raises(ConfigError, match="unknown key 'bogus'"):
        load_config(tmp_path)

def test_missing_file_raises(tmp_path):
    copy_configs(REPO_CONFIGS, tmp_path)
    (tmp_path / "camera.yaml").unlink()
    with pytest.raises(ConfigError, match="missing config file"):
        load_config(tmp_path)
```

- [ ] **Step 2: Run tests, expect ImportError on `laundrybench.config`**

- [ ] **Step 3: Implement `config.py` with `yaml.safe_load`, dataclass construction via `dataclasses.fields()` for unknown-key detection; update the YAML; rewrite `evaluate.py` to use it**

- [ ] **Step 4: Run `make check PYTHON=.venv/bin/python` and `make demo PYTHON=.venv/bin/python`, expect pass; run `.venv/bin/python projects/laundrybench/scripts/evaluate.py --help` from the repo root, expect the three flags**

- [ ] **Step 5: Commit** `feat: load and validate configs; evaluate.py reads control_hz, timeout, seed from YAML`

---

### Task 6: Run manifest and experiment-keyed artifact layout

Fixes F7. Layout follows the diagrams (D3): one directory per experiment ID.

**Files:**
- Create: `src/laundrybench/observability/manifest.py`
- Modify: `src/laundrybench/evaluation/runner.py` (accept `episode_id`)
- Modify: `scripts/evaluate.py` (`--experiment`, `--output-dir`; writes `manifest.yaml` + `episodes.jsonl`)
- Test: `tests/test_manifest.py`, `tests/test_runner.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class RunManifest:
      experiment_id: str; created_at: str; git_revision: str; config_hash: str; seed: int
      policy_name: str; robot_implementation: str; python_version: str; lerobot_version: str | None
  def git_revision(cwd: Path | None = None) -> str          # "unknown" on any failure
  def config_hash(config_dir: Path) -> str                   # sha256 hex of the four YAML files' bytes, sorted by filename
  def write_manifest(path: Path, manifest: RunManifest) -> None   # YAML via yaml.safe_dump, sort_keys=True
  EXPERIMENT_ID_RE = r"^exp-\d{3}-[a-z0-9-]+$"                     # e.g. exp-001-baseline; evaluate.py rejects others
  ```
  `lerobot_version` is `importlib.metadata.version("lerobot")` if installed else `None`; no `import lerobot`.
- `run_episode(..., episode_id: str | None = None)`: uses the given id or falls back to `uuid4()`. `evaluate.py` passes `f"{experiment_id}-{index:03d}"`.
- `evaluate.py` gains `--experiment` (required, must match `EXPERIMENT_ID_RE`) and replaces `--output` with `--output-dir` (default `outputs`); writes `outputs/<experiment_id>/manifest.yaml` and `outputs/<experiment_id>/episodes.jsonl`. Re-running the same experiment ID refuses to overwrite unless `--force`.
- Directory contract for later tasks: `outputs/<experiment_id>/{manifest.yaml, episodes.jsonl, traces/steps.jsonl, quality.json, summary.json, report.html, media/}`.

- [ ] **Step 1: Write failing tests**

```python
def test_git_revision_unknown_outside_repo(tmp_path):
    assert git_revision(cwd=tmp_path) == "unknown"

def test_config_hash_is_stable_and_changes_with_content(tmp_path):
    copy_configs(REPO_CONFIGS, tmp_path)
    h1 = config_hash(tmp_path)
    assert h1 == config_hash(tmp_path)
    (tmp_path / "task.yaml").write_text("task:\n  name: other\n")
    assert config_hash(tmp_path) != h1

def test_write_manifest_round_trips(tmp_path):
    m = RunManifest("exp-001-baseline", "2026-10-31T00:00:00Z", "abc", "deadbeef", 7, "mock-policy", "mock", "3.11.0", None)
    write_manifest(tmp_path / "manifest.yaml", m)
    assert yaml.safe_load((tmp_path / "manifest.yaml").read_text())["experiment_id"] == "exp-001-baseline"

def test_evaluate_rejects_bad_experiment_id():
    assert re.match(EXPERIMENT_ID_RE, "exp-001-baseline")
    assert not re.match(EXPERIMENT_ID_RE, "baseline")

# tests/test_runner.py
def test_runner_uses_given_episode_id(fake_clock):
    result = run_episode(MockRobot(), MockPolicy(), MockSuccessJudge(success_after_steps=1, success_probability=1.0),
                         control_hz=10, timeout_s=1.0, clock=fake_clock.now, sleep=fake_clock.sleep,
                         episode_id="exp-001-baseline-001")
    assert result.episode_id == "exp-001-baseline-001"
```

- [ ] **Step 2: Run tests, expect ImportError on `laundrybench.observability.manifest`**

- [ ] **Step 3: Implement `manifest.py` (`subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True, timeout=5)` guarded by `try/except (OSError, subprocess.SubprocessError)` and non-zero return), the runner parameter, and the `evaluate.py` output layout**

- [ ] **Step 4: Run `make check PYTHON=.venv/bin/python` and `make demo PYTHON=.venv/bin/python`; run the demo with `--experiment exp-000-mock-smoke`, confirm `outputs/exp-000-mock-smoke/manifest.yaml` exists and `git status --short` shows no `outputs/` entry**

- [ ] **Step 5: Commit** `feat: experiment-keyed output directory with manifest.yaml and deterministic episode ids`

---

### Task 7: Observation contract with joint names, units, and image slots

Fixes F9.

**Files:**
- Modify: `src/laundrybench/types.py`
- Create: `src/laundrybench/robot/so101_spec.py`
- Modify: `src/laundrybench/robot/mock.py`
- Modify: `src/laundrybench/policies/mock.py` (no change to behavior; confirm it only reads `metadata["step"]`)
- Test: `tests/test_types.py`

**Interfaces:**
- Produces:
  ```python
  # so101_spec.py
  SO101_JOINT_NAMES: tuple[str, ...] = ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper")
  JointUnits = Literal["degrees", "normalized"]
  # types.py
  @dataclass(slots=True)
  class Observation:
      timestamp_s: float
      joint_positions: list[float]
      joint_names: tuple[str, ...] = SO101_JOINT_NAMES
      joint_units: JointUnits = "normalized"
      images: dict[str, Any] = field(default_factory=dict)   # camera name -> array-like frame or None
      metadata: dict[str, Any] = field(default_factory=dict)
      def __post_init__(self): raise ValueError(...) if len(joint_positions) != len(joint_names)
  ```
  `image_ref` is removed. `MockRobot.observe` returns `images={"front": None}`.
  `Action` gains `joint_names: tuple[str, ...] = SO101_JOINT_NAMES` with the same length check.

- [ ] **Step 1: Write failing tests**

```python
def test_observation_defaults_to_so101_joints():
    obs = Observation(0.0, [0.0] * 6)
    assert obs.joint_names == SO101_JOINT_NAMES and obs.joint_units == "normalized"

def test_observation_rejects_joint_length_mismatch():
    with pytest.raises(ValueError, match="6 joint names"):
        Observation(0.0, [0.0] * 5)

def test_action_rejects_joint_length_mismatch():
    with pytest.raises(ValueError):
        Action(joint_targets=[0.0] * 7)

def test_mock_robot_observation_has_front_camera_slot():
    assert "front" in MockRobot().observe().images
```

- [ ] **Step 2: Run tests, expect ImportError on `so101_spec` / AttributeError on `joint_names`**

- [ ] **Step 3: Implement; grep for `image_ref` across `src/`, `tests/`, `scripts/`, `docs/` and remove every use**

- [ ] **Step 4: Run `make check PYTHON=.venv/bin/python`, expect pass**

- [ ] **Step 5: Commit** `feat: give Observation/Action explicit joint names, units, and camera image slots`

---

### Task 8: Per-step trajectory logging

Fixes F8. Depends on Task 7's `Observation` shape.

**Files:**
- Modify: `src/laundrybench/observability/logger.py`
- Modify: `src/laundrybench/evaluation/runner.py` (`on_step` hook)
- Modify: `scripts/evaluate.py` (writes `traces/steps.jsonl` in the experiment dir)
- Test: `tests/test_logger.py`, `tests/test_runner.py`

**Interfaces:**
- Produces:
  ```python
  class JsonlStepLogger:
      def __init__(self, path: str | Path) -> None
      def log(self, episode_id: str, step: int, observation: Observation, action: Action) -> None
  ```
  One JSON line per step with keys: `episode_id`, `step`, `timestamp_s`, `joint_positions`, `joint_names`, `joint_units`, `image_keys` (sorted list of `observation.images` keys; frames are never serialized), `joint_targets`, `action_metadata`.
- `run_episode(..., on_step: Callable[[str, int, Observation, Action], None] | None = None)`; called once per step with the pre-action observation and the action, before `robot.apply`.

- [ ] **Step 1: Write failing tests**

```python
def test_step_logger_writes_one_line_per_step_without_frames(tmp_path):
    logger = JsonlStepLogger(tmp_path / "steps.jsonl")
    obs = Observation(1.0, [0.0] * 6, images={"front": object()})
    logger.log("ep", 0, obs, Action(joint_targets=[0.1] * 6))
    payload = json.loads((tmp_path / "steps.jsonl").read_text().strip())
    assert payload["image_keys"] == ["front"]
    assert "images" not in payload
    assert payload["joint_targets"] == [0.1] * 6

# tests/test_runner.py
def test_runner_calls_on_step_each_step(fake_clock):
    seen = []
    run_episode(MockRobot(), MockPolicy(), MockSuccessJudge(success_after_steps=3, success_probability=1.0),
                control_hz=10, timeout_s=5.0, clock=fake_clock.now, sleep=fake_clock.sleep,
                episode_id="e", on_step=lambda eid, i, o, a: seen.append((eid, i)))
    assert seen == [("e", 0), ("e", 1), ("e", 2)]
```

- [ ] **Step 2: Run tests, expect ImportError / TypeError**

- [ ] **Step 3: Implement the logger and hook; in `evaluate.py` create `JsonlStepLogger(experiment_dir / "traces" / "steps.jsonl")` and pass `on_step=step_logger.log`**

- [ ] **Step 4: Run `make check PYTHON=.venv/bin/python` and `make demo PYTHON=.venv/bin/python`; confirm `outputs/exp-000-mock-smoke/traces/steps.jsonl` has more lines than `episodes.jsonl`**

- [ ] **Step 5: Commit** `feat: log per-step observations and actions to steps.jsonl`

---

### Task 9: One plan of record and a working default `make check`

Fixes F11, F12. Documentation plus a one-line Makefile change.

**Files:**
- Modify: `Makefile` (line 1)
- Modify: `ROADMAP.md`, `README.md`, `projects/laundrybench/README.md`, `docs/plans/so101-readiness.md`, `START-HERE.md`

- [ ] **Step 1: Makefile: `PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)`**

Verify: `make check` (no `PYTHON=`) passes in this worktree; `make check PYTHON=python3.13` still honours the override.

- [ ] **Step 2: Make the implementation plan the plan of record**

- `ROADMAP.md`: add under the title: "Execution detail lives in [`docs/plans/2026-10-31-laundrybench-v1-implementation.md`](docs/plans/2026-10-31-laundrybench-v1-implementation.md); this file tracks milestones only." Tick "Add structured episode logging" stays ticked; add `- [ ] Harden software contracts before hardware (see plan)` under Phase 1.
- `projects/laundrybench/README.md`: replace the "Planned physical integration" list with one sentence linking to the plan and the design review; update "Run the mock loop" to `python3.11 -m venv .venv && .venv/bin/python -m pip install -e "projects/laundrybench[dev]"` then `make check` and `make demo`; update the "Current code layout" tree to add `config.py`, `evaluation/judge.py`, `observability/manifest.py`, `robot/so101_spec.py`.
- `docs/plans/so101-readiness.md`: in "Phase 1" replace "The next refinement is to add the cloud image and a config validator..." with a link to the plan (config validation is Task 5 there; cloud image is in the Deferred section).
- `README.md` and `START-HERE.md`: in the setup/status lines, state that `make check` needs Python 3.11+ and show the venv command.

- [ ] **Step 3: Run `make check` with no arguments, expect pass**

- [ ] **Step 4: Commit** `docs: make the V1 implementation plan the plan of record; default make to .venv`

---

## Phase B: evidence and reporting (from the diagrams, D4 to D7)

Phase B starts after Task 9. Each task reads the directory contract from Task 6 and the step log from Task 8.

### Task 10: Quality gate over step traces

Fixes D4. Mirrors run-workflow step 5.

**Files:**
- Create: `src/laundrybench/evaluation/quality.py`
- Modify: `scripts/evaluate.py` (writes `quality.json` after the run)
- Test: `tests/test_quality.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class QualityFlag: episode_id: str; check: str; detail: str
  def check_episode_quality(steps: list[dict], *, control_hz: float, joint_limits: tuple[float, float] = (-100.0, 100.0)) -> list[QualityFlag]
  def write_quality_report(path: Path, flags: list[QualityFlag], episode_ids: list[str]) -> None   # {"episodes": n, "flagged": n, "flags": [...]}
  ```
  Checks, with `check` values: `frozen_actions` (same `joint_targets` for 10+ consecutive steps), `nan_action` (any non-finite target), `joint_limit` (target outside limits), `timestamp_gap` (consecutive `timestamp_s` differ by more than `3 / control_hz`), `missing_label` (failed episode whose `failure_category` is `unspecified`).

- [ ] **Step 1: Write failing tests**: one test per check with a hand-built `steps` list that trips exactly that check, plus `test_clean_episode_has_no_flags`.
- [ ] **Step 2: Run tests, expect ImportError**
- [ ] **Step 3: Implement `quality.py`; in `evaluate.py` read back `traces/steps.jsonl` grouped by `episode_id` and write `quality.json`**
- [ ] **Step 4: Run `make check PYTHON=.venv/bin/python`, expect pass**
- [ ] **Step 5: Commit** `feat: quality gate over step traces writes quality.json`

### Task 11: Summary and static HTML report

Fixes D5. Mirrors run-workflow step 7 and the diagram's `summary.json` + `report.html`.

**Files:**
- Create: `src/laundrybench/evaluation/report.py`
- Create: `scripts/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Produces:
  ```python
  def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]   # (0.0, 0.0) when n == 0
  def build_summary(experiment_dir: Path) -> dict          # summarize() output + "success_rate_ci" + "quality" counts + manifest fields
  def render_html(summary: dict, baseline: dict | None = None) -> str   # stdlib string.Template, no external deps
  ```
- `scripts/report.py --experiment-dir outputs/exp-001-baseline [--baseline outputs/exp-000-mock-smoke]` writes `summary.json` and `report.html` into the experiment dir. The HTML has: manifest table, success rate with CI, failure category bar list, intervention rate, quality flag count, and a baseline column when given.

- [ ] **Step 1: Write failing tests**: `test_wilson_interval_known_value` (7 of 10 → approx (0.397, 0.892)), `test_build_summary_reads_experiment_dir` using a tmp dir written by the Task 6/8 helpers, `test_render_html_includes_baseline_column`.
- [ ] **Step 2: Run tests, expect ImportError**
- [ ] **Step 3: Implement; keep `render_html` dependency-free**
- [ ] **Step 4: Run `make check PYTHON=.venv/bin/python`; run `scripts/report.py` on the demo output and open `report.html` once to confirm it renders**
- [ ] **Step 5: Commit** `feat: summary.json and static report.html per experiment`

### Task 12: Baseline vs candidate comparison with an injected failure

Fixes D6. Mirrors the EXP-001 to EXP-002 loop and vertical-slice steps 5 and 6.

**Files:**
- Create: `src/laundrybench/policies/faulty.py` (`FaultyMockPolicy`: like `MockPolicy` but emits NaN targets on a configurable step, so the quality gate and taxonomy are exercised end to end)
- Create: `src/laundrybench/evaluation/judge.py` addition: `MockSuccessJudge` gains `failure_category: FailureCategory = FailureCategory.MISSED_GRASP` used on timeout
- Modify: `scripts/evaluate.py` (`--policy mock|faulty`)
- Modify: `scripts/report.py` (already accepts `--baseline`; add `delta` fields to `summary.json`)
- Test: `tests/test_compare.py`

**Interfaces:**
- `build_summary(experiment_dir, baseline_dir=None)` adds `"delta": {"success_rate": float, "failure_category_counts": dict[str, int]}` when a baseline is given.

- [ ] **Step 1: Write failing tests**: run two mock experiments into tmp dirs (mock vs faulty), assert the faulty one has a `nan_action` quality flag and a lower success rate, and that `delta.success_rate` is negative.
- [ ] **Step 2: Run tests, expect failures**
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run `make check PYTHON=.venv/bin/python`, expect pass**
- [ ] **Step 5: Commit** `feat: compare baseline vs candidate experiments; faulty mock policy fixture`

### Task 13: Operator terminal view during a run

Fixes D7. Mirrors observability box "DURING the run".

**Files:**
- Create: `scripts/watch.py`
- Test: `tests/test_watch.py`

**Interfaces:**
- `def format_status(results: list[EpisodeResult], total: int) -> str` returns one line like `episode 7/20 | 4 ok | last: missed_grasp | median 3.1s`.
- `scripts/watch.py --experiment-dir outputs/exp-001-baseline` tails `episodes.jsonl` and reprints `format_status` on each new line; exits when `total` episodes are present or on Ctrl-C.

- [ ] **Step 1: Write failing test** for `format_status` with three results.
- [ ] **Step 2: Run test, expect ImportError**
- [ ] **Step 3: Implement with stdlib only (`time.sleep` polling, no watchdog dependency)**
- [ ] **Step 4: Run `make check PYTHON=.venv/bin/python`, expect pass**
- [ ] **Step 5: Commit** `feat: terminal status view that tails episodes.jsonl`

---

## Deferred until hardware or a Linux GPU host is available

These are specified here so the contract is fixed now, but they cannot be tested in CI or on the Intel Mac. Do not start them in this plan's execution.

- **`ManualSuccessJudge`** (`evaluation/judge.py`): `is_success` returns `False`; `on_timeout` prompts the operator `"Episode {id}: success? [y/n/i(ntervention)]"` and returns the verdict; an `i` answer also sets `intervention=True` via a result hook. Fits the Task 1 protocol unchanged. Needs an operator, so it is a hardware-day item.
- **`SO101LeRobotRobot`** (`robot/so101_lerobot.py`, imports `lerobot` only inside this module): wraps the installed LeRobot SO-101 follower object, maps its observation dict onto `Observation(joint_names=SO101_JOINT_NAMES, joint_units=<from LeRobot config>)`, `stop()` sends the current position as the target then disconnects. Blocked on knowing the exact object shape of the LeRobot version installed on the edge host (see `labs/05`).
- **`scripts/record.py`**: thin `subprocess` wrapper around `lerobot-record` with explicit `--robot.port`, `--robot.id`, `--dataset.repo_id`, `--dataset.num_episodes`, `--dataset.single_task=<task.description>` taken from `load_config`. Never guess a port: refuse to run when `robot.follower_port` is `null`.
- **`scripts/train.py` and `Dockerfile`**: `train.py` wraps `lerobot-train --policy.type=act --dataset.repo_id=... --steps=... --output_dir=...` from a checked-in `configs/training.yaml`; the Dockerfile builds a CUDA image with pinned `lerobot`. The image can be built locally for a smoke test but training needs a Linux NVIDIA host (Phase 4 of the readiness plan).
- **Rerun replay of a single episode** (observability box "AFTER one episode"): needs real frames; the step log from Task 8 is the input. Hardware-day item.
- **Video capture during evaluation**: `evaluation.yaml` has `record_video: true`; the plan intentionally logs `image_keys` only. Decide on hardware day whether video comes from LeRobot dataset recording during rollout or from a separate capture process.
