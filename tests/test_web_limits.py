from pathlib import Path

from fastapi.testclient import TestClient

from risklens.web.app import app
from risklens.web.limits import RateLimiter, reset_rate_limiter

client = TestClient(app)

SAMPLE_YAML = Path("examples/sample_answers.yaml").read_text(encoding="utf-8")

# /simulate is the cheapest guarded POST route: it re-scores in memory and
# writes nothing to disk, so these tests need no storage-dir overrides
SIMULATE_DATA = {"answers_yaml": SAMPLE_YAML, "question_ids": ["gov-04"]}


def test_normal_form_submission_passes_both_guards():
    response = client.post("/simulate", data=SIMULATE_DATA)

    assert response.status_code == 200
    assert "What if these findings were fixed" in response.text


def test_oversized_request_body_is_rejected_with_413():
    oversized = dict(SIMULATE_DATA, answers_yaml=SAMPLE_YAML + "x" * (600 * 1024))

    response = client.post("/simulate", data=oversized)

    assert response.status_code == 413
    assert "Request body too large" in response.text


def test_body_cap_is_configurable_from_the_environment(monkeypatch):
    monkeypatch.setenv("RISKLENS_MAX_REQUEST_BYTES", "128")

    response = client.post("/simulate", data=SIMULATE_DATA)

    assert response.status_code == 413


def test_body_cap_can_be_disabled_with_zero(monkeypatch):
    monkeypatch.setenv("RISKLENS_MAX_REQUEST_BYTES", "0")
    oversized = dict(SIMULATE_DATA, answers_yaml=SAMPLE_YAML + "\n# " + "x" * (600 * 1024))

    response = client.post("/simulate", data=oversized)

    assert response.status_code == 200


def test_oversized_chunked_body_with_no_declared_length_is_rejected_with_413():
    def chunks():
        yield b"answers_yaml="
        for _ in range(12):
            yield b"x" * (64 * 1024)

    # a streamed body declares no Content-Length, so the cap has to be
    # enforced as the chunks arrive rather than from the header
    response = client.post(
        "/simulate",
        content=chunks(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 413
    assert "Request body too large" in response.text


def test_exceeding_the_rate_limit_returns_429(monkeypatch):
    monkeypatch.setenv("RISKLENS_RATE_LIMIT_REQUESTS", "2")

    assert client.post("/simulate", data=SIMULATE_DATA).status_code == 200
    assert client.post("/simulate", data=SIMULATE_DATA).status_code == 200

    response = client.post("/simulate", data=SIMULATE_DATA)

    assert response.status_code == 429
    assert "Too many requests" in response.text
    assert int(response.headers["retry-after"]) >= 1


def test_resetting_the_limiter_clears_an_exhausted_window(monkeypatch):
    monkeypatch.setenv("RISKLENS_RATE_LIMIT_REQUESTS", "1")
    assert client.post("/simulate", data=SIMULATE_DATA).status_code == 200
    assert client.post("/simulate", data=SIMULATE_DATA).status_code == 429

    reset_rate_limiter()

    assert client.post("/simulate", data=SIMULATE_DATA).status_code == 200


def test_read_only_routes_are_never_rate_limited(monkeypatch):
    monkeypatch.setenv("RISKLENS_RATE_LIMIT_REQUESTS", "1")

    for _ in range(5):
        assert client.get("/").status_code == 200
        assert client.get("/app").status_code == 200


def test_default_limits_do_not_throttle_a_realistic_local_session():
    # a human filling out and resubmitting the questionnaire, nowhere near
    # the default allowance
    for _ in range(20):
        assert client.post("/simulate", data=SIMULATE_DATA).status_code == 200


def test_rate_limiter_window_slides_forward():
    limiter = RateLimiter()
    kwargs = {"limit": 2, "window": 60.0}

    assert limiter.check("1.2.3.4", now=100.0, **kwargs) is None
    assert limiter.check("1.2.3.4", now=101.0, **kwargs) is None
    retry_after = limiter.check("1.2.3.4", now=102.0, **kwargs)

    assert retry_after == 58.0
    # the first hit leaves the window, so one slot frees up
    assert limiter.check("1.2.3.4", now=161.0, **kwargs) is None


def test_rate_limiter_keys_clients_independently():
    limiter = RateLimiter()
    kwargs = {"limit": 1, "window": 60.0}

    assert limiter.check("1.2.3.4", now=100.0, **kwargs) is None
    assert limiter.check("1.2.3.4", now=100.0, **kwargs) is not None
    # a different client still gets its own allowance
    assert limiter.check("5.6.7.8", now=100.0, **kwargs) is None


def test_rate_limiter_limit_of_zero_disables_the_check():
    limiter = RateLimiter()

    for _ in range(50):
        assert limiter.check("1.2.3.4", limit=0, window=60.0, now=100.0) is None
