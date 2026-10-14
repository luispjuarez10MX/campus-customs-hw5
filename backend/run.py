"""Run the agent team from the command line.

    .venv/bin/python -m backend.run --reset
    .venv/bin/python -m backend.run --task "Only look at ticket 102."
"""

import argparse
import asyncio

from backend.agents import DEFAULT_TASK, run_team


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Campus Customs agent team.")
    parser.add_argument("--task", default=DEFAULT_TASK, help="Instruction for the Boss.")
    parser.add_argument("--reset", action="store_true", help="Reset the working DB from the original first.")
    args = parser.parse_args()
    report = asyncio.run(run_team(args.task, reset=args.reset))
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
