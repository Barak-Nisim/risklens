"""Prompt construction for the AI narrator.

The prompt hands the model a JSON payload derived entirely from the
deterministic ScoreResult -- scores, tiers, and findings -- and asks it to
narrate and prioritize that data. It is explicitly told not to recompute
scores or invent findings.
"""

from __future__ import annotations

import json

from risklens.models import ScoreResult

SYSTEM_PROMPT = (
    "You are a security governance advisor writing for company leadership. "
    "You are given the deterministic output of a security maturity scoring engine: "
    "an overall score, per-function scores, and a prioritized list of findings "
    "(gaps below a maturity threshold, ranked by weight times severity). "
    "Your job is to narrate and prioritize this data for a non-technical executive "
    "audience. Do not recompute or second-guess the scores or the finding "
    "priority order, and do not invent findings that are not in the input."
)


def build_findings_payload(result: ScoreResult) -> dict:
    return {
        "org_name": result.assessment.org_name,
        "overall_score": round(result.overall_score, 2),
        "tier": result.tier,
        "function_scores": [
            {"function": fs.function.name, "score": round(fs.score, 2)}
            for fs in result.function_scores
        ],
        "findings": [
            {
                "question_id": f.question.id,
                "question": f.question.text,
                "function": f.function.name,
                "category": f.category.name,
                "score": f.score,
                "weight": f.question.weight,
            }
            for f in result.findings
        ],
    }


def build_user_prompt(result: ScoreResult) -> str:
    payload = build_findings_payload(result)
    return (
        "Here is the scored assessment, as JSON:\n\n"
        f"{json.dumps(payload, indent=2)}\n\n"
        "Write:\n"
        "1. A short executive summary (around 150 words) in plain, leadership-facing language.\n"
        "2. A prioritized remediation plan, one entry per finding, in the order given, "
        "each with a short title, a one-sentence rationale, and a concrete next step. "
        "Include the exact question_id from the input on each entry so it can be matched "
        "back to its finding.\n"
        "3. A risk register: one row per finding, with a risk statement, likelihood, "
        "impact, and a suggested owner expressed as a role or team, not a person's name. "
        "Include the exact question_id from the input on each row."
    )
