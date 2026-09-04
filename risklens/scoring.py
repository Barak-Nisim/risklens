"""Pure scoring engine: framework + assessment -> ScoreResult.

No I/O, no network calls. Every function here is a plain transformation over
the dataclasses in models.py, which is what makes the scoring logic fully
unit-testable and explainable independent of the AI narrator layer.

Scoring model:
- Each question is answered on a 0-4 maturity scale.
- An unanswered question is scored 0 (missing evidence of a control is
  treated as the worst case, not skipped -- silently excluding unanswered
  questions would let an org "hide" gaps by leaving them blank).
- Category score = weighted average of its questions' scores.
- Function score = weighted average of its categories' scores.
- Overall score = weighted average of the six functions' scores.
- A question scoring below `finding_threshold` becomes a Finding.
- Findings are ranked by priority = question.weight * (MAX_SCORE - score),
  so high-weight, low-maturity gaps surface first.
"""

from __future__ import annotations

from risklens.models import (
    DEFAULT_FINDING_THRESHOLD,
    MATURITY_LEVELS,
    Answer,
    Assessment,
    CategoryScore,
    Finding,
    Framework,
    FunctionScore,
    QuestionScore,
    ScoreResult,
)

MAX_SCORE = 4.0

TIER_BOUNDARIES = (
    (0.8, "Initial"),
    (1.6, "Developing"),
    (2.4, "Defined"),
    (3.2, "Managed"),
    (float("inf"), "Optimized"),
)


def tier_for_score(score: float) -> str:
    for boundary, tier in TIER_BOUNDARIES:
        if score < boundary:
            return tier
    return "Optimized"


# The four presets app_form.html's dropdown offers, each with a plain-English
# intensity name; the CLI's --threshold accepts any float, so a value outside
# this set gets a generic "Custom" label rather than a guessed nearest match.
_SENSITIVITY_NAMES = {1.0: "Lenient", 2.0: "Standard", 3.0: "Strict", 4.0: "Very strict"}


def finding_sensitivity_label(threshold: float) -> str:
    """Human label for a finding_threshold value, e.g. 'Standard (below
    "Defined")' -- built from MATURITY_LEVELS so it can't drift from the
    labels shown on each answered question."""
    name = _SENSITIVITY_NAMES.get(threshold, "Custom")
    if 0 < threshold <= MAX_SCORE:
        return f'{name} (below "{MATURITY_LEVELS[int(threshold)]}")'
    return f"{name} ({threshold:.1f})"


def _weighted_average(scored_weights: list[tuple[float, float]]) -> float:
    total_weight = sum(weight for _, weight in scored_weights)
    if total_weight == 0:
        return 0.0
    return sum(score * weight for score, weight in scored_weights) / total_weight


def score_assessment(
    framework: Framework,
    assessment: Assessment,
    finding_threshold: float = DEFAULT_FINDING_THRESHOLD,
) -> ScoreResult:
    function_scores: list[FunctionScore] = []
    findings: list[Finding] = []

    for function in framework.functions:
        category_scores: list[CategoryScore] = []

        for category in function.categories:
            question_scores: list[QuestionScore] = []

            for question in category.questions:
                answer: Answer | None = assessment.answers.get(question.id)
                score = float(answer.score) if answer is not None else 0.0
                question_scores.append(
                    QuestionScore(question=question, answer=answer, score=score)
                )

                if score < finding_threshold:
                    priority = question.weight * (MAX_SCORE - score)
                    findings.append(
                        Finding(
                            question=question,
                            category=category,
                            function=function,
                            score=score,
                            priority=priority,
                        )
                    )

            category_score = _weighted_average(
                [(qs.score, qs.question.weight) for qs in question_scores]
            )
            category_scores.append(
                CategoryScore(
                    category=category,
                    score=category_score,
                    question_scores=tuple(question_scores),
                )
            )

        function_score = _weighted_average(
            [(cs.score, cs.category.weight) for cs in category_scores]
        )
        function_scores.append(
            FunctionScore(
                function=function,
                score=function_score,
                category_scores=tuple(category_scores),
            )
        )

    overall_score = _weighted_average(
        [(fs.score, fs.function.weight) for fs in function_scores]
    )
    findings.sort(key=lambda f: f.priority, reverse=True)

    return ScoreResult(
        assessment=assessment,
        framework=framework,
        overall_score=overall_score,
        tier=tier_for_score(overall_score),
        function_scores=tuple(function_scores),
        findings=tuple(findings),
    )
