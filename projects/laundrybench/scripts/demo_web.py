"""Generate explicitly synthetic UI examples through the real mock runner."""
from __future__ import annotations

import argparse
import platform
from datetime import UTC, datetime
from pathlib import Path

import yaml

from laundrybench.evaluation.experiment import run_experiment
from laundrybench.evaluation.judge import MockSuccessJudge
from laundrybench.observability.manifest import RunManifest, config_hash, git_revision
from laundrybench.policies.mock import MockPolicy
from laundrybench.robot.mock import MockRobot


class DemoClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class DemoRobot(MockRobot):
    def __init__(self, clock: DemoClock) -> None:
        super().__init__()
        self.clock = clock

    def observe(self):
        observation = super().observe()
        observation.timestamp_s = self.clock()
        return observation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    for number, name, probability in ((900, "mock-baseline", .2), (901, "mock-candidate", .8)):
        experiment_id = f"exp-{number}-{name}"
        target = args.output_dir / experiment_id
        if target.exists():
            print(f"preserved existing {target} (including any manual labels)")
            continue
        clock = DemoClock()
        manifest = RunManifest(
            experiment_id, datetime.now(UTC).isoformat(), git_revision(project),
            config_hash(project / "configs"), 17, "mock-policy", "mock",
            platform.python_version(), None,
        )
        run_experiment(
            target, manifest, robot=DemoRobot(clock), policy=MockPolicy(),
            judge=MockSuccessJudge(seed=17, success_probability=probability),
            episodes=12, control_hz=20, timeout_s=.3, clock=clock, sleep=clock.sleep,
        )
        manifest_path = target / "manifest.yaml"
        provenance = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        provenance.update(
            execution_mode="synthetic",
            accelerated_clock=True,
            config_hash_scope="checked-in YAML; demo_parameters override runner settings",
            demo_parameters={
                "episodes": 12, "control_hz": 20, "timeout_s": .3,
                "judge_probability": probability, "success_after_steps": 4,
            },
        )
        manifest_path.write_text(yaml.safe_dump(provenance, sort_keys=True), encoding="utf-8")
        print(f"created {target}: MOCK outcomes, accelerated clock, no hardware or training")


if __name__ == "__main__":
    main()
