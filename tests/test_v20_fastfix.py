"""Low-latency V20 regression tests, no external Gemini requests or secrets."""
from __future__ import annotations
import io
import json
import math
import struct
import wave
import urllib.error

import pytest
from fastapi.testclient import TestClient
from app.gemini import GeminiService
from app import gemini as gemini_module
from app import main
from app.ai_errors import AIServiceError


class Response:
    def __init__(self, response):
        self.payload=json.dumps(response).encode('utf-8')
    def __enter__(self): return self
    def __exit__(self,*_): return False
    def read(self):return self.payload


def payload(text):
    return {'candidates':[{'content':{'parts':[{'text':text}]}}]}


def speech_wav():
    buf=io.BytesIO()
    with wave.open(buf,'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000)
        wav.writeframes(b''.join(struct.pack('<h',int(6500*math.sin(i*.1))) for i in range(16000)))
    return buf.getvalue()


def test_fast_asr_one_request_and_lite_model(monkeypatch):
    engine=GeminiService();engine.api_key='test-key-not-real';calls=[]
    def intercept(req,timeout):
        calls.append((req.full_url,timeout,json.loads(req.data)))
        return Response(payload('I like cats.'))
    monkeypatch.setattr(gemini_module.urllib.request,'urlopen',intercept)
    assert engine.transcribe_wav(speech_wav())=='I like cats.'
    assert len(calls)==1
    assert 'gemini-3.5-flash-lite' in calls[0][0]
    assert calls[0][1] == 15
    assert calls[0][2]['generationConfig']['maxOutputTokens'] >= 128


def test_fast_503_switches_once_without_long_backoff(monkeypatch):
    engine=GeminiService();engine.api_key='test-key-not-real';calls=[]
    def intercept(req,timeout):
        calls.append(req.full_url)
        if len(calls)==1:
            raise urllib.error.HTTPError(req.full_url,503,'busy',None,io.BytesIO())
        return Response(payload('Hello'))
    monkeypatch.setattr(gemini_module.urllib.request,'urlopen',intercept)
    monkeypatch.setattr(gemini_module.time,'sleep',lambda secs: (_ for _ in ()).throw(AssertionError('Fast path must not sleep')))
    assert engine.transcribe_wav(speech_wav())=='Hello'
    assert len(calls)==2
    assert 'gemini-3.5-flash-lite' in calls[0]
    assert 'gemini-3.8-flash' in calls[1]


def test_fast_429_is_actionable_not_generic(monkeypatch):
    engine=GeminiService();engine.api_key='test-key-not-real';calls=[]
    def fail(req,timeout):
        calls.append(req.full_url)
        raise urllib.error.HTTPError(req.full_url,429,'quota',None,io.BytesIO())
    monkeypatch.setattr(gemini_module.urllib.request,'urlopen',fail)
    with pytest.raises(AIServiceError) as exc:
        engine.transcribe_wav(speech_wav())
    assert exc.value.code=='quota_exceeded'
    assert len(calls)==2


def test_audio_picture_single_gemini_request(monkeypatch):
    engine=GeminiService();engine.api_key='test-key-not-real';calls=[]
    def intercept(req,timeout):
        data=json.loads(req.data);calls.append(data)
        return Response(payload(json.dumps({
            'transcript':'I see a red car.', 'score':88,
            'feedback':'Well done!', 'model_sentence':'I can see a red car.',
            'next_question':'Where is the car?'})))
    monkeypatch.setattr(gemini_module.urllib.request,'urlopen',intercept)
    result=engine.look_and_speak_audio(b'\xff\xd8\xff', 'image/jpeg', speech_wav(),3)
    assert result['transcript']=='I see a red car.' and result['score']==88
    assert len(calls)==1
    parts=calls[0]['contents'][0]['parts']
    assert sum('inline_data' in x for x in parts)==2
    assert calls[0]['generationConfig']['responseMimeType']=='application/json'


def test_invalid_json_or_empty_transcript_is_not_a_fake_success(monkeypatch):
    engine=GeminiService();engine.api_key='test-key-not-real'
    monkeypatch.setattr(engine,'_call',lambda *a,**k:'not json')
    with pytest.raises(AIServiceError,match='định dạng'):
        engine.look_and_speak_audio(b'\xff\xd8\xff','image/jpeg',speech_wav(),3)
    monkeypatch.setattr(engine,'_call',lambda *a,**k:json.dumps({'transcript':'','score':0,'feedback':'',
        'model_sentence':'','next_question':''}))
    with pytest.raises(AIServiceError) as err:
        engine.look_and_speak_audio(b'\xff\xd8\xff','image/jpeg',speech_wav(),3)
    assert err.value.code=='no_speech'


def test_look_speak_endpoint_voice_single_processing_step(monkeypatch):
    class AI:
        enabled=True
        def __init__(self):self.calls=0
        def look_and_speak_audio(self,image,mime,audio,grade):
            self.calls+=1
            return {'transcript':'I see a ball','score':82,'feedback':'Good',
                    'model_sentence':'I see a ball.','next_question':'What colour is it?'}
    fake=AI()
    monkeypatch.setattr(main,'gemini',fake)
    monkeypatch.setattr(main,'transcribe_audio',lambda a:(_ for _ in ()).throw(AssertionError('Separate ASR call is forbidden')))
    with TestClient(main.app) as client:
        login=client.post('/api/v1/auth/login',json={'email':'student@demo.com','password':'student123'})
        assert login.status_code==200
        headers={'Authorization':'Bearer '+login.json()['access_token']}
        resp=client.post('/api/v1/multimodal/look-speak',headers=headers,
                         files={'image':('img.jpg',b'\xff\xd8\xff\xe0','image/jpeg'),
                                'audio':('voice.wav',speech_wav(),'audio/wav')})
        assert resp.status_code==200,resp.text
        assert fake.calls==1
        assert resp.json()['transcript']=='I see a ball'
        assert resp.json()['latency_ms']>=0
