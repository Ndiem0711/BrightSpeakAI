"""Isolate CAPTCHA rate limits between tests; production rate limiting stays enabled."""
import pytest

@pytest.fixture(autouse=True)
def isolate_captcha_challenges():
    from app.db import db
    try:
        db.init_schema()
        db.execute('DELETE FROM captcha_challenges')
    except Exception:
        pass
