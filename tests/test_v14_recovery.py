import pytest
from fastapi.testclient import TestClient
from app import seed
from app.main import app
from app.db import Database
from scripts import recover_accounts as recovery


def test_demo_repair_and_admin_recovery(tmp_path, monkeypatch):
    database = Database('sqlite:///' + str(tmp_path/'users.db'))
    for module in (seed, recovery):
        monkeypatch.setattr(module, 'db', database)
        monkeypatch.setattr(module, 'APP_ENV', 'local')
    import app.main as main
    monkeypatch.setattr(main, 'db', database)
    with TestClient(app) as c:
        database.execute("UPDATE users SET active=0 WHERE id='demo-admin'")
        recovery.recover_demos()
        for _, email, password, _, role, _ in seed.DEMO_USERS:
            r = c.post('/api/v1/auth/login', json=dict(email=email,password=password))
            assert r.json()['user']['role'] == role
        recovery.recover_admin('ADMIN@demo.com','replacement-14')
        assert c.post('/api/v1/auth/login',json=dict(email='admin@demo.com',password='replacement-14')).status_code == 200
        with pytest.raises(ValueError):
            recovery.recover_admin('student@demo.com','replacement-14')
        monkeypatch.setattr(recovery, 'APP_ENV', 'cloud')
        with pytest.raises(ValueError):
            recovery.recover_demos()
