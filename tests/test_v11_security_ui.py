"""V11 security/regression coverage. No real messages or Gemini requests sent."""
from __future__ import annotations
import re
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient
from app.main import app
from app import main, captcha

ROOT=Path(__file__).resolve().parents[1]


def _sign_up(c,email,name,password,monkeypatch):
    monkeypatch.setattr(captcha.secrets,'choice',lambda _: 'C')
    challenge=c.get('/api/v1/auth/captcha').json()
    response=c.post('/api/v1/auth/register',json={
        'email':email,'full_name':name,'password':password,'confirm_password':password,
        'grade':3,'guardian_confirmed':True,'captcha_id':challenge['captcha_id'],'captcha_code':'CCCCC'})
    assert response.status_code==201,response.text
    return response.json()


def _login(c,email='admin@demo.com',password='admin123'):
    r=c.post('/api/v1/auth/login',json={'email':email,'password':password})
    assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['access_token']}


def _token_from_email(body):
    m=re.search(r'https?://[^\s]+account_token=([^\s]+)',body)
    assert m,body
    return m.group(1)


def test_v11_change_password_requires_two_identical_new_passwords(monkeypatch):
    with TestClient(app) as c:
        email=f'profile-{uuid.uuid4().hex[:10]}@example.test'
        v=_sign_up(c,email,'Practice Learner','begin-12345',monkeypatch)
        h={'Authorization':'Bearer '+v['access_token']}
        old={'current_password':'begin-12345','new_password':'changed-12345'}
        assert c.post('/api/v1/profile/password',headers=h,json=old).status_code==422
        assert c.post('/api/v1/profile/password',headers=h,json={**old,'confirm_password':'different'}).status_code==422
        assert c.post('/api/v1/profile/password',headers=h,json={**old,'confirm_password':'changed-12345'}).status_code==200
        assert c.get('/api/v1/auth/me',headers=h).status_code==401  # all old access tokens revoked
        assert c.post('/api/v1/auth/refresh',json={'refresh_token':v['refresh_token']}).status_code==401
        assert c.post('/api/v1/auth/login',json={'email':email,'password':'begin-12345'}).status_code==401
        assert c.post('/api/v1/auth/login',json={'email':email,'password':'changed-12345'}).status_code==200


def test_v11_reset_token_one_time_no_email_enumeration(monkeypatch):
    received=[]
    monkeypatch.setattr(main,'email_ready',lambda:True)
    monkeypatch.setattr(main,'send_transactional_email',lambda to,subject,body:received.append((to,subject,body)) or True)
    with TestClient(app) as c:
        email=f'reset-{uuid.uuid4().hex[:10]}@example.test'
        _sign_up(c,email,'Reset Learner','before-12345',monkeypatch)
        received.clear()
        r=c.post('/api/v1/auth/password/forgot',json={'email':email})
        assert r.status_code==200
        assert len(received)==1
        raw=_token_from_email(received[0][2])
        assert c.get('/api/v1/auth/password/link-info',params={'token':raw}).json()['purpose']=='reset'
        x={'token':raw,'new_password':'after-12345','confirm_password':'bad'}
        assert c.post('/api/v1/auth/password/complete',json=x).status_code==422
        assert c.post('/api/v1/auth/password/complete',json={**x,'confirm_password':'after-12345'}).status_code==200
        assert c.post('/api/v1/auth/password/complete',json={**x,'confirm_password':'after-12345'}).status_code==400
        assert c.post('/api/v1/auth/login',json={'email':email,'password':'after-12345'}).status_code==200
        unknown=c.post('/api/v1/auth/password/forgot',json={'email':'no-such-account@example.test'})
        assert unknown.status_code==200
        assert unknown.json()['message']==r.json()['message']
        assert len(received)==1


def test_v11_admin_invitation_not_plaintext_password(monkeypatch):
    received=[]
    monkeypatch.setattr(main,'email_ready',lambda:True)
    monkeypatch.setattr(main,'send_transactional_email',lambda to,subject,body:received.append((to,subject,body)) or True)
    with TestClient(app) as c:
        h=_login(c)
        email=f'teacher-{uuid.uuid4().hex[:10]}@example.test'
        body={'full_name':'Demo Teacher','email':email,'role':'teacher'}
        result=c.post('/api/v1/admin/invitations',headers=h,json=body)
        assert result.status_code==201,result.text
        assert result.json()['user']['verified'] is False
        assert c.post('/api/v1/auth/login',json={'email':email,'password':'made-up'}).status_code==401
        assert len(received)==1
        assert 'Mật khẩu:' not in received[0][2]
        raw=_token_from_email(received[0][2])
        assert c.get('/api/v1/auth/password/link-info',params={'token':raw}).json()['purpose']=='invite'
        assert c.post('/api/v1/auth/password/complete',json={'token':raw,'new_password':'new-teacher-123','confirm_password':'new-teacher-123'}).status_code==200
        assert c.post('/api/v1/auth/login',json={'email':email,'password':'new-teacher-123'}).status_code==200
        child=c.post('/api/v1/admin/invitations',headers=h,json={'full_name':'Child Example','email':f'{uuid.uuid4().hex}@example.test','role':'student','grade':3})
        assert child.status_code==422


def test_v11_mail_unconfigured_produces_clear_error(monkeypatch):
    monkeypatch.setattr(main,'email_ready',lambda:False)
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/password/forgot',json={'email':'fake@example.com'}).status_code==503
        h=_login(c)
        assert c.post('/api/v1/admin/invitations',headers=h,json={'full_name':'Another Teacher','email':'teacher@example.com','role':'teacher'}).status_code==503


def test_v11_ui_source_integrity():
    html=(ROOT/'app/static/index.html').read_text()
    js=(ROOT/'app/static/features.js').read_text()
    launcher=(ROOT/'START-BRIGHTSPEAK.ps1').read_text()
    assert '<title>BrightSpeakAI – Luyện nói tiếng Anh</title>' in html
    assert "WindowTitle='BrightSpeakAI'" in launcher
    assert 'confirmPass' in js and 'confirm_password' in js
    assert 'account_token' in (ROOT/'app/static/app.js').read_text()
    assert 'function closeLiveTurn()' in js
    assert 'bubble.dataset.turnSpeaker=who' in js
    assert 'v11-meet-toolbar' in js and 'v11-meet-aside' in js
    assert 'renderAdmin=renderAdminV11;' in js
