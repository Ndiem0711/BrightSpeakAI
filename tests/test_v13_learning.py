"""V13 behavioural checks. Provider calls are mocked; no AI quality claims."""
import io
import math
import struct
import wave
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import main
from app.adaptive import recommend_lessons
from app.audio_feedback import assess_audio
from app.scoring import score_pronunciation, acoustic_features, validate_speech_signal
from app.ai_errors import provider_error
from app.db import db


def wav(silent=False):
    out=io.BytesIO()
    with wave.open(out,'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000)
        f.writeframes(b''.join(struct.pack('<h',0 if silent else int(5000*math.sin(2*math.pi*220*i/16000))) for i in range(16000)))
    return out.getvalue()


def auth(c,email='student@demo.com',password='student123'):
    response=c.post('/api/v1/auth/login',json={'email':email,'password':password})
    assert response.status_code==200,response.text
    return {'Authorization':'Bearer '+response.json()['access_token']}


def test_word_order_and_missing_words_are_not_perfect():
    features=acoustic_features(wav())
    perfect=score_pronunciation('I like my dog','I like my dog',features)
    reversed_score=score_pronunciation('I like my dog','dog my like I',features)
    missing=score_pronunciation('I like my dog','I like dog',features)
    assert perfect['accuracy']==100
    assert reversed_score['accuracy']<100
    assert missing['completeness']==75
    assert any(w['status']=='omission' and w['expected']=='my' for w in missing['word_alignment'])
    assert perfect['phoneme_assessment'] is False


def test_silence_is_rejected():
    with pytest.raises(ValueError,match='im lặng'):
        validate_speech_signal(acoustic_features(wav(True)))


def test_manual_transcript_is_not_saved_or_counted():
    with TestClient(app) as c:
        h=auth(c)
        lesson=c.get('/api/v1/lessons',headers=h).json()[0]
        before=db.fetchone('SELECT COUNT(*) AS n FROM attempts')['n']
        r=c.post('/api/v1/pronunciation/analyze',headers=h,
            data={'lesson_id':lesson['id'],'demo_transcript':lesson['target_text']},
            files={'audio':('practice.wav',wav(),'audio/wav')})
        assert r.status_code==200,r.text
        assert r.json()['saved'] is False
        assert db.fetchone('SELECT COUNT(*) AS n FROM attempts')['n']==before


def test_real_asr_pipeline_persists_details(monkeypatch):
    monkeypatch.setattr(main,'transcribe_audio',lambda audio:('I like cats','mock-asr-integration'))
    monkeypatch.setattr(main,'AUDIO_FEEDBACK_ENABLED',False)
    with TestClient(app) as c:
        h=auth(c);lesson=c.get('/api/v1/lessons',headers=h).json()[0]
        r=c.post('/api/v1/pronunciation/analyze',headers=h,data={'lesson_id':lesson['id']},
            files={'audio':('practice.wav',wav(),'audio/wav')})
        assert r.status_code==200,r.text
        d=r.json();assert d['saved'] is True
        assert db.fetchone('SELECT * FROM assessment_details WHERE attempt_id=?',(d['attempt_id'],))['method'].endswith('v13')
        db.execute('DELETE FROM attempts WHERE id=?',(d['attempt_id'],))


def test_recommendations_do_not_expose_other_grades_or_teacher_assignments():
    with TestClient(app) as c:
        assert c.get('/api/v1/learning/recommendations').status_code==401
        h=auth(c);allowed={l['id'] for l in c.get('/api/v1/lessons',headers=h).json()}
        r=c.get('/api/v1/learning/recommendations',headers=h)
        assert r.status_code==200
        assert r.json()['items']
        assert all(l['id'] in allowed and l['grade']==3 for l in r.json()['items'])


def test_adaptation_ignores_demo_and_prioritizes_weak_lesson():
    lessons=[{'id':'a','target_text':'I like cats'},{'id':'b','target_text':'Dog'}]
    attempts=[{'lesson_id':'a','overall':40,'ai_mode':'gemini'}]
    assert recommend_lessons(lessons,attempts)[0]['id']=='a'
    attempts[0]['ai_mode']='demo'
    assert recommend_lessons(lessons,attempts)[0]['id']=='b'


def test_admin_diagnostic_is_protected_and_does_not_claim_live_verified(monkeypatch):
    with TestClient(app) as c:
        assert c.post('/api/v1/admin/ai/check',headers=auth(c)).status_code==403
        h=auth(c,'admin@demo.com','admin123')
        monkeypatch.setattr(main.gemini,'api_key','test-not-a-real-key')
        monkeypatch.setattr(main.gemini,'_call',lambda *a:'OK')
        r=c.post('/api/v1/admin/ai/check',headers=h)
        assert r.json()['ok'] is True
        assert r.json()['live_verified'] is False


def test_provider_errors_do_not_expose_payload():
    assert provider_error(404).code=='model_unavailable'
    assert provider_error(429).code=='quota_exceeded'
    assert 'API key' in str(provider_error(401))


def test_audio_feedback_parsing_and_audio_input():
    class Service:
        model='unit-test'
        def _call(self, parts, temperature):
            assert parts[1]['inline_data']['mime_type']=='audio/wav'
            return '{"feedback_vi":"Em hãy nói chậm hơn.","practice_words":["cats"],"uncertain":true}'
    result=assess_audio(Service(),wav(),'I like cats',3)
    assert result['source']=='gemini-audio'
    assert result['uncertain'] is True
    assert result['practice_words']==['cats']


def test_cloud_blocks_manual_scores(monkeypatch):
    monkeypatch.setattr(main,'APP_ENV','cloud')
    with TestClient(app) as c:
        h=auth(c);lesson=c.get('/api/v1/lessons',headers=h).json()[0]
        r=c.post('/api/v1/pronunciation/analyze',headers=h,
            data={'lesson_id':lesson['id'],'demo_transcript':'Hello'},files={'audio':('a.wav',wav(),'audio/wav')})
        assert r.status_code==403
