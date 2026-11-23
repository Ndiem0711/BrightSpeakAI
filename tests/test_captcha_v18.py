"""CAPTCHA security and front-end regression tests (no real email/API calls)."""
from datetime import timedelta
from pathlib import Path
from fastapi.testclient import TestClient
import pytest
from app.main import app
from app import captcha
from app.db import db


def test_captcha_not_disclosed_and_is_raster(monkeypatch):
    monkeypatch.setattr(captcha.secrets,'choice',lambda _: 'D')
    with TestClient(app) as c:
        r=c.get('/api/v1/auth/captcha')
        assert r.status_code==200
        d=r.json()
        assert d['image_data'].startswith('data:image/png;base64,')
        assert not any(k in d for k in ('answer','code','demo_otp'))
        assert c.get('/').status_code==200
        assert 'regCaptchaText' in c.get('/').text
        assert 'otpForm' not in c.get('/').text


def test_failed_captcha_limit_and_replay(monkeypatch):
    monkeypatch.setattr(captcha.secrets,'choice',lambda _: 'E')
    with TestClient(app) as c:
        cid=c.get('/api/v1/auth/captcha').json()['captcha_id']
        for _ in range(captcha.MAX_ATTEMPTS):
            with pytest.raises(Exception):captcha.consume(cid,'WRONG')
        with pytest.raises(Exception):captcha.consume(cid,'EEEEE')
        cid=c.get('/api/v1/auth/captcha').json()['captcha_id']
        captcha.consume(cid,'eeeee')
        with pytest.raises(Exception):captcha.consume(cid,'EEEEE')


def test_expired_captcha(monkeypatch):
    monkeypatch.setattr(captcha.secrets,'choice',lambda _: 'F')
    with TestClient(app) as c:
        cid=c.get('/api/v1/auth/captcha').json()['captcha_id']
        db.execute('UPDATE captcha_challenges SET expires_at=? WHERE id=?',('2000-01-01T00:00:00+00:00',cid))
        with pytest.raises(Exception):captcha.consume(cid,'FFFFF')


def test_gemini_only_cloud_deployment_files():
    root=Path(__file__).resolve().parents[1]
    assert not (root/'requirements-ml.txt').exists()
    assert 'Pillow' in (root/'requirements.txt').read_text()
    assert 'BrightSpeakAI' in (root/'render.yaml').read_text()
