"""RiskLens CLI: risklens assess <answers.yaml> [options]"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from risklens.dashboard import build_executive_view
from risklens.decisions import DECISION_STATUSES, clear_decision, load_decisions, record_decision
from risklens.history import record_snapshot, render_trend
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

    decisions = subparsers.add_parser("decisions", help="Manage risk acceptance decisions")
    decisions_action = decisions.add_subparsers(dest="decisions_action", required=True)

    list_parser = decisions_action.add_parser("list", help="List recorded decisions for an org")
    list_parser.add_argument("org_name")

    record_parser = decisions_action.add_parser("record", help="Record a decision for a finding")
    record_parser.add_argument("org_name")
    record_parser.add_argument("question_id")
    record_parser.add_argument("status", choices=sorted(DECISION_STATUSES))
    record_parser.add_argument("--rationale", default="", help="Why this disposition was chosen")

    clear_parser = decisions_action.add_parser("clear", help="Clear a recorded decision")
    clear_parser.add_argument("org_name")
    clear_parser.add_argument("question_id")

    return parser


def _run_assess(args: argparse.Namespace) -> int:
    assessment = load_assessment(args.answers)
    framework = load_framework(args.framework or assessment.framework_id)
    result = score_assessment(framework, assessment, finding_threshold=args.threshold)

    ai_narrative = None
    if not args.no_ai:
        from risklens.ai.narrator import generate_narrative

        ai_narrative = generate_narrative(result)

    history = record_snapshot(result)
    decisions = load_decisions(result.assessment.org_name)
    executive_view = build_executive_view(result, decisions)
    report = render(result, ai_narrative=ai_narrative, executive_view=executive_view)
    trend = render_trend(history)
    if trend:
        report += "\n\n" + trend

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


def _run_decisions(args: argparse.Namespace) -> int:
    if args.decisions_action == "list":
        decisions = load_decisions(args.org_name)
        if not decisions:
            print("No decisions recorded yet.", file=sys.stderr)
        else:
            for question_id, decision in decisions.items():
                line = f"{question_id}: {decision.status}"
                if decision.rationale:
                    line += f" -- {decision.rationale}"
                print(line)
    elif args.decisions_action == "record":
        record_decision(
            args.org_name,
            args.question_id,
            args.status,
            args.rationale,
            decided_at=dt.date.today().isoformat(),
        )
        print(f"Recorded '{args.status}' for {args.question_id}.", file=sys.stderr)
    elif args.decisions_action == "clear":
        clear_decision(args.org_name, args.question_id)
        print(f"Cleared decision for {args.question_id}.", file=sys.stderr)

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "assess":
        return _run_assess(args)
    if args.command == "serve":
        return _run_serve(args)
    if args.command == "decisions":
        return _run_decisions(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
