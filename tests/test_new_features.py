from __future__ import annotations
import os
import uuid
import math
import io
import struct
import wave
os.environ["DATABASE_URL"] = "sqlite:///runtime/test_bright.db"
os.environ["DEMO_OTP"] = "true"
os.environ["GEMINI_API_KEY"] = ""

from fastapi.testclient import TestClient
from app.main import app


def wav():
    bf=io.BytesIO()
    with wave.open(bf,'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000)
        w.writeframes(b''.join(struct.pack('<h',int(7000*math.sin(2*math.pi*i/75))) for i in range(16000)))
    return bf.getvalue()


def auth(c, who='student'):
    d=c.post('/api/v1/auth/login',json={'email':f'{who}@demo.com','password':f'{who}123'}).json()
    return {'Authorization':'Bearer '+d['access_token']}


def test_edit_profile_and_grade_and_self_only():
    with TestClient(app) as c:
        h=auth(c)
        d=c.patch('/api/v1/profile',headers=h,json={'full_name':'Tuan Test','grade':4})
        assert d.status_code==200,d.text
        assert d.json()['full_name']=='Tuan Test'
        assert d.json()['grade']==4
        assert c.get('/api/v1/auth/me',headers=h).json()['grade']==4
        assert c.patch('/api/v1/profile',json={'full_name':'Invalid','grade':3}).status_code==401
        c.patch('/api/v1/profile',headers=h,json={'full_name':'Minh Anh','grade':3})


def test_profile_password_rejects_bad_old_password():
    with TestClient(app) as c:
        h=auth(c)
        r=c.post('/api/v1/profile/password',headers=h,json={'current_password':'wrong','new_password':'somepassword8','confirm_password':'somepassword8'})
        assert r.status_code==400


def test_live_access_requires_auth():
    with TestClient(app) as c:
        with c.websocket_connect('/api/v1/live/ws') as sock:
            sock.send_json({'type':'init','access_token':'invalid','topic':'Animals','video_consent':False})
            assert sock.receive_json()['type']=='error'


def test_student_voice_requires_real_asr():
    with TestClient(app) as c:
        r=c.post('/api/v1/conversation/voice',headers=auth(c),data={'topic':'Animals'},files={'audio':('a.wav',wav(),'audio/wav')})
        assert r.status_code==503


def test_look_audio_rejects_fake_asr_not_score():
    with TestClient(app) as c:
        r=c.post('/api/v1/multimodal/look-speak',headers=auth(c),files={
            'audio':('a.wav',wav(),'audio/wav'),
            'image':('p.png',b'\x89PNG\r\n\x1a\n','image/png')})
        assert r.status_code==503
        assert 'score' not in r.json()


def test_topic_bank_and_teacher_student_scoping():
    with TestClient(app) as c:
        topic=c.get('/api/v1/conversation/topics',headers=auth(c))
        assert topic.status_code==200 and topic.json()['topics']
        teacher=c.get('/api/v1/teacher/overview',headers=auth(c,'teacher'))
        assert teacher.status_code==200
        assert any(u['email']=='student@demo.com' for u in teacher.json()['students'])
        assert all('password' not in u for u in teacher.json()['students'])


def test_admin_can_assign_student_to_teacher():
    with TestClient(app) as c:
        admin=auth(c,'admin')
        r=c.post('/api/v1/admin/teacher-students',headers=admin,data={
            'teacher_id':'demo-teacher','student_id':'demo-student'})
        assert r.status_code==200
        reject=c.post('/api/v1/admin/teacher-students',headers=auth(c),data={
            'teacher_id':'demo-teacher','student_id':'demo-student'})
        assert reject.status_code==403


def test_real_gemini_branch_with_mock(monkeypatch):
    import app.main as m
    with TestClient(app) as c:
        class StubAI:
            enabled=True
            def look_and_speak(self, image,mime,answer,grade):
                assert answer == 'I can see a dog.'
                return {'score':79,'feedback':'Good description','model_sentence':'This is a dog.', 'next_question':'What colour is it?'}
        monkeypatch.setattr(m,'gemini',StubAI())
        monkeypatch.setattr(m,'transcribe_audio',lambda b:('I can see a dog.','whisper-dl'))
        data=c.post('/api/v1/multimodal/look-speak',headers=auth(c),files={
            'image':('test.png',b'\x89PNG\r\n\x1a\n','image/png'),
            'audio':('a.wav',wav(),'audio/wav')})
        assert data.status_code==200,data.text
        assert data.json()['voice_mode']=='whisper-dl'
        assert data.json()['transcript']=='I can see a dog.'
        assert data.json()['score']==79
