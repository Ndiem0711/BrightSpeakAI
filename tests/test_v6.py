"""V6 behaviour is testable without a camera or billable Gemini calls."""
import os
os.environ["DATABASE_URL"]="sqlite:///runtime/test_bright.db"
os.environ["DEMO_OTP"]="true"
os.environ["GEMINI_API_KEY"]=""
from fastapi.testclient import TestClient
from app.main import app
from app.daily import daily_goal, record_spoken_turn


def _student(c):
    d=c.post('/api/v1/auth/login',json={'email':'student@demo.com','password':'student123'}).json()
    return {'Authorization':'Bearer '+d['access_token']}, d['user']['id']


def test_v6_health_and_speaking_goal():
    with TestClient(app) as c:
        headers,user_id=_student(c)
        h=c.get('/api/v1/system/health').json()
        assert h['version']=='13.0.0'
        before=c.get('/api/v1/speaking/today',headers=headers)
        assert before.status_code==200
        assert before.json()['target']==3
        n=before.json()['count']
        record_spoken_turn(user_id,'voice_chat','I love cats.')
        assert c.get('/api/v1/speaking/today',headers=headers).json()['count']==n+1
        record_spoken_turn(user_id,'typed','I am typing a message')
        record_spoken_turn(user_id,'gemini_live','Hi')
        assert daily_goal(user_id)['count']==n+1


def test_v6_goal_rejects_unauthenticated_and_teacher():
    with TestClient(app) as c:
        assert c.get('/api/v1/speaking/today').status_code==401
        t=c.post('/api/v1/auth/login',json={'email':'teacher@demo.com','password':'teacher123'}).json()
        assert c.get('/api/v1/speaking/today',headers={'Authorization':'Bearer '+t['access_token']}).status_code==403
        v=c.get('/api/v1/teacher/overview',headers={'Authorization':'Bearer '+t['access_token']})
        assert v.status_code==200
        assert v.json()['speaking_goal']==3
        assert 'speaking_today' in v.json()['students'][0]
