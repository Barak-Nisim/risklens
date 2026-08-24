"""RiskLens CLI: risklens assess <answers.yaml> [options]"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from risklens.loader import load_assessment, load_framework
from risklens.report.markdown import render
from risklens.scoring import DEFAULT_FINDING_THRESHOLD, score_assessment


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="risklens")
    subparsers = parser.add_subparsers(dest="command", required=True)

    assess = subparsers.add_parser("assess", help="Run a security readiness assessment")
    assess.add_argument("answers", help="Path to a filled-out answers YAML file")
    assess.add_argument(
        "--framework",
        default=None,
        help="Framework id or path to a framework YAML (default: from the answers file)",
    )
    assess.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_FINDING_THRESHOLD,
        help=f"Score below which a question is a finding (default: {DEFAULT_FINDING_THRESHOLD})",
    )
    assess.add_argument(
        "--no-ai",
        action="store_true",
        help="Skip the AI narrator and render the deterministic report only",
    )
    assess.add_argument(
        "--jira-export",
        metavar="PATH",
        help="Also export the prioritized remediation backlog as a Jira-importable CSV",
    )
    assess.add_argument(
        "--output",
        "-o",
        metavar="PATH",
        help="Write the report to a file instead of stdout",
    )

    return parser


def _run_assess(args: argparse.Namespace) -> int:
    assessment = load_assessment(args.answers)
    framework = load_framework(args.framework or assessment.framework_id)
    result = score_assessment(framework, assessment, finding_threshold=args.threshold)

    ai_narrative = None
    if not args.no_ai:
        from risklens.ai.narrator import generate_narrative

        ai_narrative = generate_narrative(result)

    report = render(result, ai_narrative=ai_narrative)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(report)

    if args.jira_export:
        from risklens.report.jira_csv import write_jira_csv

        write_jira_csv(result, args.jira_export)
        print(f"Jira CSV written to {args.jira_export}", file=sys.stderr)

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "assess":
        return _run_assess(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
