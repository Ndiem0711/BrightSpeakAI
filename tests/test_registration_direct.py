"""V13.0.1 direct signup: no email delivery, no OTP, immediate student session."""
import uuid
import pytest
from fastapi.testclient import TestClient
from app import main
from app.main import app
from app.db import db

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main,'REGISTRATION_MODE','direct')
    monkeypatch.setattr(main,'APP_ENV','cloud')
    monkeypatch.setattr(main,'email_ready',lambda:False)
    def forbidden(*a,**k):
        raise AssertionError('Direct signup must not send email')
    monkeypatch.setattr(main,'send_otp_email',forbidden)
    with TestClient(app) as c: yield c


def payload():
    return {'full_name':'Registration test','email':f'qa-{uuid.uuid4().hex}@example.test',
        'password':'StudentTest123!', 'confirm_password':'StudentTest123!',
        'grade':3,'guardian_confirmed':True}


def test_direct_register_returns_session_without_otp(client):
    body=payload();r=client.post('/api/v1/auth/register',json=body)
    assert r.status_code==201,r.text
    d=r.json();assert d['requires_verification'] is False
    assert d['email_verified'] is False and d['user']['email_verified'] is False
    assert d['user']['role']=='student' and d['user']['verified'] is True
    assert not db.fetchone('SELECT id FROM otp_codes WHERE user_id=?',(d['user']['id'],))
    headers={'Authorization':'Bearer '+d['access_token']}
    assert client.get('/api/v1/auth/me',headers=headers).status_code==200
    assert client.get('/api/v1/lessons',headers=headers).status_code==200
    assert client.get('/api/v1/admin/overview',headers=headers).status_code==403
    assert client.post('/api/v1/auth/login',json={'email':body['email'],'password':body['password']}).status_code==200


def test_direct_requires_guardian_confirmation(client):
    body=payload();body['guardian_confirmed']=False
    assert client.post('/api/v1/auth/register',json=body).status_code==422


def test_direct_cannot_overwrite_existing_account(client):
    body=payload();assert client.post('/api/v1/auth/register',json=body).status_code==201
    body['password']='AnotherPassword123!';body['confirm_password']=body['password']
    assert client.post('/api/v1/auth/register',json=body).status_code==409


def test_direct_rejects_mismatch_and_invalid_email(client):
    body=payload();body['confirm_password']='different'
    assert client.post('/api/v1/auth/register',json=body).status_code==422
    body=payload();body['email']='not-an-email'
    assert client.post('/api/v1/auth/register',json=body).status_code==400


def test_pending_student_can_resume_only_with_own_password(client):
    body=payload();d=client.post('/api/v1/auth/register',json=body).json()
    uid=d['user']['id'];db.execute('UPDATE users SET verified=0 WHERE id=?',(uid,))
    wrong={**body,'password':'WrongPassword123!','confirm_password':'WrongPassword123!'}
    assert client.post('/api/v1/auth/register',json=wrong).status_code==409
    assert db.fetchone('SELECT verified FROM users WHERE id=?',(uid,))['verified']==0
    r=client.post('/api/v1/auth/register',json=body)
    assert r.status_code==201 and r.json()['user']['id']==uid


def test_signup_cannot_choose_admin_role(client):
    body=payload();body['role']='admin'
    r=client.post('/api/v1/auth/register',json=body)
    assert r.status_code==201 and r.json()['user']['role']=='student'
