"""Run a finite, supervised LeRobot ACT rollout into LaundryBench evidence."""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import shutil
import signal
from pathlib import Path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="explicit rollout YAML config")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="connect to the configured physical SO-101 follower and run the bounded policy",
    )
    parser.add_argument(
        "--supervised",
        action="store_true",
        help=(
            "confirm an operator is present with clear workspace and immediate physical stop access"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    # Delay project and optional model imports until after argparse can service --help.
    from laundrybench.evaluation.physical import load_rollout_config
    from laundrybench.policies.act import LeRobotACTPolicy, load_act_contract

    config_path = args.config.expanduser().resolve()
    config = load_rollout_config(config_path)
    checkpoint_path = _resolve(config_path.parent, config["checkpoint"]["path"])
    contract_path = _resolve(config_path.parent, config["checkpoint"]["contract_path"])
    output_dir = _resolve(config_path.parent, config["output_dir"])
    if output_dir.exists():
        raise SystemExit(f"refusing to overwrite existing rollout directory: {output_dir}")

    if not args.execute:
        # This validates the checkpoint/contract without importing PyTorch, LeRobot, or hardware.
        contract = load_act_contract(contract_path, checkpoint_path)
        _verify_config_contract(config, contract)
        print(
            json.dumps(
                {
                    "mode": "dry-run",
                    "execute": False,
                    "hardware_connected": False,
                    "checkpoint": str(checkpoint_path),
                    "experiment_id": config["experiment_id"],
                    "episodes": config["runtime"]["episodes"],
                    "timeout_s": config["runtime"]["timeout_s"],
                    "control_hz": config["runtime"]["control_hz"],
                    "max_relative_target": config["runtime"]["max_relative_target"],
                    "camera_names": sorted(config["cameras"]),
                },
                indent=2,
            )
        )
        return 0
    if not args.supervised:
        raise SystemExit("--execute requires --supervised; no robot has been connected")
    if shutil.which("ffmpeg") is None:
        raise SystemExit(
            "ffmpeg is required for physical camera evidence; no robot has been connected"
        )
    if importlib.util.find_spec("numpy") is None:
        raise SystemExit(
            "numpy is required for physical camera evidence; no robot has been connected"
        )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    if not output_dir.parent.is_dir():
        raise SystemExit(f"rollout output parent is not a directory: {output_dir.parent}")

    # Complete cheap compatibility and output checks before importing model/device stacks.
    contract = load_act_contract(contract_path, checkpoint_path)
    _verify_config_contract(config, contract)
    try:
        installed_version = importlib.metadata.version("lerobot")
    except importlib.metadata.PackageNotFoundError as error:
        raise SystemExit("LeRobot 0.6.1 is required in the selected environment") from error
    if installed_version != "0.6.1":
        raise SystemExit(f"LeRobot 0.6.1 is required; found {installed_version}")

    from laundrybench.evaluation.physical import run_physical_experiment
    from laundrybench.robot.so101 import CameraSettings, create_so101_robot

    runtime = config["runtime"]
    policy = LeRobotACTPolicy(
        checkpoint_path,
        contract_path,
        device=runtime["device"],
        expected_task=config["task"]["id"],
        expected_protocol=config["protocol"]["id"],
        expected_dataset_id=config["dataset"]["id"],
        expected_dataset_revision=config["dataset"]["revision"],
    )
    cameras = {name: CameraSettings(**settings) for name, settings in config["cameras"].items()}
    previous_sigterm = signal.getsignal(signal.SIGTERM)

    def stop_on_sigterm(signum, frame):
        del signum, frame
        raise KeyboardInterrupt("received SIGTERM; stopping supervised rollout")

    signal.signal(signal.SIGTERM, stop_on_sigterm)
    robot = None
    try:
        robot = create_so101_robot(
            port=config["robot"]["port"],
            robot_id=config["robot"]["id"],
            cameras=cameras,
            max_relative_target=runtime["max_relative_target"],
        )
        results = run_physical_experiment(
            experiment_dir=output_dir,
            config_path=config_path,
            config=config,
            robot=robot,
            policy=policy,
            lerobot_version=installed_version,
        )
    finally:
        try:
            if robot is not None:
                robot.stop()
        finally:
            signal.signal(signal.SIGTERM, previous_sigterm)
    print(f"wrote {len(results)} provisional physical episodes to {output_dir}")
    print("Human outcome labels are required before this run contributes to reviewed metrics.")
    return 0


def _resolve(base: Path, raw: str) -> Path:
    path = Path(raw).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def _verify_config_contract(config: dict, contract: dict) -> None:
    expected = (
        ("task.id", config["task"]["id"], contract["task"]["id"]),
        ("task.version", config["task"]["version"], contract["task"]["version"]),
        ("protocol.id", config["protocol"]["id"], contract["protocol"]["id"]),
        ("protocol.version", config["protocol"]["version"], contract["protocol"]["version"]),
        ("dataset.id", config["dataset"]["id"], contract["dataset"]["repo_id"]),
        ("dataset.revision", config["dataset"]["revision"], contract["dataset"]["revision"]),
        ("dataset.fps", config["dataset"]["fps"], contract["dataset"]["fps"]),
        ("dataset/control fps", config["dataset"]["fps"], config["runtime"]["control_hz"]),
        ("camera keys", sorted(config["cameras"]), sorted(contract["cameras"])),
    )
    mismatches = [name for name, wanted, actual in expected if wanted != actual]
    if mismatches:
        raise SystemExit(f"rollout config does not match policy contract: {', '.join(mismatches)}")
    camera_mismatches = [
        name
        for name, camera in config["cameras"].items()
        if camera["width"] != contract["cameras"][name]["width"]
        or camera["height"] != contract["cameras"][name]["height"]
    ]
    if camera_mismatches:
        raise SystemExit(
            "rollout camera dimensions do not match checkpoint contract: "
            + ", ".join(sorted(camera_mismatches))
        )


if __name__ == "__main__":
    raise SystemExit(main())
