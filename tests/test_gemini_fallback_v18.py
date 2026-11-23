"""Retry/fallback behavior is tested without making real Gemini calls."""
import io
import json
import urllib.error

import pytest
from fastapi.testclient import TestClient
from app.gemini import GeminiService
from app.ai_errors import AIServiceError
from app import gemini as gemini_module
from app.main import app
from app import main


class FakeResponse:
    def __init__(self, data):
        self.content=json.dumps(data).encode()
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self):return self.content


def test_retry_then_fallback_from_temporary_503(monkeypatch):
    service=GeminiService();service.api_key='dummy-not-a-real-key';service.model='gemini-3.8-flash'
    routes=[]
    def fake_urlopen(req,timeout):
        routes.append(req.full_url)
        if 'gemini-3.8-flash' in req.full_url:
            raise urllib.error.HTTPError(req.full_url,503,'busy',None,io.BytesIO())
        return FakeResponse({'candidates':[{'content':{'parts':[{'text':'hello'}]}}]})
    monkeypatch.setattr(gemini_module.urllib.request,'urlopen',fake_urlopen)
    monkeypatch.setattr(gemini_module.time,'sleep',lambda seconds:None)
    assert service._call([{'text':'hello'}])=='hello'
    assert len(routes)==4
    assert 'gemini-3.6-flash' in routes[3]


def test_invalid_api_key_is_not_retried(monkeypatch):
    service=GeminiService();service.api_key='dummy-not-a-real-key'
    calls=[]
    def fail(req,timeout):
        calls.append(req.full_url)
        raise urllib.error.HTTPError(req.full_url,401,'bad key',None,io.BytesIO())
    monkeypatch.setattr(gemini_module.urllib.request,'urlopen',fail)
    with pytest.raises(AIServiceError) as err:service._call([{'text':'ping'}])
    assert err.value.code=='invalid_key'
    assert len(calls)==1


def test_admin_create_teacher_without_email_in_cloud(monkeypatch):
    monkeypatch.setattr(main,'APP_ENV','cloud')
    with TestClient(app) as client:
        admin=client.post('/api/v1/auth/login',json={'email':'admin@demo.com','password':'admin123'}).json()
        headers={'Authorization':'Bearer '+admin['access_token']}
        import uuid
        e='cloud-teacher-'+uuid.uuid4().hex+'@example.test'
        data={'full_name':'Demo Teacher Cloud','email':e,'role':'teacher','password':'TempPassword456!'}
        r=client.post('/api/v1/admin/users',json=data,headers=headers)
        assert r.status_code==201,r.text
        assert r.json()['user']['role']=='teacher'
        assert 'password' not in r.json()
        assert client.post('/api/v1/auth/login',json={'email':e,'password':data['password']}).status_code==200
        student={'full_name':'Learner','email':'cloud-'+uuid.uuid4().hex+'@example.test',
                 'role':'student','grade':3,'password':'TempPassword456!'}
        assert client.post('/api/v1/admin/users',json=student,headers=headers).status_code==422
        student['guardian_confirmed']=True
        assert client.post('/api/v1/admin/users',json=student,headers=headers).status_code==201
