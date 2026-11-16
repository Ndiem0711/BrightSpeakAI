"""V12: real HTTP RBAC and source-integrity checks. No child's actual voice or camera required."""
from pathlib import Path
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.curriculum import curated_prompts
from app.db import db

ROOT=Path(__file__).resolve().parents[1]

def credentials(client,email,password):
    r=client.post('/api/v1/auth/login',json={'email':email,'password':password})
    assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['access_token']}

def test_curriculum_105_prompt_grade_scopes():
    prompts=curated_prompts()
    assert len(prompts)==105
    assert {p['grade'] for p in prompts}=={1,2,3,4,5}
    assert len({p['id'] for p in prompts})==len(prompts)
    assert all(p['question'] and p['sample_answer'] and p['unit_title'] for p in prompts)
    with TestClient(app) as c:
        student=credentials(c,'student@demo.com','student123')
        r=c.get('/api/v1/live/prompts',headers=student)
        assert r.status_code==200,r.text
        assert all(p['grade']==3 for p in r.json()['prompts'])
        assert c.get('/api/v1/live/prompts').status_code==401
        grade=c.get('/api/v1/lessons?grade=5',headers=student)
        assert grade.status_code==200
        assert all(x['grade']==3 for x in grade.json())

def test_teacher_create_assign_update_disable_with_backend_access():
    with TestClient(app) as c:
        admin=credentials(c,'admin@demo.com','admin123')
        teacher=credentials(c,'teacher@demo.com','teacher123')
        student=credentials(c,'student@demo.com','student123')
        other=f'other-{uuid.uuid4().hex[:8]}@example.test'
        response=c.post('/api/v1/admin/users',headers=admin,json={'email':other,'full_name':'Test learner','password':'safeTestPass123','role':'student','grade':3})
        assert response.status_code==201,response.text
        other_user=response.json()['user']['id']
        foreign=credentials(c,other,'safeTestPass123')
        payload={'grade':3,'topic':'My pets','target_text':'My cat is white.', 'hint':'Slowly read and repeat.', 'student_ids':['demo-student']}
        res=c.post('/api/v1/teacher/lessons',headers=teacher,json=payload)
        assert res.status_code==201,res.text
        lid=res.json()['id']
        assert lid.startswith('GV-')
        assert c.post('/api/v1/teacher/lessons',headers=student,json=payload).status_code==403
        assert c.post('/api/v1/teacher/lessons',headers=teacher,json={**payload,'student_ids':[other_user]}).status_code==403
        assert c.post('/api/v1/teacher/lessons',headers=teacher,json={**payload,'target_text':'a '*40}).status_code==422
        own=c.get('/api/v1/teacher/lessons',headers=teacher)
        assert own.status_code==200 and lid in {x['id'] for x in own.json()['lessons']}
        visible=c.get('/api/v1/lessons',headers=student).json()
        assert lid in [x['id'] for x in visible]
        hidden=c.get('/api/v1/lessons',headers=foreign).json()
        assert lid not in [x['id'] for x in hidden]
        live=c.get('/api/v1/live/prompts',headers=student).json()['prompts']
        assert any(p['id']=='TEACHER:'+lid for p in live)
        foreign_live=c.get('/api/v1/live/prompts',headers=foreign).json()['prompts']
        assert all(p['id']!='TEACHER:'+lid for p in foreign_live)
        changed=c.put('/api/v1/teacher/lessons/'+lid,headers=teacher,json={**payload,'target_text':'I like my dog.'})
        assert changed.status_code==200,changed.text
        assert any(x['target_text']=='I like my dog.' for x in c.get('/api/v1/lessons',headers=student).json())
        assert c.delete('/api/v1/teacher/lessons/'+lid,headers=teacher).status_code==200
        assert lid not in [x['id'] for x in c.get('/api/v1/lessons',headers=student).json()]

def test_v12_ui_and_audio_fallback_implementation():
    js=(ROOT/'app/static/features.js').read_text(encoding='utf-8')
    live=(ROOT/'app/live.py').read_text(encoding='utf-8')
    assert 'loadLivePrompts()' in js
    assert "api('/api/v1/live/prompts')" in js
    assert 'speakLiveFallback' in js
    assert "if(!d.had_audio&&!liveLastAudioTurn && aiText)" in js
    assert "liveWS.send(JSON.stringify({type:'practice_prompt'" in js
    assert "msg.get('type') == 'practice_prompt'" in live
    assert 'model_transcription_seen' in live
    assert 'teacher_access_to_student' in (ROOT/'app/main.py').read_text()
    assert 'renderTeacher=renderTeacherV12' in js
    assert 'V11' not in (ROOT/'HUONG_DAN_V12.txt').read_text(encoding='utf-8') if (ROOT/'HUONG_DAN_V12.txt').exists() else True
