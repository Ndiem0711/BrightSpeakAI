"""V10 regression tests: Gemini Live must survive more than one turn.
No actual Gemini calls, media capture or child recordings.
"""
import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault('DATABASE_URL','sqlite:///runtime/test_bright.db')

from fastapi.testclient import TestClient
from app.main import app

ROOT=Path(__file__).resolve().parents[1]


import pytest

@pytest.mark.parametrize('reading', [False, True])
def test_live_relay_continues_after_greeting(monkeypatch, reading):
    import sys
    import types as pytypes
    import google
    fake_genai=pytypes.ModuleType('google.genai')
    fake_types=pytypes.ModuleType('google.genai.types')
    fake_types.Content=lambda **kw:kw
    fake_types.Part=lambda **kw:kw
    fake_types.Blob=lambda **kw:kw
    fake_genai.types=fake_types
    monkeypatch.setitem(sys.modules,'google.genai',fake_genai)
    monkeypatch.setitem(sys.modules,'google.genai.types',fake_types)
    monkeypatch.setattr(google,'genai',fake_genai,raising=False)
    genai=fake_genai
    import app.live as live
    monkeypatch.setattr(live, 'GEMINI_API_KEY', 'test-only-key')
    calls={'receive':0}
    class Session:
        async def send_client_content(self, **_):
            pass
        async def send_realtime_input(self, **_):
            pass
        async def receive(self):
            calls['receive']+=1
            if calls['receive']==1:
                content=SimpleNamespace(input_transcription=None,output_transcription=SimpleNamespace(text='Hello, I am Bibi.'), model_turn=None,turn_complete=True,interrupted=False)
                yield SimpleNamespace(server_content=content)
            elif calls['receive']==2:
                content=SimpleNamespace(input_transcription=SimpleNamespace(text='I like cats.'),output_transcription=None,model_turn=None,turn_complete=True,interrupted=False)
                yield SimpleNamespace(server_content=content)
            else:
                import asyncio
                await asyncio.sleep(3600)
                if False: yield None
    class Connect:
        async def __aenter__(self):return Session()
        async def __aexit__(self,*_):pass
    class Client:
        def __init__(self, **_): self.aio=SimpleNamespace(live=SimpleNamespace(connect=lambda **_:Connect()),aclose=self.aclose)
        async def aclose(self):pass
    monkeypatch.setattr(genai,'Client',Client,raising=False)
    with TestClient(app) as c:
        login=c.post('/api/v1/auth/login',json={'email':'student@demo.com','password':'student123'})
        assert login.status_code==200, login.text
        t=login.json()['access_token']
        with c.websocket_connect('/api/v1/live/ws') as ws:
            ws.send_json({'type':'init','activity':'read' if reading else 'talk','access_token':t,'topic':'Animals','video_consent':False})
            events=[ws.receive_json() for _ in range(7 if reading else 6)]
            reviews=[e for e in events if e['type']=='reading_feedback']
            assert len(reviews)==int(reading)
            if reading:
                assert reviews[0]['target'] and reviews[0]['topic'] and reviews[0]['heard']=='I like cats.'
            assert events[0]['type']=='ready', events
            assert {'type':'output_text','text':'Hello, I am Bibi.'} in events
            assert {'type':'input_text','text':'I like cats.'} in events
            assert sum(e['type']=='turn_complete' for e in events)==2,events
            ws.send_json({'type':'end'})
    assert calls['receive']>=2


def test_v10_live_ui_has_prompt_camera_and_one_audio_owner():
    js=(ROOT/'app/static/features.js').read_text(encoding='utf-8')
    backend=(ROOT/'app/live.py').read_text(encoding='utf-8')
    assert 'while True:\n                        pending_model_parts = []' in backend
    assert '"type": "interrupted"' in backend
    assert 'liveSampleQuestion' in js and 'liveSampleAnswer' in js
    assert 'liveCameraRequestId' in js and 'stopLive({closeCamera:false' in js
    assert 'livePlayback?.interrupt()' in js
    assert "speechSynthesis.cancel()" in js
    assert 'livePlayback?.isAudible()' in js
    assert "liveMessageQueue" not in js


def test_v10_health_and_assets():
    with TestClient(app) as c:
        assert c.get('/api/v1/system/health').json()['version']=='20.0.0'
        index=c.get('/').text
        assert '/static/features.js?v=20261123-v20-fastfix2' in index
        assert c.get('/static/features.js').status_code==200
