"""Calls the Claude API to narrate a ScoreResult into an executive summary,
remediation plan, and risk register.

This module never recomputes or overrides scores -- it only narrates the
deterministic output of risklens.scoring. Requires ANTHROPIC_API_KEY to be
set (see .env.example); not exercised by the test suite or CI, which run
with mocked responses.
"""

from __future__ import annotations

import json

import anthropic
from dotenv import load_dotenv

from risklens.ai.prompts import SYSTEM_PROMPT, build_user_prompt
from risklens.models import ScoreResult

MODEL = "claude-opus-4-8"

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "executive_summary": {"type": "string"},
        "remediation_plan": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question_id": {"type": "string"},
                    "title": {"type": "string"},
                    "rationale": {"type": "string"},
                    "next_step": {"type": "string"},
                },
                "required": ["question_id", "title", "rationale", "next_step"],
                "additionalProperties": False,
            },
        },
        "risk_register": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question_id": {"type": "string"},
                    "risk": {"type": "string"},
                    "likelihood": {"type": "string"},
                    "impact": {"type": "string"},
                    "owner": {"type": "string"},
                },
                "required": ["question_id", "risk", "likelihood", "impact", "owner"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["executive_summary", "remediation_plan", "risk_register"],
    "additionalProperties": False,
}


def generate_narrative(result: ScoreResult) -> dict:
    load_dotenv()
    client = anthropic.Anthropic()

    response = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(result)}],
        output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
    )

    text = next(block.text for block in response.content if block.type == "text")
    return json.loads(text)
