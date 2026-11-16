"""Cloud-readiness checks that make NO calls to Google Cloud or Gemini."""
import os
os.environ['DATABASE_URL'] = 'sqlite:///runtime/test_bright.db'
os.environ['DEMO_OTP'] = 'true'
os.environ['GEMINI_API_KEY'] = ''

from fastapi.testclient import TestClient
from app.main import app
from app.db import db
from app.auth import verify_password
from app import seed


def _login(client, name, pwd):
    response = client.post('/api/v1/auth/login', json={'email': name, 'password': pwd})
    assert response.status_code == 200, response.text
    return {'Authorization': 'Bearer '+response.json()['access_token']}


def test_admin_account_provisioning_access_controls():
    with TestClient(app) as c:
        admin = _login(c, 'admin@demo.com', 'admin123')
        student = _login(c, 'student@demo.com', 'student123')
        payload = {'full_name': 'Cloud Test Teacher', 'email': 'cloud-qa-teacher@example.org',
                   'password': 'A-Demo-Only-Password-123', 'role': 'teacher', 'grade': None}
        assert c.post('/api/v1/admin/users',json=payload).status_code == 401
        assert c.post('/api/v1/admin/users',json=payload,headers=student).status_code == 403
        result=c.post('/api/v1/admin/users',json=payload,headers=admin)
        assert result.status_code in (201,409), result.text
        if result.status_code == 201:
            assert result.json()['user']['role']=='teacher'
            assert 'password' not in result.json()
        assert c.post('/api/v1/admin/users',json=payload,headers=admin).status_code == 409
        invalid=dict(payload,email='cloud-qa-bad-student@example.org',role='student',grade=None)
        assert c.post('/api/v1/admin/users',json=invalid,headers=admin).status_code == 422


def test_cloud_seed_idempotent_and_requires_env(monkeypatch):
    with TestClient(app):
        monkeypatch.setattr(seed,'APP_ENV','cloud')
        monkeypatch.setenv('BOOTSTRAP_ADMIN_EMAIL','cloud-bootstrap-test@example.org')
        monkeypatch.setenv('BOOTSTRAP_ADMIN_PASSWORD','test_admin_bootstrap_pwd_12')
        seed.seed_cloud_admin()
        user=db.fetchone('SELECT * FROM users WHERE email=?',('cloud-bootstrap-test@example.org',))
        assert user is not None and user['role']=='admin' and user['verified']==1
        old_hash = user['password_hash']
        monkeypatch.setenv('BOOTSTRAP_ADMIN_PASSWORD','different_password_12')
        seed.seed_cloud_admin()
        assert db.fetchone('SELECT * FROM users WHERE email=?',('cloud-bootstrap-test@example.org',))['password_hash']==old_hash
        monkeypatch.delenv('BOOTSTRAP_ADMIN_PASSWORD')
        monkeypatch.delenv('BOOTSTRAP_ADMIN_EMAIL')
        seed.seed_cloud_admin()
