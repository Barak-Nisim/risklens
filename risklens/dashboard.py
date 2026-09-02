"""Deterministic executive risk dashboard.

Consumes an already-computed ScoreResult plus the already-loaded risk
acceptance decisions and produces a leadership-facing "Top N risks" view:
business impact, suggested owner, recommended action, and residual risk. This
module never re-scores and never calls the network -- like simulate.py it is a
pure transformation over the dataclasses in models.py, unit-tested in isolation.

Residual risk here is a *label* derived from the finding's inherent severity
band plus any recorded decision, never a recomputed number out of scoring.py.
Keeping that line bright is the whole point: the deterministic engine owns the
math, this module only classifies and presents its output for executives.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from risklens.decisions import Decision
from risklens.models import Finding, ScoreResult

# Ordered weakest -> strongest so a one-level "step down" is a simple index shift.
_BAND_ORDER = ("Low", "Medium", "High")


@dataclass(frozen=True)
class ExecutiveRisk:
    rank: int
    question_id: str
    title: str
    function_name: str
    category_name: str
    inherent_priority: float
    severity_band: str  # High / Medium / Low
    business_impact: str
    suggested_owner: str
    recommended_action: str
    decision_status: str | None
    residual_band: str


@dataclass(frozen=True)
class ExecutiveView:
    overall_score: float
    tier: str
    risks: tuple[ExecutiveRisk, ...]
    top_n: int


def severity_band(rank: int, total: int) -> str:
    """Rank-based band, top third = High, matching report/jira_csv.py::priority_tier
    so the dashboard and the Jira export tell the same story about the same rows."""
    if total <= 1:
        return "High"
    position = rank / (total - 1)  # 0.0 (first) .. 1.0 (last)
    if position <= 1 / 3:
        return "High"
    if position <= 2 / 3:
        return "Medium"
    return "Low"


def _step_down(band: str) -> str:
    index = _BAND_ORDER.index(band)
    return _BAND_ORDER[max(0, index - 1)]


def residual_band(inherent_band: str, decision_status: str | None) -> str:
    """Presentation-layer classification of inherent band + recorded decision.

    This is deliberately NOT a score recomputation: no decision or a deferred
    one leaves residual at the inherent band; accepting retains the risk (a
    labeled "Accepted (retained)"); mitigating or transferring steps the band
    down one level. The scoring math in scoring.py is untouched.
    """
    if decision_status == "accepted":
        return "Accepted (retained)"
    if decision_status in ("mitigated", "transferred"):
        return _step_down(inherent_band)
    # None (no decision) or "deferred": inherent band stands.
    return inherent_band


def _default_recommended_action(finding: Finding) -> str:
    return (
        f"Raise {finding.category.name} maturity from {finding.score:.0f}/4 "
        "toward a documented, measured practice."
    )


def build_executive_view(
    result: ScoreResult, decisions: dict[str, Decision], top_n: int = 5
) -> ExecutiveView:
    total = len(result.findings)
    risks: list[ExecutiveRisk] = []

    for rank, finding in enumerate(result.findings[:top_n]):
        band = severity_band(rank, total)
        decision = decisions.get(finding.question.id)
        status = decision.status if decision else None
        impact = finding.category.business_impact or "Not specified for this category"
        owner = finding.category.suggested_owner or "Unassigned"

        risks.append(
            ExecutiveRisk(
                rank=rank + 1,
                question_id=finding.question.id,
                title=finding.question.text,
                function_name=finding.function.name,
                category_name=finding.category.name,
                inherent_priority=finding.priority,
                severity_band=band,
                business_impact=impact,
                suggested_owner=owner,
                recommended_action=_default_recommended_action(finding),
                decision_status=status,
                residual_band=residual_band(band, status),
            )
        )

    return ExecutiveView(
        overall_score=result.overall_score,
        tier=result.tier,
        risks=tuple(risks),
        top_n=top_n,
    )


def enrich_executive_view(view: ExecutiveView, ai_narrative: dict | None) -> ExecutiveView:
    """Overlays optional AI prose onto the two enrichable columns only.

    Row selection, ordering, severity bands, and residual bands stay exactly as
    the deterministic build produced them; the AI supplies nicer phrasing for
    business impact and recommended action, keyed by question id, behind a
    deterministic fallback. If the narrative is absent or a row has no matching
    id, the deterministic defaults are kept.
    """
    if not ai_narrative:
        return view

    next_step_by_id = {
        item["question_id"]: item["next_step"]
        for item in ai_narrative.get("remediation_plan", [])
        if item.get("question_id") and item.get("next_step")
    }
    impact_by_id = {
        row["question_id"]: row["impact"]
        for row in ai_narrative.get("risk_register", [])
        if row.get("question_id") and row.get("impact")
    }

    enriched: list[ExecutiveRisk] = []
    for risk in view.risks:
        enriched.append(
            replace(
                risk,
                recommended_action=next_step_by_id.get(risk.question_id, risk.recommended_action),
                business_impact=impact_by_id.get(risk.question_id, risk.business_impact),
            )
        )

    return replace(view, risks=tuple(enriched))
