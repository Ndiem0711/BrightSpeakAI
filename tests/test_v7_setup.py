from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
P=Path(__file__).resolve().parent.parent

def test_v7_key_file_empty():
 assert 'GEMINI_API_KEY=' in (P/'GEMINI_KEY.txt').read_text(encoding='utf-8-sig')
 assert [a.strip() for a in (P/'GEMINI_KEY.txt').read_text(encoding='utf-8-sig').splitlines() if a.strip().startswith('GEMINI_API_KEY=')]==['GEMINI_API_KEY=']

def test_v7_key_ignored_for_cloud():
 for f in ['.dockerignore','.railwayignore','.gitignore']:
  assert 'GEMINI_KEY.txt' in (P/f).read_text()

def test_v7_health():
 with TestClient(app) as c:
  assert c.get('/api/v1/system/health').json()['version']=='13.0.0'

def test_v7_one_click():
 assert 'Get-BrightSpeakGeminiKey' in (P/'START-BRIGHTSPEAK.ps1').read_text(encoding='utf-8-sig')
 assert "Read-Host 'Gemini API key" not in (P/'START-BRIGHTSPEAK.ps1').read_text(encoding='utf-8-sig')
