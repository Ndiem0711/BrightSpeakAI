
"""Regression: V7 failed on Windows 10/11 Python 3.12 without IANA tzdata."""
from datetime import timedelta
from pathlib import Path
from fastapi.testclient import TestClient
from app.daily import VIETNAM_TZ, local_day
from app.main import app

ROOT=Path(__file__).resolve().parents[1]

def test_vietnam_timezone_without_system_tzdata():
    assert VIETNAM_TZ.utcoffset(None) == timedelta(hours=7)
    assert len(local_day()) == 10
    assert local_day()[4] == '-' and local_day()[7] == '-'

def test_v8_health_and_pages():
    with TestClient(app) as client:
        r=client.get('/api/v1/system/health')
        assert r.status_code == 200
        assert r.json()['version'] == '13.0.0'
        assert client.get('/').status_code == 200
        assert client.get('/static/app.js').status_code == 200

def test_one_click_keeps_key_out_of_source():
    assert (ROOT/'GEMINI_KEY.txt').exists()
    for name in ('.gitignore','.dockerignore','.railwayignore'):
        assert 'GEMINI_KEY.txt' in (ROOT/name).read_text(encoding='utf-8')
    assert 'Get-BrightSpeakGeminiKey' in (ROOT/'START-BRIGHTSPEAK.ps1').read_text(encoding='utf-8-sig')
    assert '13.0.0' in (ROOT/'START-BRIGHTSPEAK.ps1').read_text(encoding='utf-8-sig')
