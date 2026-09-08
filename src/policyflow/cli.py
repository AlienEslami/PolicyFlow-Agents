from __future__ import annotations

import argparse
import json
from pathlib import Path

from .app import build_local_service
from .evaluation import DeterministicJudge, TransformersJudge, evaluate, load_cases


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="policyflow")
    subcommands = parser.add_subparsers(dest="command", required=True)
    evaluation = subcommands.add_parser("evaluate", help="run the frozen evaluation suite")
    evaluation.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).resolve().parents[2]
        / "data"
        / "synthetic"
        / "evaluation_cases.json",
    )
    evaluation.add_argument(
        "--judge-backend", choices=("rules", "transformers"), default="rules"
    )
    evaluation.add_argument("--judge-model", default="google/flan-t5-small")
    args = parser.parse_args(argv)
    if args.command == "evaluate":
        judge = (
            TransformersJudge(args.judge_model)
            if args.judge_backend == "transformers"
            else DeterministicJudge()
        )
        report = evaluate(build_local_service(), load_cases(args.cases), judge)
        print(json.dumps(report.__dict__, indent=2, sort_keys=True))
        return 0 if report.status_accuracy == 1.0 and report.safety_pass_rate == 1.0 else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
