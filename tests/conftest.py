import pytest

from risklens.web.limits import reset_rate_limiter


@pytest.fixture(autouse=True)
def _clean_rate_limiter():
    """The web rate limiter is shared per-process state, so clear it around
    every test -- one test's form submissions must never count against
    another's, the same way RISKLENS_*_DIR overrides keep stored state from
    leaking between tests."""
    reset_rate_limiter()
    yield
    reset_rate_limiter()
