"""In-process WebSocket tests with fake Gemini Live session, no network/real children."""
import asyncio
import sys
import types as pytypes
from types import SimpleNamespace

from fastapi.testclient import TestClient
from app.main import app


def test_live_hint_rejects_wrong_lesson_and_reads_approved_sample(monkeypatch):
    import google
    import app.live as live
    fake_genai=pytypes.ModuleType('google.genai')
    fake_types=pytypes.ModuleType('google.genai.types')
    fake_types.Content=lambda **kw:kw
    fake_types.Part=lambda **kw:kw
    fake_types.Blob=lambda **kw:kw
    fake_genai.types=fake_types
    monkeypatch.setitem(sys.modules,'google.genai',fake_genai)
    monkeypatch.setitem(sys.modules,'google.genai.types',fake_types)
    monkeypatch.setattr(google,'genai',fake_genai,raising=False)
    monkeypatch.setattr(live,'GEMINI_API_KEY','test-key-not-real')

    sent=[]
    class FakeSession:
        def __init__(self):self.messages=asyncio.Queue()
        async def send_client_content(self, **kwargs):
            text=kwargs['turns'][0]['parts'][0]['text']
            sent.append(text)
            response=SimpleNamespace(server_content=SimpleNamespace(
                input_transcription=None,output_transcription=SimpleNamespace(text=text),
                model_turn=None,turn_complete=True,interrupted=False))
            await self.messages.put(response)
        async def send_realtime_input(self,**kwargs):pass
        async def receive(self):
            response=await self.messages.get()
            yield response
    class Connect:
        def __init__(self):self.session=FakeSession()
        async def __aenter__(self):return self.session
        async def __aexit__(self,*args):pass
    class Client:
        def __init__(self, **kwargs):self.aio=SimpleNamespace(live=SimpleNamespace(connect=lambda **kwargs:Connect()),aclose=self.aclose)
        async def aclose(self):pass
    fake_genai.Client=Client

    with TestClient(app) as client:
        login=client.post('/api/v1/auth/login',json={'email':'student@demo.com','password':'student123'})
        assert login.status_code==200,login.text
        token=login.json()['access_token']
        with client.websocket_connect('/api/v1/live/ws') as ws:
            ws.send_json({'type':'init','activity':'talk','access_token':token,'video_consent':False})
            ready=ws.receive_json()
            assert ready['type']=='ready'
            assert ready['question'] and ready['sample_answer']
            assert ready['prompt_id']
            # Initial response from the fake Live model.
            assert ws.receive_json()['type']=='output_text'
            assert ws.receive_json()['type']=='turn_complete'
            ws.send_json({'type':'request_hint','prompt_id':'other-lesson'})
            reject=ws.receive_json()
            assert reject['type']=='error_notice'
            ws.send_json({'type':'request_hint','prompt_id':ready['prompt_id']})
            hint=ws.receive_json()
            assert hint['type']=='hint_ready'
            assert hint['sample_answer']==ready['sample_answer']
            assert 'You can say: '+ready['sample_answer'] in (ws.receive_json()['text'])
            assert ws.receive_json()['type']=='turn_complete'
            ws.send_json({'type':'request_hint','prompt_id':ready['prompt_id']})
            ws.send_json({'type':'end'})
    assert len(sent)==2, 'only one approved hint should be sent to Gemini for this question'
