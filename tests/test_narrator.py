"""Tests for the AI narrator. The Claude API is always mocked here -- these
tests never make a network call and never require ANTHROPIC_API_KEY.
"""

import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from risklens.ai.narrator import generate_narrative
from risklens.loader import load_assessment, load_framework
from risklens.scoring import score_assessment

FAKE_NARRATIVE = {
    "executive_summary": "Overall posture is developing, with vendor and IR gaps.",
    "remediation_plan": [
        {
            "question_id": "id-01",
            "title": "Reassess existing vendors",
            "rationale": "Highest-priority gap by weight.",
            "next_step": "Schedule a Q3 vendor risk review.",
        }
    ],
    "risk_register": [
        {
            "question_id": "id-01",
            "risk": "Unreviewed vendors introduce unmanaged third-party risk",
            "likelihood": "Medium",
            "impact": "High",
            "owner": "Vendor Management",
        }
    ],
}


def _sample_result():
    framework = load_framework("nist_csf")
    assessment = load_assessment("examples/sample_answers.yaml")
    return score_assessment(framework, assessment)


def _mock_client_with_response(payload: dict) -> MagicMock:
    mock_client = MagicMock()
    mock_response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text=json.dumps(payload))]
    )
    mock_client.messages.create.return_value = mock_response
    return mock_client


@patch("risklens.ai.narrator.anthropic.Anthropic")
def test_generate_narrative_parses_mocked_response(mock_anthropic, monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_NARRATIVE_CACHE_DIR", str(tmp_path))
    mock_anthropic.return_value = _mock_client_with_response(FAKE_NARRATIVE)

    narrative = generate_narrative(_sample_result())

    assert narrative == FAKE_NARRATIVE
    mock_anthropic.return_value.messages.create.assert_called_once()


@patch("risklens.ai.narrator.anthropic.Anthropic")
def test_generate_narrative_uses_structured_output_schema(mock_anthropic, monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_NARRATIVE_CACHE_DIR", str(tmp_path))
    mock_anthropic.return_value = _mock_client_with_response(FAKE_NARRATIVE)

    generate_narrative(_sample_result())

    _, kwargs = mock_anthropic.return_value.messages.create.call_args
    assert kwargs["model"] == "claude-opus-4-8"
    assert kwargs["output_config"]["format"]["type"] == "json_schema"
    schema = kwargs["output_config"]["format"]["schema"]
    assert "executive_summary" in schema["required"]
    # question_id is required on both list sections so the executive dashboard can
    # match AI prose back to the deterministic rows it enriches.
    assert "question_id" in schema["properties"]["remediation_plan"]["items"]["required"]
    assert "question_id" in schema["properties"]["risk_register"]["items"]["required"]


# ---------- Narrative cache ----------


@patch("risklens.ai.narrator.anthropic.Anthropic")
def test_generate_narrative_second_identical_assessment_is_served_from_cache(
    mock_anthropic, monkeypatch, tmp_path
):
    monkeypatch.setenv("RISKLENS_NARRATIVE_CACHE_DIR", str(tmp_path))
    mock_anthropic.return_value = _mock_client_with_response(FAKE_NARRATIVE)

    first = generate_narrative(_sample_result())
    second = generate_narrative(_sample_result())

    assert first == second == FAKE_NARRATIVE
    mock_anthropic.return_value.messages.create.assert_called_once()


@patch("risklens.ai.narrator.anthropic.Anthropic")
def test_generate_narrative_cache_misses_when_an_answer_score_changes(
    mock_anthropic, monkeypatch, tmp_path
):
    monkeypatch.setenv("RISKLENS_NARRATIVE_CACHE_DIR", str(tmp_path))
    mock_anthropic.return_value = _mock_client_with_response(FAKE_NARRATIVE)
    framework = load_framework("nist_csf")
    assessment = load_assessment("examples/sample_answers.yaml")
    question_id = next(iter(assessment.answers))
    original = assessment.answers[question_id]
    regressed = replace(
        assessment,
        answers={**assessment.answers, question_id: replace(original, score=0)},
    )

    generate_narrative(score_assessment(framework, assessment))
    generate_narrative(score_assessment(framework, regressed))

    assert mock_anthropic.return_value.messages.create.call_count == 2


@patch("risklens.ai.narrator.anthropic.Anthropic")
def test_generate_narrative_cache_misses_when_the_finding_threshold_changes(
    mock_anthropic, monkeypatch, tmp_path
):
    # A stricter threshold surfaces a different set of findings, so the payload
    # the model sees genuinely differs even though the answers are identical.
    monkeypatch.setenv("RISKLENS_NARRATIVE_CACHE_DIR", str(tmp_path))
    mock_anthropic.return_value = _mock_client_with_response(FAKE_NARRATIVE)
    framework = load_framework("nist_csf")
    assessment = load_assessment("examples/sample_answers.yaml")

    generate_narrative(score_assessment(framework, assessment, finding_threshold=3))
    generate_narrative(score_assessment(framework, assessment, finding_threshold=4))

    assert mock_anthropic.return_value.messages.create.call_count == 2


@patch("risklens.ai.narrator.anthropic.Anthropic")
def test_generate_narrative_cache_is_isolated_from_real_user_home(
    mock_anthropic, monkeypatch, tmp_path
):
    monkeypatch.setenv("RISKLENS_NARRATIVE_CACHE_DIR", str(tmp_path))
    mock_anthropic.return_value = _mock_client_with_response(FAKE_NARRATIVE)

    generate_narrative(_sample_result())

    assert list(tmp_path.glob("*.json"))
