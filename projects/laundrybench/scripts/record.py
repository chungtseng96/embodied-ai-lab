"""Future entrypoint for recording SO-101 demonstrations.

V1 intentionally leaves hardware recording to the upcoming LeRobot integration.
This file exists so the CLI surface is stable before hardware arrives.
"""


def main() -> None:
    raise SystemExit(
        "Hardware recording is not wired yet. Integrate LeRobot after SO-101 bring-up."
    )


if __name__ == "__main__":
    main()
