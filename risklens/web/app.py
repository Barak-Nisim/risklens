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

from risklens.loader import dump_assessment, load_assessment, load_framework, parse_assessment
from risklens.models import Answer, Assessment
from risklens.report.jira_csv import FIELDNAMES as JIRA_FIELDNAMES
from risklens.report.jira_csv import build_rows as build_jira_rows
from risklens.scoring import DEFAULT_FINDING_THRESHOLD, score_assessment, tier_for_score

WEB_DIR = Path(__file__).parent
SAMPLE_ANSWERS_PATH = WEB_DIR.parent.parent / "examples" / "sample_answers.yaml"

app = FastAPI(title="RiskLens")
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")


def _sample_prefill() -> dict:
    if SAMPLE_ANSWERS_PATH.exists():
        sample = load_assessment(SAMPLE_ANSWERS_PATH)
        return {
            "org_name": sample.org_name,
            "date": sample.date,
            "answers": sample.answers,
        }
    return {"org_name": "", "date": "", "answers": {}}


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
    framework = load_framework("nist_csf")
    prefill = _sample_prefill()
    # rubric is identical across every question (shared via a YAML anchor in
    # nist_csf.yaml), so any one question's rubric works as the legend
    legend = framework.functions[0].categories[0].questions[0].rubric

    return templates.TemplateResponse(
        request,
        "app_form.html",
        {
            "framework": framework,
            "legend": legend,
            "org_name": prefill["org_name"],
            "date": prefill["date"],
            "prefill_answers": prefill["answers"],
            "ai_available": _ai_available(),
            "error": None,
        },
    )


@app.post("/assess", response_class=HTMLResponse)
async def assess(request: Request):
    form = await request.form()
    framework = load_framework("nist_csf")

    answers = {}
    for question in framework.all_questions():
        raw_score = form.get(f"q_{question.id}")
        if raw_score in (None, ""):
            continue
        notes = form.get(f"notes_{question.id}") or None
        answers[question.id] = Answer(question_id=question.id, score=int(raw_score), notes=notes)

    assessment = Assessment(
        org_name=str(form.get("org_name") or "Untitled Organization"),
        date=str(form.get("date") or ""),
        framework_id="nist_csf",
        answers=answers,
    )
    result = score_assessment(framework, assessment, finding_threshold=DEFAULT_FINDING_THRESHOLD)
    answers_yaml = dump_assessment(assessment)

    ai_narrative = None
    if form.get("use_ai") and _ai_available():
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
