"""Renders a ScoreResult (and optional AI narrative) as a Markdown report."""

from __future__ import annotations

from risklens.dashboard import ExecutiveView, enrich_executive_view
from risklens.models import ScoreResult
from risklens.scoring import tier_for_score


def render(
    result: ScoreResult,
    ai_narrative: dict | None = None,
    executive_view: ExecutiveView | None = None,
) -> str:
    lines: list[str] = []
    a = result.assessment

    lines.append(f"# RiskLens Security Readiness Report: {a.org_name}")
    lines.append("")
    lines.append(f"**Date:** {a.date or 'n/a'}  ")
    lines.append(f"**Framework:** {result.framework.name}  ")
    lines.append(f"**Overall Score:** {result.overall_score:.2f} / 4.0 ({result.tier})")
    lines.append("")

    if executive_view is not None:
        view = enrich_executive_view(executive_view, ai_narrative)
        lines.append("## Executive Risk Dashboard")
        lines.append("")
        if view.risks:
            lines.append(
                "| # | Risk | Business impact | Suggested owner "
                "| Recommended action | Residual risk |"
            )
            lines.append("|---|---|---|---|---|---|")
            for risk in view.risks:
                lines.append(
                    f"| {risk.rank} | {risk.title} | {risk.business_impact} "
                    f"| {risk.suggested_owner} | {risk.recommended_action} "
                    f"| {risk.residual_band} |"
                )
        else:
            lines.append("No findings below the configured threshold.")
        lines.append("")

    lines.append("## Function Scores")
    lines.append("")
    lines.append("| Function | Score | Tier |")
    lines.append("|---|---|---|")
    for fs in result.function_scores:
        lines.append(f"| {fs.function.name} | {fs.score:.2f} | {tier_for_score(fs.score)} |")
    lines.append("")

    lines.append("## Findings (prioritized)")
    lines.append("")
    if result.findings:
        lines.append("| # | Question | Function / Category | Score | Weight |")
        lines.append("|---|---|---|---|---|")
        for i, finding in enumerate(result.findings, start=1):
            lines.append(
                f"| {i} | {finding.question.text} "
                f"| {finding.function.name} / {finding.category.name} "
                f"| {finding.score:.0f}/4 | {finding.question.weight:.1f} |"
            )
    else:
        lines.append("No findings below the configured threshold.")
    lines.append("")

    if ai_narrative:
        lines.append("## Executive Summary")
        lines.append("")
        lines.append(ai_narrative.get("executive_summary", "").strip())
        lines.append("")

        lines.append("## Remediation Plan")
        lines.append("")
        for i, item in enumerate(ai_narrative.get("remediation_plan", []), start=1):
            lines.append(f"{i}. **{item.get('title', '')}**: {item.get('rationale', '')}")
            next_step = item.get("next_step")
            if next_step:
                lines.append(f"   - Next step: {next_step}")
        lines.append("")

        risk_register = ai_narrative.get("risk_register", [])
        if risk_register:
            lines.append("## Risk Register")
            lines.append("")
            lines.append("| Risk | Likelihood | Impact | Suggested Owner |")
            lines.append("|---|---|---|---|")
            for row in risk_register:
                lines.append(
                    f"| {row.get('risk', '')} | {row.get('likelihood', '')} "
                    f"| {row.get('impact', '')} | {row.get('owner', 'TBD')} |"
                )
            lines.append("")

    return "\n".join(lines)
