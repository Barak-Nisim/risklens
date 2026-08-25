"""What-if scenario simulation: shows the effect of hypothetically improving
specific answers (e.g. "what if we implemented MFA?"), by calling
score_assessment() twice, once for the real assessment and once for a copy
with the chosen questions bumped to a target score. scoring.py itself is
never modified or duplicated; this module only orchestrates two calls to it
and diffs the results.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from risklens.models import Answer, Assessment, Framework, ScoreResult
from risklens.scoring import DEFAULT_FINDING_THRESHOLD, score_assessment


@dataclass(frozen=True)
class SimulationResult:
    baseline: ScoreResult
    hypothetical: ScoreResult
    question_ids: tuple[str, ...]
    target_score: int
    overall_score_delta: float
    resolved_finding_ids: tuple[str, ...]  # findings in baseline, cleared in the hypothetical
    remaining_finding_ids: tuple[str, ...]  # findings present in both


def simulate_improvement(
    framework: Framework,
    assessment: Assessment,
    question_ids: list[str],
    target_score: int = 4,
    finding_threshold: float = DEFAULT_FINDING_THRESHOLD,
) -> SimulationResult:
    baseline = score_assessment(framework, assessment, finding_threshold=finding_threshold)

    new_answers = dict(assessment.answers)
    for question_id in question_ids:
        existing = new_answers.get(question_id)
        notes = existing.notes if existing else None
        new_answers[question_id] = Answer(question_id=question_id, score=target_score, notes=notes)
    hypothetical_assessment = replace(assessment, answers=new_answers)

    hypothetical = score_assessment(
        framework, hypothetical_assessment, finding_threshold=finding_threshold
    )

    baseline_finding_ids = {f.question.id for f in baseline.findings}
    hypothetical_finding_ids = {f.question.id for f in hypothetical.findings}

    return SimulationResult(
        baseline=baseline,
        hypothetical=hypothetical,
        question_ids=tuple(question_ids),
        target_score=target_score,
        overall_score_delta=round(hypothetical.overall_score - baseline.overall_score, 2),
        resolved_finding_ids=tuple(sorted(baseline_finding_ids - hypothetical_finding_ids)),
        remaining_finding_ids=tuple(sorted(baseline_finding_ids & hypothetical_finding_ids)),
    )


def render_simulation(sim: SimulationResult) -> str:
    lines = [
        "# What-If Simulation",
        "",
        f"**Questions improved to {sim.target_score}/4:** {', '.join(sim.question_ids)}",
        f"**Overall score:** {sim.baseline.overall_score:.2f} ({sim.baseline.tier}) -> "
        f"{sim.hypothetical.overall_score:.2f} ({sim.hypothetical.tier}) "
        f"({sim.overall_score_delta:+.2f})",
        "",
    ]

    if sim.resolved_finding_ids:
        lines.append(f"**Findings resolved:** {len(sim.resolved_finding_ids)}")
        for question_id in sim.resolved_finding_ids:
            question = sim.baseline.framework.question_by_id(question_id)
            lines.append(f"- {question.text if question else question_id}")
    else:
        lines.append("**Findings resolved:** none")

    if sim.remaining_finding_ids:
        lines.append(f"\n**Findings still open:** {len(sim.remaining_finding_ids)}")

    return "\n".join(lines)
