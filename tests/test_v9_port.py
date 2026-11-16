import pathlib
import socket
import sys
from fastapi.testclient import TestClient
from app.main import app
from scripts.select_local_port import choose_port,port_is_available

ROOT=pathlib.Path(__file__).resolve().parents[1]

def test_health_v9():
    with TestClient(app) as c:
        r=c.get('/api/v1/system/health')
        assert r.status_code==200 and r.json()['version']=='13.0.0'

def test_port_skip_busy():
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1',0));sock.listen(1)
        busy=sock.getsockname()[1]
        if busy<65534:
            assert not port_is_available('127.0.0.1',busy)
            assert choose_port('127.0.0.1',busy,3)!=busy

def test_launcher_uses_dynamic_port_and_does_not_kill():
    text=(ROOT/'START-BRIGHTSPEAK.ps1').read_text(encoding='utf-8')
    assert 'scripts/select_local_port.py' in text
    assert '--port' in text and '$port' in text
    assert 'Stop-Process' not in text
    assert '13.0.0' in text

def test_dataset_documents_present():
    assert (ROOT/'data'/'lessons.json').exists()
    assert (ROOT/'ml'/'DATA_LICENSE_AND_METRICS.md').exists()
