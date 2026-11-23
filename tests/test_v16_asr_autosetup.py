"""ASR regression: no Whisper, Gemini-only (fake provider, no network)."""
from pathlib import Path
import pytest
from app import asr
from app.main import app
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1]

def test_launcher_starts_gemini_without_whisper():
    launcher=(ROOT/'START-BRIGHTSPEAK.ps1').read_text(encoding='utf-8')
    assert "$env:ASR_ENGINE='gemini'" in launcher
    assert "& $python 'scripts/check_gemini_config.py'" in launcher
    assert 'requirements-ml' not in launcher
    assert 'prepare_asr' not in launcher
    assert 'Get-BrightSpeakGeminiKey' in launcher
    assert '20.0.0' in launcher

def test_no_gemini_key_is_clear_error(monkeypatch):
    engine=asr._ASR()
    monkeypatch.setattr(asr.gemini,'api_key','')
    assert not engine.available()
    assert engine.provider()=='unavailable'
    with pytest.raises(asr.ASRUnavailable,match='Gemini API key'):
        engine(b'RIFFfake')

def test_gemini_is_the_only_asr_provider(monkeypatch):
    engine=asr._ASR()
    monkeypatch.setattr(asr.gemini,'api_key','fake-key')
    monkeypatch.setattr(asr.gemini,'transcribe_wav',lambda wav:'I can see a cat.')
    assert engine(b'RIFFfake')==('I can see a cat.','gemini')

def test_missing_transcript_not_fabricated(monkeypatch):
    engine=asr._ASR()
    monkeypatch.setattr(asr.gemini,'api_key','fake-key')
    monkeypatch.setattr(asr.gemini,'transcribe_wav',lambda wav:'')
    with pytest.raises(asr.ASRUnavailable,match='chưa nghe rõ'):
        engine(b'RIFFfake')

def test_cloud_health_only_reports_gemini_or_unavailable():
    with TestClient(app) as c:
        result=c.get('/api/v1/system/health').json()
    assert result['version']=='20.0.0'
    assert result['asr_provider'] in {'gemini','unavailable'}
    assert result['local_asr_available'] is False
    assert 'api_key' not in result
