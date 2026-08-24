"""FastAPI web UI for RiskLens.

Thin wrapper around the same loader/scoring/report modules the CLI uses --
no scoring or narration logic lives here. Run locally with `risklens serve`.
"""

from __future__ import annotations

import csv
import io
import os
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from risklens.loader import load_framework, parse_assessment
from risklens.report.jira_csv import FIELDNAMES as JIRA_FIELDNAMES
from risklens.report.jira_csv import build_rows as build_jira_rows
from risklens.scoring import DEFAULT_FINDING_THRESHOLD, score_assessment, tier_for_score

WEB_DIR = Path(__file__).parent
SAMPLE_ANSWERS_PATH = WEB_DIR.parent.parent / "examples" / "sample_answers.yaml"

app = FastAPI(title="RiskLens")
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")


def _sample_yaml() -> str:
    if SAMPLE_ANSWERS_PATH.exists():
        return SAMPLE_ANSWERS_PATH.read_text(encoding="utf-8")
    return "org_name: Your Organization\ndate: \"2026-01-01\"\nframework: nist_csf\nanswers: {}\n"


def _ai_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse(request, "landing.html", {})


@app.get("/how-it-works", response_class=HTMLResponse)
def how_it_works(request: Request):
    return templates.TemplateResponse(request, "how_it_works.html", {})


@app.get("/app", response_class=HTMLResponse)
def app_form(request: Request):
    return templates.TemplateResponse(
        request,
        "app_form.html",
        {
            "answers_yaml": _sample_yaml(),
            "ai_available": _ai_available(),
            "error": None,
        },
    )


@app.post("/assess", response_class=HTMLResponse)
def assess(request: Request, answers_yaml: str = Form(...), use_ai: str | None = Form(None)):
    try:
        assessment = parse_assessment(answers_yaml)
        framework = load_framework(assessment.framework_id)
        result = score_assessment(
            framework, assessment, finding_threshold=DEFAULT_FINDING_THRESHOLD
        )
    except Exception as exc:  # noqa: BLE001 -- surfaced to the user, not swallowed
        return templates.TemplateResponse(
            request,
            "app_form.html",
            {
                "answers_yaml": answers_yaml,
                "ai_available": _ai_available(),
                "error": f"Could not parse or score this assessment: {exc}",
            },
        )

    ai_narrative = None
    if use_ai and _ai_available():
        from risklens.ai.narrator import generate_narrative

        ai_narrative = generate_narrative(result)

    return templates.TemplateResponse(
        request,
        "report.html",
        {
            "result": result,
            "ai_narrative": ai_narrative,
            "tier_for_score": tier_for_score,
            "answers_yaml": answers_yaml,
        },
    )


@app.post("/jira-export")
def jira_export(answers_yaml: str = Form(...)):
    assessment = parse_assessment(answers_yaml)
    framework = load_framework(assessment.framework_id)
    result = score_assessment(framework, assessment, finding_threshold=DEFAULT_FINDING_THRESHOLD)

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=JIRA_FIELDNAMES)
    writer.writeheader()
    writer.writerows(build_jira_rows(result))
    buffer.seek(0)

    filename = f"risklens-backlog-{result.assessment.org_name.replace(' ', '_')}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
