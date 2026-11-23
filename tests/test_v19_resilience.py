"""Regression checks for repeated ASR and Cloud deploy configuration.
No user microphone, network or Gemini key is required.
"""
from __future__ import annotations
from pathlib import Path
import io
import urllib.error
import pytest
from app import asr
from app import gemini as gm
from app.ai_errors import AIServiceError
from app.gemini import GeminiService

ROOT = Path(__file__).resolve().parents[1]


def test_three_sequential_gemini_requests_have_distinct_results(monkeypatch):
    engine=asr._ASR()
    phrases=iter(['hello','good morning','I like apples'])
    monkeypatch.setattr(asr.gemini,'api_key','fake-key')
    monkeypatch.setattr(asr.gemini,'transcribe_wav',lambda wav: next(phrases))
    assert [engine(b'RIFFinput')[0] for _ in range(3)] == ['hello','good morning','I like apples']

def test_no_lesson_fabrication_when_gemini_empty(monkeypatch):
    engine=asr._ASR()
    monkeypatch.setattr(asr.gemini,'api_key','fake-key')
    monkeypatch.setattr(asr.gemini,'transcribe_wav',lambda audio:'')
    with pytest.raises(asr.ASRUnavailable,match='chưa nghe rõ'):
        engine(b'RIFFinput')

def test_gemini_service_failure_sanitized(monkeypatch):
    engine=asr._ASR()
    monkeypatch.setattr(asr.gemini,'api_key','fake-key')
    def failure(wav):
        raise AIServiceError('quota_exceeded','Đã chạm hạn mức API.')
    monkeypatch.setattr(asr.gemini,'transcribe_wav',failure)
    with pytest.raises(asr.ASRUnavailable,match='hạn mức'):
        engine(b'RIFFinput')

def test_gemini_429_backoff_then_success(monkeypatch):
    service=GeminiService();service.api_key='not-a-real-key'
    calls=[];delays=[]
    class Result:
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self):return b'{"candidates":[{"content":{"parts":[{"text":"hello"}]}}]}'
    def invoke(req, timeout):
        calls.append(req.full_url)
        if len(calls)<3:
            raise urllib.error.HTTPError(req.full_url,429,'too many requests',{'Retry-After':'0.5'},io.BytesIO())
        return Result()
    monkeypatch.setattr(gm.urllib.request,'urlopen',invoke)
    monkeypatch.setattr(gm.time,'sleep',lambda seconds:delays.append(seconds))
    assert service._call([{'text':'hello'}])=='hello'
    assert len(calls)==3
    assert delays==[0.5,0.5]


def test_gemini_429_still_errors_with_a_sanitized_message(monkeypatch):
    service=GeminiService();service.api_key='not-a-real-key'
    def invoke(req,timeout):
        raise urllib.error.HTTPError(req.full_url,429,'key-is-SECRET',None,io.BytesIO())
    monkeypatch.setattr(gm.urllib.request,'urlopen',invoke)
    monkeypatch.setattr(gm.time,'sleep',lambda seconds:None)
    with pytest.raises(AIServiceError) as err:
        service._call([{'text':'hello'}])
    assert err.value.code == 'quota_exceeded'
    assert 'SECRET' not in str(err.value)


def test_cloud_blueprint_checks_repo_root_and_no_legacy_name():
    content=(ROOT/'render.yaml').read_text()
    assert 'brightspeakai-app' in content
    assert 'brightspeakai\n' in content
    assert 'v13' not in content.lower()
    assert "app/main.py" in content
    assert 'PYTHON_VERSION' in content
    assert 'DATABASE_URL' in content
    assert (ROOT/'app/main.py').exists()
    assert (ROOT/'app/__init__.py').exists()
    assert 'GEMINI_KEY.txt' in (ROOT/'.gitignore').read_text()


def test_local_launcher_is_gemini_only():
    launcher=(ROOT/'START-BRIGHTSPEAK.ps1').read_text(encoding='utf-8')
    assert "$env:ASR_ENGINE='gemini'" in launcher
    assert 'requirements-ml' not in launcher
    assert not (ROOT/'requirements-ml.txt').exists()
    assert not (ROOT/'scripts/prepare_asr.py').exists()
