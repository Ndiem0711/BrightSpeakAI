from __future__ import annotations

import io
import math
import os
import struct
import uuid
import wave
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///runtime/test_bright.db"
os.environ["DEMO_OTP"] = "true"
os.environ["GEMINI_API_KEY"] = ""

from fastapi.testclient import TestClient
from app.main import app


def wav_bytes(seconds: float = 1.1, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        frames = bytearray()
        for i in range(int(seconds * rate)):
            value = int(7000 * math.sin(2 * math.pi * 220 * i / rate))
            frames += struct.pack("<h", value)
        wf.writeframes(frames)
    return buf.getvalue()


def login(client: TestClient, email: str, password: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_health_and_login():
    with TestClient(app) as client:
        h = client.get("/api/v1/system/health")
        assert h.status_code == 200
        assert h.json()["app"] == "BrightSpeak AI"
        data = login(client, "student@demo.com", "student123")
        assert data["user"]["role"] == "student"
        assert data["access_token"]
        assert data["refresh_token"]


def test_register_verify_and_wrong_otp():
    with TestClient(app) as client:
        email = f"student-{uuid.uuid4().hex[:8]}@example.com"
        reg = client.post("/api/v1/auth/register", json={
            "full_name": "Test Student", "email": email, "password": "password123", "grade": 4
        })
        assert reg.status_code == 201, reg.text
        code = reg.json()["demo_otp"]
        wrong = client.post("/api/v1/auth/verify", json={"email": email, "code": "000000" if code != "000000" else "111111"})
        assert wrong.status_code == 400
        ok = client.post("/api/v1/auth/verify", json={"email": email, "code": code})
        assert ok.status_code == 200, ok.text
        assert ok.json()["user"]["verified"] is True


def test_pronunciation_progress_and_role_protection():
    with TestClient(app) as client:
        student = login(client, "student@demo.com", "student123")
        headers = auth_header(student["access_token"])
        lessons = client.get("/api/v1/lessons", headers=headers)
        assert lessons.status_code == 200
        lesson = lessons.json()[0]
        result = client.post(
            "/api/v1/pronunciation/analyze",
            headers=headers,
            data={"lesson_id": lesson["id"], "demo_transcript": lesson["target_text"]},
            files={"audio": ("recording.wav", wav_bytes(), "audio/wav")},
        )
        assert result.status_code == 200, result.text
        payload = result.json()
        assert 0 <= payload["scores"]["overall"] <= 100
        progress = client.get("/api/v1/progress/me", headers=headers)
        assert progress.status_code == 200
        assert payload["saved"] is False
        assert payload.get("attempt_id") is None
        forbidden = client.get("/api/v1/admin/overview", headers=headers)
        assert forbidden.status_code == 403


def test_teacher_and_admin_dashboards():
    with TestClient(app) as client:
        teacher = login(client, "teacher@demo.com", "teacher123")
        t = client.get("/api/v1/teacher/overview", headers=auth_header(teacher["access_token"]))
        assert t.status_code == 200
        assert "students" in t.json()
        admin = login(client, "admin@demo.com", "admin123")
        a = client.get("/api/v1/admin/overview", headers=auth_header(admin["access_token"]))
        assert a.status_code == 200
        assert a.json()["lesson_count"] >= 10


def test_look_speak_demo_path():
    with TestClient(app) as client:
        student = login(client, "student@demo.com", "student123")
        r = client.post(
            "/api/v1/multimodal/look-speak",
            headers=auth_header(student["access_token"]),
            data={"answer": "I can see a dog in the park."},
            files={"image": ("test.jpg", b"fake-jpeg-demo-bytes", "image/jpeg")},
        )
        assert r.status_code == 503, r.text  # no Gemini key: must not invent a picture score
        assert "Gemini API key" in r.json()["detail"]


def test_refresh_token_flow():
    with TestClient(app) as client:
        student = login(client, "student@demo.com", "student123")
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": student["refresh_token"]})
        assert r.status_code == 200, r.text
        assert r.json()["access_token"]


def test_invalid_audio_exception_path():
    with TestClient(app) as client:
        student = login(client, "student@demo.com", "student123")
        headers = auth_header(student["access_token"])
        lesson = client.get("/api/v1/lessons", headers=headers).json()[0]
        r = client.post(
            "/api/v1/pronunciation/analyze",
            headers=headers,
            data={"lesson_id": lesson["id"], "demo_transcript": "hello"},
            files={"audio": ("bad.wav", b"not-a-wave", "audio/wav")},
        )
        assert r.status_code == 400
        assert "WAV" in r.json()["detail"]


def test_admin_lesson_crud_guardrails():
    with TestClient(app) as client:
        admin = login(client, "admin@demo.com", "admin123")
        headers = auth_header(admin["access_token"])
        lesson_id = f"TEST-{uuid.uuid4().hex[:8]}"
        body = {"id": lesson_id, "grade": 5, "topic": "Test topic", "target_text": "This is a stable test lesson.", "hint": "Test", "focus_sound": "t"}
        first = client.post("/api/v1/admin/lessons", headers=headers, json=body)
        assert first.status_code == 201, first.text
        duplicate = client.post("/api/v1/admin/lessons", headers=headers, json=body)
        assert duplicate.status_code == 409
