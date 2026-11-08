# Factory repo profile

The factory skills (`skills/factory*/SKILL.md`) describe a workflow that
runs unchanged in any repository; every value specific to this one lives
here. This is the only file a repo edits to adopt the factory
([Adopting the factory in another repo](factory.md#adopting-the-factory-in-another-repo)).
The skills name its sections in bold, for example "the profile's **Pre-push gate**".

## Repo

- `REPO=chungtseng96/embodied-ai-lab`.
- Default base: `main`.
- Protected refs a run never pushes to: `main`.
- Linear ticket prefix: `JWA-<n>` (`/factory JWA-<n>`), team `JWA` in the
  personal workspace `jwang-embodied-ai-lab`.
- Label group: `Factory` (`factory:ready`, `factory:working`,
  `factory:needs-human`, `factory:human-ready`), a single-select group on
  the `JWA` team. `python3 scripts/factory_linear.py ensure-labels` creates
  it idempotently.

## Host

- **Claude Code on the laptop**, interactive or headless (`claude -p`),
  started by a human (`/factory JWA-<n>`) or by the dispatcher
  ([Dispatch](factory.md#dispatch)). No turn cap; the Bash tool caps one
  command at ten minutes, so every gate and watch gets the 600000 ms
  timeout the router's **CI wait** describes. The **Turn budget** rule is
  inactive here.
- **A Superset automation session** on the same laptop runs the same way.
  If a host with a turn cap is ever added, write its cap and budget mark
  here; the **Turn budget** rule then applies with those numbers.
- GitHub as `chungtseng96`, never the machine's default `gh` login: every
  command block that calls `gh` starts with
  `export GH_TOKEN="$(gh auth token --user chungtseng96)"`. Pushes use the
  repo-local credential helper and need nothing extra.

## Ticket kinds

- **Kind:** `R` or `B` from the title marker (`T3 (R): ...`); `R` is a
  refactor whose output must be byte-identical (its goldens are the
  **Goldens** suite), `B` a behavior change; no marker means `B`. Most
  tickets here carry no marker.
- **Pure move:** a ticket that calls itself a pure move or no behavior
  change, with a verbatim-move check, is treated as `R` only for the
  expectation that the diff is no larger than the move, not for the goldens
  gate.
- **Open B-kind decision:** a decision the ticket leaves open about the
  task definition, the success judge or evaluation protocol, a hardware
  limit (joint range, speed, torque), a new dependency, or a schema that an
  experiment record or a physical run depends on. "TBD", "decide later", a
  question in the acceptance list, or two options with no choice all count.
  Such a ticket is not ready at pickup and stops `blocked` for a human;
  implement meeting one stops the run.

## Hardware

The factory never touches the arm, a camera, a GPU or the Hub. Out of
bounds in every phase: `scripts/record.py`, `scripts/run_policy.py` and
`scripts/train.py` against anything but their mock or fixture modes, any
command that opens a serial port or camera, any LeRobot command with a real
`robot.port` or `camera`, any upload. `make lerobot-check` and
`make host-check` are allowed: they inspect the environment and connect to
nothing.

**Operator-run criteria.** Pickup files an acceptance criterion under
**Operator-run** when it needs physical evidence or a human present: wording
like "on calibrated hardware", "physical", "supervised", "operator", "real
robot", "camera", "GPU", "cloud training", "record demonstrations",
"rollout on the arm". The run still builds the software side (a dry run, a
mock test, a config check) and lists the criterion under **Not verified**
as `operator-run`; the human runs it under the
[home playbook](../../projects/laundrybench/docs/playbooks/so101-home-feedback-loop.md)
and records it under the physical evidence contract. A ticket whose every
criterion is operator-run has nothing for the factory to build and stops
`blocked` at pickup.

Every evidence line a run writes says `mock`. The run never writes
`physical`.

## Toolchain

The project needs Python 3.11 or newer; the laptop's `python3` is 3.9.
Every worktree gets its own environment, so a check cannot import
LaundryBench from another checkout
([agent guide](../agent-guide.md#checks-from-the-repository-root)). Any
phase that finds `.venv/bin/python` missing in its worktree creates it
first:
```bash
[ -x .venv/bin/python ] || uv venv --python 3.11 .venv
make install
```
`make` picks `.venv/bin/python` on its own. The factory scripts run under
the same interpreter: `.venv/bin/python scripts/factory_linear.py ...`,
`.venv/bin/python scripts/factory_base.py ...`; this profile writes
`python3 scripts/...` as shorthand for that. `uv` is at
`/opt/homebrew/bin/uv`; without it, `python3.13 -m venv .venv`.
Frontend checks need Node 22 (`make frontend-install` once per worktree).

## Workspace

- A git worktree under `.claude/worktrees/` (ignored by git), one per
  ticket, created from the repository root. Fresh branch:
  ```bash
  git -C <repo-root> worktree add --no-track -b $BRANCH .claude/worktrees/<slug> origin/$BASE
  ```
  The dispatcher pre-creates `.claude/worktrees/factory-<ticket>` detached
  at `origin/main`; pickup then runs `git switch --no-track -c $BRANCH
  origin/$BASE` inside it instead of adding a second worktree.
- Restore on resume: the worktree at the recorded path if it exists on this
  host (then `git fetch origin $BRANCH && git merge --ff-only
  origin/$BRANCH`; a failure means local commits another session never saw,
  hard stop), else a new one (`git worktree add .claude/worktrees/<slug>
  $BRANCH` after `git fetch origin $BRANCH:$BRANCH`). Then the
  **Toolchain** setup inside it.
- Every later command runs inside the worktree (Claude Code:
  `EnterWorktree` when available, else `git -C <path>` and `make -C <path>`).
  The shared checkout at the repository root is never switched.

## Files

- **Component resolution.** A boundary named without a path resolves to its
  directory under `projects/laundrybench/src/laundrybench/` (`robot`,
  `policies`, `data`, `evaluation`, `observability`, `training`, `web`), or
  to `projects/laundrybench/scripts/`, `configs/`, `frontend/src/`, `e2e/`,
  `tests/`, `docs/` for those words. The
  [agent guide's route table](../agent-guide.md#route-by-change) maps a
  change kind to its files and tests.
- **Path examples.** Tickets write project-relative paths
  (`scripts/evaluate.py` for `projects/laundrybench/scripts/evaluate.py`,
  `tests/test_web.py` for `projects/laundrybench/tests/test_web.py`). A
  path the ticket creates resolves its parent directory the same way.
- **Complexity unit:** boundaries, so the Readiness line reads
  `Complexity: <small | medium | large> · <n> files, <m> boundaries`.
- **Hard-stop paths:** a change the ticket does not call for under
  `.github/`, `.claude/`, `projects/laundrybench/configs/robot.yaml`,
  `projects/laundrybench/configs/camera.yaml`,
  `projects/laundrybench/Dockerfile.train`, the `dependencies` list of
  `projects/laundrybench/pyproject.toml`, `projects/laundrybench/frontend/package.json`
  dependencies, or any path containing `calibration`, `outputs/`,
  `data/raw/`, `data/processed/`. Generated media, checkpoints and datasets
  are never committed (`.gitignore`); a diff that adds one is a hard stop.

## Standards

- **What simplify judges against:** the root [`AGENTS.md`](../../AGENTS.md)
  (Engineering rules, Hardware boundary),
  [`projects/laundrybench/AGENTS.md`](../../projects/laundrybench/AGENTS.md)
  (boundaries, no LeRobot import in the core package), the
  [agent guide](../agent-guide.md), the architecture doc under
  `projects/laundrybench/docs/architecture/` for each boundary the diff
  touches (`so101-adapter.md`, `recording-workflow.md`,
  `training-workflow.md`, `act-rollout.md`, `physical-evidence.md`,
  `results-application.md`, `evaluation-platform.md`, `outcome-contract.md`,
  `media-contract.md`, `experiment-context.md`), and the
  [bounce log](factory-bounces.md) for entries naming the phase or the
  files. The repository has no `docs/rules/`; record it as absent.
- **Build check:** before each implement commit, `make lint` plus the
  touched test files
  (`cd projects/laundrybench && ../../.venv/bin/python -m pytest tests/<file>`);
  the full `make check` at simplify's new head.

## Verification

This repository has no separate verification guide; these four rules are
what verify wraps.
- **define-the-smallest-complete-outcome:** one sentence a test can decide,
  the command that decides it, and the positive control that shows the
  change does not block good behavior.
- **make-the-test-environment-ready-first:** create the worktree's `.venv`
  and `make install` before the first check; install the frontend only when
  the diff touches it; never point a check at another checkout's
  environment or at hardware.
- **run-the-pre-push-gate:** the **Pre-push gate** lines for the kinds of
  path the diff touches, on the exact head that is pushed; a local failure
  is fixed in its own commit and the gate reruns.
- **own-commands-through-completion:** a check that is started is read to
  its end; a check the host cannot run is written under **Not verified**
  with the missing prerequisite, never reported as passed or quietly
  skipped. Mock and physical evidence are never mixed in one line.

## Component checks

- Always: `make check` (pytest, Ruff, script smoke checks; what CI runs).
- `projects/laundrybench/frontend/**` touched: `make frontend-install` once,
  then `make frontend-check`.
- `src/laundrybench/web/**`, `evaluation/report.py`, `scripts/serve.py`,
  `scripts/report.py`, `scripts/demo_web.py` or `scripts/build_showcase.py`
  touched: `make web-demo` must finish and write its output directory.
- `scripts/*.py` at the repository root touched: `make factory-test`.
- A path in `.github/workflows/lerobot-compat.yml`'s path list touched:
  `make lerobot-check PYTHON=.venv-lerobot/bin/python` when that
  environment exists on the host, else **Not verified** ("no LeRobot
  environment on this host").

## Pre-push gate

Per the **Verification** rule run-the-pre-push-gate:
- Python, config or script changes: `make check`.
- Frontend changes: also `make frontend-check`.
- Any change: `git diff --check $(git merge-base origin/$BASE HEAD)` with
  new files staged.
- Docs-only (**Conventions**): the `git diff --check` line alone.

## CI

- Required check: `check` (workflow `CI`, job `check`). It is
  `REQUIRED_CHECK = "check"` in `scripts/watch_pr_checks.py`; a repository
  copying the scripts edits that constant.
- Also treated as required when the diff touches
  `projects/laundrybench/frontend/**` or `projects/laundrybench/e2e/**`:
  `browser` (workflow `Browser acceptance`). Otherwise `browser` and
  `Optional LeRobot ACT CPU compatibility` are informational: merge-ready
  tolerates `UNSTABLE` from them.
- One **CI wait** observation; `scripts/verify_candidate.py` wraps
  `scripts/watch_pr_checks.py`:
  ```bash
  export GH_TOKEN="$(gh auth token --user chungtseng96)"
  ERR="${TMPDIR:-/tmp}/ci-stderr-$N.txt"
  .venv/bin/python scripts/verify_candidate.py --wait-for-ci --exit-on-ci --ci-timeout-seconds 540 --timeout-seconds 30 --repo $REPO --pr $N --head-sha $SHA --base $BASE 2>"$ERR"
  ```

## Goldens

- **Suite:** an `R` ticket's goldens are the suite the ticket names. The
  two this repository can offer: `make demo` (the mock evaluation summary
  it prints) and `make web-demo` (the reproducible mock UI dataset under
  `projects/laundrybench/outputs/`, compared with `diff -r` against a run
  at `origin/$BASE`, ignoring timestamp fields). No suite named: record
  the goldens under **Not verified**.
- **PR label:** none; no golden workflow runs on a label here.
- **Result:** the before-run output recorded at implement equals the
  output at `SHA`, byte for byte after the timestamp filter the ticket
  names. It must hold at the final head, including after a babysit push.

## Reviews

No review bot is installed on this repository. The reviewer is a
**fresh-context subagent** this run dispatches (the Agent tool, a
general-purpose agent), which never sees the run's conversation.

- **Brief:** [`skills/factory/reviewer.md`](../../skills/factory/reviewer.md),
  plus the ticket id, the verbatim acceptance criteria and Constraints from
  the state record, `BASE`, `SHA`, `N`, the worktree path, and the first
  line "no `git switch`, `checkout`, `worktree`, `commit` or `push`".
- **Posts:** one PR review at `SHA`
  (`gh pr review $N --repo $REPO --comment --body-file <file>`) whose first
  line is the verdict marker
  `**Factory review** · head <full SHA> · verdict: <approve | send back>`,
  followed by findings as `- [blocking] <file>:<line> <claim>` or
  `- [nit] <file>:<line> <claim>`. The subagent reports the same text back
  to the run.
- **Blocking findings:** every `[blocking]` line of a `send back` verdict;
  `[nit]` lines are answered but never block.
- **Verdict query** (the latest review at a head):
  ```bash
  export GH_TOKEN="$(gh auth token --user chungtseng96)"
  gh api repos/$REPO/pulls/$N/reviews --paginate --jq '[.[] | select(.body | startswith("**Factory review**"))] | map(select(.commit_id=="'"$SHA"'")) | last | "\(.id) \(.commit_id) \(.body | split("\n")[0])"'
  ```
- **Bounded watch:** the reviewer runs inside the session, so there is
  nothing to wait on; if the subagent returns without a posted review,
  request it once more, then stop `blocked` ("review not posted at <sha>").
- **Rounds:** as the router says, three; the first review is requested by
  verify at PR creation.

## Impact

- **Risk surface:** the contracts other work depends on: the outcome and
  metrics contract (`evaluation/outcomes.py`, `metrics.py`,
  `outcome-contract.md`), the results API and UI schema (`web/`,
  `frontend/src/api.ts`), the recording, training and rollout manifests and
  config schemas (`data/recording.py`, `training/`, `policies/act.py`,
  `configs/*.yaml`), and the experiment record format. A change to them
  says in verify's ledger and the packet's Could break which physical or
  recorded artifacts stop loading.
- **Human calls:** a task definition, success judge, evaluation protocol,
  hardware limit, dependency addition, or anything that needs the arm is a
  needs-human entry, never the run's decision.

## Conventions

- **Plan:** a change that crosses two or more boundaries, changes a schema
  or manifest, or alters an evaluation protocol gets a plan at
  `projects/laundrybench/docs/plans/YYYY-MM-DD-<ticket>-<slug>.md`
  ([template](../templates/plan.md)) with its acceptance matrix; the plan
  file is in scope even when Files omits it.
- **Experiment record:** a meaningful model, data, hardware or configuration
  change gets a record under `projects/laundrybench/experiments/`
  ([template](../templates/experiment.md)), per `AGENTS.md`.
- **Docs-only diff:** every changed path is `*.md`, or under `docs/`,
  `projects/laundrybench/docs/` or `skills/`.
- **Recurring dismissals** belong in
  [`skills/factory/reviewer.md`](../../skills/factory/reviewer.md) through
  the [bounce log](factory-bounces.md).
- **Merge:** a human merges by hand after reading the packet. There is no
  merger label or skill.

## PR body

Fill [`.github/pull_request_template.md`](../../.github/pull_request_template.md):
- **Change and acceptance:** the Linear link and the acceptance criteria
  verbatim, with each marked done (mock), not done, or operator-run.
- **Evidence:** the pre-push gate commands with the head SHA, the CI line
  (`pending for <SHA>` at open, the `verdict` and run link after the CI
  wait), **Not verified** items including every operator-run criterion,
  and the words "mock" or "physical" on every result.
- **Review and ownership:** the agent's scope (the factory run), the
  independent review performed (the reviewer subagent, rounds, findings
  fixed and dismissed), and the human decisions left open (the needs-human
  list).
- **Factory run** note, at the end, each line naming the SHA it was
  produced at: Phases (each with its head), Review (rounds; fixed,
  dismissed, escalated), Synced (`main` or a parent merged in, and when),
  Weakest point (the packet's sentence), Packet (link to the **Proof of
  done** comment), Needs human (the list, or none), and a link to the
  ticket's **Factory state** comment.

## Linear

All through `scripts/factory_linear.py`, which reads the key from
`LINEAR_API_KEY` or `~/.config/linear/embodied-ai-lab.key` and never prints
it. The `mcp__claude_ai_Linear__*` connector is a different workspace and
is never used for this repository.
```bash
python3 scripts/factory_linear.py issue $T                       # ticket, comments, labels, blockedBy, blocks, factoryState
python3 scripts/factory_linear.py set-label $T working           # ready | working | needs-human | human-ready
python3 scripts/factory_linear.py upsert-comment $T --marker "**Factory state**" --body-file record.md
python3 scripts/factory_linear.py upsert-comment $T --marker "**Proof of done**" --body-file packet.md
python3 scripts/factory_linear.py working $T                     # watchdog: the project's working tickets and heartbeats
python3 scripts/factory_linear.py children $T                    # cascade: blockedBy children, onlyParent, factoryLabel
```

## Base

The router's **Base** rule as a script (tests: `make factory-test`):
```bash
export GH_TOKEN="$(gh auth token --user chungtseng96)"
.venv/bin/python scripts/factory_base.py --repo $REPO --branch $BRANCH --base $BASE --parent-branch <parent branch> --parent-head <recorded parent head> --pr $N   # omit --pr with PR: none
```
