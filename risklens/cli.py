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
    assess.add_argument(
        "--simulate",
        metavar="QUESTION_IDS",
        default=None,
        help="Comma-separated question ids to hypothetically improve and show the effect"
        " (e.g. pr-02,gv-04)",
    )
    assess.add_argument(
        "--simulate-target",
        type=int,
        default=4,
        metavar="SCORE",
        help="Hypothetical score to simulate for --simulate question ids (default: 4)",
    )

    serve = subparsers.add_parser("serve", help="Run the RiskLens web UI locally")
    serve.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    serve.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    serve.add_argument("--reload", action="store_true", help="Auto-reload on code changes")

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

    if args.simulate:
        from risklens.simulate import render_simulation, simulate_improvement

        question_ids = [q.strip() for q in args.simulate.split(",") if q.strip()]
        sim = simulate_improvement(
            framework,
            assessment,
            question_ids,
            target_score=args.simulate_target,
            finding_threshold=args.threshold,
        )
        print("\n" + render_simulation(sim))

    return 0


def _run_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("risklens.web.app:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "assess":
        return _run_assess(args)
    if args.command == "serve":
        return _run_serve(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
