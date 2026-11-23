"""Regression checks for safe audio/image uploads and honest failure states."""
import io
import math
import struct
import wave
import uuid

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.scoring import acoustic_features
from app.upload_validation import image_mime, MAX_IMAGE_BYTES
from app.asr import transcribe_audio
from app.gemini import gemini


def test_image_signature_rejects_forged_jpeg():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as raised:
        image_mime(b"<html>not actually a JPEG</html>")
    assert raised.value.status_code == 400


def test_image_signature_accepts_supported_magic():
    assert image_mime(b"\xff\xd8\xff\xe0" + b"0" * 24) == "image/jpeg"
    assert image_mime(b"\x89PNG\r\n\x1a\n" + b"0" * 24) == "image/png"
    assert image_mime(b"RIFF" + b"0" * 4 + b"WEBP" + b"0" * 20) == "image/webp"


def test_oversized_wav_header_rejected_before_decoding():
    # This 46s WAV fits well below 8MB; it must still fail the speaking-duration limit.
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1);wf.setsampwidth(2);wf.setframerate(16000)
        wf.writeframes(b"\x01\x00" * (16000 * 46))
    with pytest.raises(ValueError,match='45 giây'):
        acoustic_features(buf.getvalue())


def test_non_pcm_audio_rejected():
    with pytest.raises(ValueError):
        acoustic_features(b"this is not wav")


def test_invalid_image_is_rejected_before_gemini_call(monkeypatch):
    with TestClient(app) as client:
        logged=client.post('/api/v1/auth/login',json={'email':'student@demo.com','password':'student123'})
        assert logged.status_code == 200
        header={'Authorization':'Bearer '+logged.json()['access_token']}
        monkeypatch.setattr(gemini, 'api_key','dummy-not-real')
        monkeypatch.setattr(gemini,'look_and_speak',lambda *args: (_ for _ in ()).throw(AssertionError('AI must not see invalid image')))
        r=client.post('/api/v1/multimodal/look-speak',headers=header,
          data={'answer':'I can see a cat'},files={'image':('spoof.png',b'<script>alert(1)</script>','image/png')})
        assert r.status_code == 400


def test_image_upload_size_limit_without_large_memory():
    from app.upload_validation import limited_upload
    from starlette.datastructures import UploadFile
    import asyncio
    upload=UploadFile(file=io.BytesIO(b'a'*(1024+1)),filename='a.png')
    with pytest.raises(Exception) as raised:
        asyncio.run(limited_upload(upload,1024,'Ảnh'))
    assert getattr(raised.value,'status_code',None)==413


def test_pronunciation_auth_and_strict_wav():
    with TestClient(app) as client:
        logged=client.post('/api/v1/auth/login',json={'email':'student@demo.com','password':'student123'})
        h={'Authorization':'Bearer '+logged.json()['access_token']}
        lesson=client.get('/api/v1/lessons',headers=h).json()[0]
        r=client.post('/api/v1/pronunciation/analyze',headers=h,data={'lesson_id':lesson['id']},
          files={'audio':('recording.wav',b'not-a-wave','audio/wav')})
        assert r.status_code==400


def test_no_release_label_in_public_page():
    with TestClient(app) as client:
        r=client.get('/')
        assert r.status_code==200
        assert 'V17' not in r.text
        assert 'V16' not in r.text
        assert '<title>BrightSpeakAI' in r.text
