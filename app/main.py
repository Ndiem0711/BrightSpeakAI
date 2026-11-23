from __future__ import annotations

import mimetypes
import json
import time
import re
import smtplib
import uuid
from contextlib import asynccontextmanager
from datetime import timedelta
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import (
    create_token,
    decode_token,
    get_current_user,
    hash_password,
    iso_now,
    require_roles,
    token_pair,
    utcnow,
    verify_password,
)
from .config import (
    APP_ENV,
    GEMINI_MODEL,
    ROOT_DIR,
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USERNAME,
    PUBLIC_BASE_URL,
)
from .db import db
from .daily import daily_goal, record_spoken_turn
from .gemini import gemini
from .ai_errors import AIServiceError
from .scoring import acoustic_features, score_pronunciation, validate_speech_signal
from .adaptive import recommend_lessons
from .audio_feedback import assess_audio
from .config import AUDIO_FEEDBACK_ENABLED, GEMINI_LIVE_MODEL, REGISTRATION_MODE
from starlette.concurrency import run_in_threadpool
from .asr import transcribe_audio, ASRUnavailable
from .seed import seed_defaults
from .storage import upload_bytes
from .upload_validation import limited_upload, image_mime, MAX_WAV_BYTES, MAX_IMAGE_BYTES
from .mailer import email_ready, send_transactional_email
from . import captcha

@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_schema()
    seed_defaults()
    yield


app = FastAPI(
    title="BrightSpeakAI",
    version="20.0.0",
    description="Multimodal AI English pronunciation and speaking practice for primary learners.",
    lifespan=lifespan,
)

STATIC_DIR = ROOT_DIR / "app" / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")



class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    grade: int = Field(ge=1, le=5)
    confirm_password: str | None = None
    guardian_confirmed: bool = False
    captcha_id: str = Field(min_length=20, max_length=80)
    captcha_code: str = Field(min_length=5, max_length=12)


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ConversationRequest(BaseModel):
    topic: str = Field(default="Daily life", min_length=2, max_length=80)
    text: str = Field(min_length=1, max_length=500)


class LessonCreateRequest(BaseModel):
    id: str = Field(min_length=3, max_length=40)
    grade: int = Field(ge=1, le=5)
    topic: str = Field(min_length=2, max_length=80)
    target_text: str = Field(min_length=2, max_length=300)
    hint: str = Field(default="", max_length=300)
    focus_sound: str = Field(default="", max_length=30)


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "role": user["role"],
        "grade": user.get("grade"),
        "verified": bool(user["verified"]),
        "email_verified": bool(user.get("email_verified", 0)),
        "active": bool(user["active"]),
    }


def _issue_account_link(user_id: str, purpose: str, *, lifetime_minutes: int = 30) -> str:
    """Save only SHA-256 of an unguessable bearer token; never log raw tokens."""
    import hashlib
    import secrets
    token = secrets.token_urlsafe(40)
    db.execute(
        "INSERT INTO account_links(id,user_id,token_hash,purpose,expires_at,used,created_at) "
        "VALUES(?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), user_id, hashlib.sha256(token.encode('utf-8')).hexdigest(),
         purpose, (utcnow() + timedelta(minutes=lifetime_minutes)).isoformat(), 0, iso_now()),
    )
    return token


def _revoke_account_link(token: str) -> None:
    import hashlib
    db.execute("UPDATE account_links SET used=1 WHERE token_hash=?",
               (hashlib.sha256(token.encode('utf-8')).hexdigest(),))


def _link_url(token: str) -> str:
    from urllib.parse import quote
    return PUBLIC_BASE_URL.rstrip('/') + '/?account_token=' + quote(token, safe='')


def _find_account_link(token: str) -> dict[str, Any] | None:
    import hashlib
    if len(token) < 24 or len(token) > 256:
        return None
    row = db.fetchone("SELECT * FROM account_links WHERE token_hash=? AND used=0",
                      (hashlib.sha256(token.encode('utf-8')).hexdigest(),))
    if not row:
        return None
    try:
        if datetime.fromisoformat(row['expires_at']) <= utcnow():
            return None
    except (ValueError, TypeError):
        return None
    return row


class RequestPasswordReset(BaseModel):
    email: str = Field(min_length=5, max_length=120)


class CompletePasswordReset(BaseModel):
    token: str = Field(min_length=24, max_length=256)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)


@app.post('/api/v1/auth/password/forgot')
def request_password_reset(payload: RequestPasswordReset) -> dict[str, str]:
    # An explicit unavailable status is preferable to pretending a mail was sent.
    if not email_ready():
        raise HTTPException(status_code=503, detail='Chưa cấu hình dịch vụ gửi email. Hãy liên hệ quản trị viên.')
    email = payload.email.strip().lower()
    user = db.fetchone('SELECT * FROM users WHERE email=? AND active=1', (email,))
    if user:
        recent = db.fetchone('SELECT COUNT(*) AS n FROM account_links WHERE user_id=? AND purpose=? AND created_at>?',
                             (user['id'], 'reset', (utcnow()-timedelta(hours=1)).isoformat()))
        if recent and int(recent['n']) < 3:
            token = _issue_account_link(user['id'], 'reset', lifetime_minutes=20)
            sent = send_transactional_email(
                email, 'BrightSpeakAI – Đặt lại mật khẩu',
                'Có yêu cầu đặt lại mật khẩu cho tài khoản BrightSpeakAI.\n'
                'Mở đường dẫn này trong 20 phút: ' + _link_url(token) + '\n'
                'Nếu bạn không yêu cầu, hãy bỏ qua email này. Không chuyển tiếp đường dẫn.',
            )
            if not sent:
                _revoke_account_link(token)
                # Do not reveal whether email exists, including on provider errors.
    return {'message': 'Nếu email tồn tại, hệ thống sẽ gửi liên kết đặt lại mật khẩu.'}


@app.get('/api/v1/auth/password/link-info')
def password_link_info(token: str) -> dict[str, str]:
    row = _find_account_link(token)
    if not row or row['purpose'] not in ('reset', 'invite'):
        raise HTTPException(status_code=400, detail='Liên kết không hợp lệ hoặc đã hết hạn')
    return {'purpose': row['purpose']}


@app.post('/api/v1/auth/password/complete')
def complete_password_reset(payload: CompletePasswordReset) -> dict[str, str]:
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=422, detail='Hai lần nhập mật khẩu mới không trùng khớp')
    row = _find_account_link(payload.token)
    if not row or row['purpose'] not in ('reset', 'invite'):
        raise HTTPException(status_code=400, detail='Liên kết không hợp lệ, hết hạn hoặc đã sử dụng')
    user = db.fetchone('SELECT * FROM users WHERE id=? AND active=1', (row['user_id'],))
    if not user:
        raise HTTPException(status_code=400, detail='Tài khoản không còn khả dụng')
    db.execute('UPDATE users SET password_hash=?, verified=1, token_version=token_version+1 WHERE id=?',
               (hash_password(payload.new_password), row['user_id']))
    db.execute('UPDATE account_links SET used=1 WHERE user_id=?', (row['user_id'],))
    return {'message': 'Đã thiết lập mật khẩu. Bạn có thể đăng nhập.'}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/v1/system/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "app": "BrightSpeak AI",
        "version": "20.0.0",
        "environment": APP_ENV,
        "gemini_enabled": gemini.enabled,
        "email_enabled": email_ready(),
        "registration_mode": REGISTRATION_MODE,
        "captcha_required": True,
        "gemini_model": GEMINI_MODEL,
        "local_asr_available": False,
        "asr_provider": transcribe_audio.provider(),
        "live_enabled": gemini.enabled,
    }


@app.get('/api/v1/auth/captcha')
def registration_captcha(request: Request) -> dict[str, Any]:
    from fastapi.responses import JSONResponse
    # Public route. Image is rasterized; challenge answer never enters the response.
    response = captcha.new_challenge(request.client.host if request.client else 'unknown')
    return JSONResponse(response, headers={'Cache-Control': 'no-store, private'})


@app.post("/api/v1/auth/register", status_code=201)
def register(payload: RegisterRequest) -> dict[str, Any]:
    # CAPTCHA must be validated on the server. Never rely on a frontend-only field.
    captcha.consume(payload.captcha_id, payload.captcha_code)
    email = payload.email.strip().lower()
    if payload.confirm_password is not None and payload.confirm_password != payload.password:
        raise HTTPException(status_code=422, detail='Hai mật khẩu không trùng khớp')
    if not payload.guardian_confirmed:
        raise HTTPException(status_code=422, detail='Cần có sự đồng ý của người giám hộ trước khi đăng ký cho trẻ')
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail='Email không hợp lệ')
    existing = db.fetchone("SELECT * FROM users WHERE email = ?", (email,))
    if existing:
        # Allow resuming ONLY a pending student account with its original password.
        if (existing['role'] == 'student' and not existing['verified']
                and existing['active'] and verify_password(payload.password, existing['password_hash'])):
            db.execute('UPDATE users SET verified=1 WHERE id=?', (existing['id'],))
            existing['verified'] = 1
            return {'message': 'Tài khoản đã được kích hoạt. Em có thể bắt đầu luyện tập.',
                    'requires_verification': False, 'email_verified': False,
                    'user': public_user(existing), **token_pair(existing)}
        raise HTTPException(status_code=409, detail='Email này đã được sử dụng. Hãy đăng nhập hoặc dùng email khác.')
    user_id = str(uuid.uuid4())
    db.execute('INSERT INTO users(id,email,password_hash,full_name,role,grade,verified,active,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
               (user_id,email,hash_password(payload.password),payload.full_name.strip(),
                'student',payload.grade,1,1,iso_now()))
    user = db.fetchone('SELECT * FROM users WHERE id=?',(user_id,))
    return {'message': 'Đăng ký thành công! Em có thể bắt đầu luyện tập.',
            'requires_verification': False, 'email_verified': False,
            'user': public_user(user), **token_pair(user)}


@app.post("/api/v1/auth/login")
def login(payload: LoginRequest) -> dict[str, Any]:
    user = db.fetchone("SELECT * FROM users WHERE email = ?", (payload.email.strip().lower(),))
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu chưa đúng.")
    if not int(user["active"]):
        raise HTTPException(status_code=403, detail="Tài khoản đang bị khóa. Hãy liên hệ quản trị viên.")
    if not int(user["verified"]):
        raise HTTPException(status_code=403, detail="Tài khoản chưa được kích hoạt. Hãy liên hệ quản trị viên.")
    return {"user": public_user(user), **token_pair(user)}


@app.post("/api/v1/auth/refresh")
def refresh(payload: RefreshRequest) -> dict[str, Any]:
    decoded = decode_token(payload.refresh_token, "refresh")
    user = db.fetchone("SELECT * FROM users WHERE id = ?", (decoded["sub"],))
    if not user or not int(user["active"]):
        raise HTTPException(status_code=401, detail="Account unavailable")
    if int(decoded.get('pv', 0)) != int(user.get('token_version', 0)):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")
    return {"access_token": create_token(user, "access"), "token_type": "bearer"}


@app.get("/api/v1/auth/me")
def me(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return public_user(user)


@app.get("/api/v1/lessons")
def lessons(
    grade: int | None = None,
    user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    # Students must not retrieve exercises from higher grades or other teachers.
    selected_grade = int(user.get('grade') or 3) if user['role'] == 'student' else int(grade or user.get('grade') or 3)
    if selected_grade not in range(1,6):
        raise HTTPException(status_code=422, detail='Grade must be from 1 to 5')
    if user['role'] == 'student':
        return db.fetchall("""SELECT l.id,l.grade,l.topic,l.target_text,l.hint,l.focus_sound
            FROM lessons l WHERE l.grade=? AND l.active=1
            AND (l.owner_teacher_id IS NULL OR EXISTS
                 (SELECT 1 FROM teacher_lesson_assignments a WHERE a.lesson_id=l.id AND a.student_id=?))
            ORDER BY l.topic,l.id""", (selected_grade, user['id']))
    if user['role'] == 'teacher':
        return db.fetchall("""SELECT id,grade,topic,target_text,hint,focus_sound
            FROM lessons WHERE grade=? AND active=1 AND (owner_teacher_id IS NULL OR owner_teacher_id=?)
            ORDER BY topic,id""", (selected_grade,user['id']))
    return db.fetchall(
        "SELECT id,grade,topic,target_text,hint,focus_sound FROM lessons WHERE grade = ? AND active = 1 ORDER BY topic,id",
        (selected_grade,),
    )


@app.post("/api/v1/pronunciation/analyze")
async def analyze_pronunciation(
    lesson_id: str = Form(...),
    demo_transcript: str = Form(""),
    audio: UploadFile = File(...),
    user: dict[str, Any] = Depends(require_roles("student")),
) -> dict[str, Any]:
    lesson = db.fetchone("SELECT * FROM lessons WHERE id = ? AND active = 1", (lesson_id,))
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    if int(lesson['grade']) != int(user.get('grade') or 3):
        raise HTTPException(status_code=404, detail='Lesson not found for this grade')
    if lesson.get('owner_teacher_id') and not db.fetchone(
        'SELECT 1 AS ok FROM teacher_lesson_assignments WHERE lesson_id=? AND student_id=?',
        (lesson_id,user['id'])
    ):
        raise HTTPException(status_code=404, detail='Lesson was not assigned to this student')
    started = time.perf_counter()
    wav_bytes = await limited_upload(audio, MAX_WAV_BYTES, "Bản ghi âm")
    try:
        features = acoustic_features(wav_bytes)
        validate_speech_signal(features)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Never pretend a target sentence was recognised. Explicit demo text is only for technical checks.
    if APP_ENV == 'cloud' and demo_transcript.strip():
        raise HTTPException(status_code=403, detail='Kiểm thử transcript thủ công chỉ dùng khi chạy local.')
    transcript = demo_transcript.strip()
    ai_mode = "demo" if transcript else "unavailable"
    ai_note = "Manual test transcript; the displayed score is NOT real voice recognition."
    if not transcript:
        try:
            transcript, ai_mode = await run_in_threadpool(transcribe_audio, wav_bytes)
            ai_note = f"Speech recognised by {ai_mode}; score is a rule-based practice indicator."
        except ASRUnavailable as exc:
            status = 429 if exc.code == "quota_exceeded" else 502 if exc.code in ("invalid_response", "model_unavailable") else 503
            raise HTTPException(status_code=status, detail=str(exc)) from None
    if not transcript.strip():
        raise HTTPException(status_code=422, detail="Không nghe được câu nói. Hãy ghi âm lại ở nơi yên tĩnh.")

    scores = score_pronunciation(lesson["target_text"], transcript, features)
    audio_feedback = None
    if ai_mode != 'demo' and AUDIO_FEEDBACK_ENABLED and gemini.enabled:
        try:
            audio_feedback = await run_in_threadpool(assess_audio, gemini, wav_bytes,
                lesson['target_text'], int(user.get('grade') or 3))
        except Exception:
            audio_feedback = {'source': 'unavailable', 'feedback_vi':
                'Chưa lấy được nhận xét từ bản ghi. Em có thể thử lại hoặc nhờ GV nghe giúp.',
                'uncertain': True, 'practice_words': []}
    # Manual transcripts must never contaminate the student's progress/history.
    if ai_mode == 'demo':
        return {'attempt_id': None, 'saved': False, 'lesson': lesson, 'transcript': transcript,
            'scores': scores, 'acoustic': features, 'ai_mode': ai_mode, 'ai_note': ai_note,
            'audio_feedback': None, 'keyword_ml': None,
            'latency_ms': round((time.perf_counter() - started) * 1000)}

    # Audio is not stored by default. Use an explicit consent-based recording policy if needed.
    attempt_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO attempts(id,user_id,lesson_id,transcript,accuracy,fluency,completeness,prosody,overall,duration,ai_mode,feedback,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            attempt_id, user["id"], lesson_id, transcript, scores["accuracy"], scores["fluency"],
            scores["completeness"], scores["prosody"], scores["overall"], features["duration"],
            ai_mode, scores["feedback"], iso_now(),
        ),
    )
    db.execute('INSERT INTO assessment_details(attempt_id,method,alignment_json,feedback_json) VALUES(?,?,?,?)',
        (attempt_id, scores['assessment_method'], json.dumps(scores['word_alignment']),
         json.dumps(audio_feedback, ensure_ascii=False)))
    # Optional real ML word classifier trained on Google Speech Commands.
    # It does not replace pronunciation scores or imply child-speech validity.
    keyword_ml = None
    try:
        from ml.keyword_inference import predict_keyword
        if len(lesson['target_text'].split()) == 1:
            keyword_ml = predict_keyword(wav_bytes)
    except Exception:
        keyword_ml = None
    return {
        "saved": True,
        "audio_feedback": audio_feedback,
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "keyword_ml": keyword_ml,
        "attempt_id": attempt_id,
        "lesson": {"id": lesson["id"], "target_text": lesson["target_text"], "topic": lesson["topic"]},
        "transcript": transcript,
        "scores": scores,
        "acoustic": features,
        "ai_mode": ai_mode,
        "ai_note": ai_note,
    }


@app.post("/api/v1/conversation/message")
def conversation(
    payload: ConversationRequest,
    user: dict[str, Any] = Depends(require_roles("student")),
) -> dict[str, Any]:
    grade = int(user.get("grade") or 3)
    if not gemini.enabled:
        raise HTTPException(status_code=503, detail="Hội thoại AI cần Gemini API key. Hãy nhập key trong PowerShell và khởi động lại.")
    try:
        recent = db.fetchall(
            "SELECT user_text,ai_text FROM conversation_logs WHERE user_id=? AND topic=? ORDER BY created_at DESC LIMIT 5",
            (user["id"], payload.topic),
        )
        reply = gemini.conversation_reply(grade, payload.topic, payload.text, list(reversed(recent)))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Không thể kết nối Gemini: {str(exc)[:220]}") from exc
    db.execute(
        "INSERT INTO conversation_logs(id,user_id,topic,user_text,ai_text,ai_mode,created_at) VALUES(?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), user["id"], payload.topic, payload.text, reply, "gemini", iso_now()),
    )
    return {"reply": reply, "ai_mode": "gemini"}


@app.post("/api/v1/conversation/voice")
async def conversation_voice(
    topic: str = Form("Daily life"),
    audio: UploadFile = File(...),
    user: dict[str, Any] = Depends(require_roles("student")),
) -> dict[str, Any]:
    if not gemini.enabled:
        raise HTTPException(status_code=503, detail="Nói với AI cần Gemini API key; mở GEMINI_KEY.txt, dán key và chạy lại START-BRIGHTSPEAK.bat.")
    blob = await limited_upload(audio, MAX_WAV_BYTES, "Bản ghi âm")
    try:
        validate_speech_signal(acoustic_features(blob))
        spoken, asr_mode = await run_in_threadpool(transcribe_audio, blob)
        if not spoken.strip():
            raise ValueError("Không nhận ra giọng nói, hãy thử lại")
        grade = int(user.get("grade") or 3)
        reply = await run_in_threadpool(gemini.conversation_reply, grade, topic[:80], spoken)
    except (ASRUnavailable, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Dịch vụ hội thoại AI đang gặp lỗi. Vui lòng thử lại sau.") from exc
    db.execute(
        "INSERT INTO conversation_logs(id,user_id,topic,user_text,ai_text,ai_mode,created_at) VALUES(?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), user["id"], topic[:80], spoken, reply, "gemini", iso_now()),
    )
    goal = record_spoken_turn(user["id"], "voice_chat", spoken)
    return {"transcript": spoken, "reply": reply, "ai_mode": "gemini", "asr_mode": asr_mode, "daily_goal": goal}


@app.post("/api/v1/multimodal/look-speak")
async def look_speak(
    answer: str = Form(""),
    image: UploadFile = File(...),
    audio: UploadFile | None = File(None),
    user: dict[str, Any] = Depends(require_roles("student")),
) -> dict[str, Any]:
    started = time.perf_counter()
    answer = answer.strip()
    voice_mode = "typed"
    wav_bytes = None
    if audio is not None:
        wav_bytes = await limited_upload(audio, MAX_WAV_BYTES, "Bản ghi âm")
        try:
            validate_speech_signal(acoustic_features(wav_bytes))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        voice_mode = "gemini"
    if wav_bytes is None and not answer:
        raise HTTPException(status_code=400, detail="Hãy ghi âm hoặc nhập câu mô tả tranh")
    image_bytes = await limited_upload(image, MAX_IMAGE_BYTES, "Hình ảnh")
    mime = image_mime(image_bytes)
    if not gemini.enabled:
        raise HTTPException(status_code=503, detail="Chưa có Gemini API key để nhận dạng và phân tích tranh.")
    try:
        if wav_bytes is not None:
            # One audio+image request replaces V20's two serial Gemini calls.
            result = await run_in_threadpool(gemini.look_and_speak_audio,
                image_bytes, mime, wav_bytes, int(user.get("grade") or 3))
            answer = result["transcript"]
        else:
            result = await run_in_threadpool(gemini.look_and_speak,
                image_bytes, mime, answer, int(user.get("grade") or 3))
    except AIServiceError as exc:
        status = 429 if exc.code == "quota_exceeded" else 503 if exc.code in ("provider_unavailable", "network_error") else 422 if exc.code == "no_speech" else 502
        raise HTTPException(status_code=status, detail=str(exc)) from None
    except Exception:
        raise HTTPException(status_code=502, detail="Gemini chưa xử lí được lượt luyện này. Hãy thử lại hoặc kiểm tra kết nối.") from None
    db.execute(
        "INSERT INTO look_speak_logs(id,user_id,answer_text,score,feedback,ai_mode,created_at) VALUES(?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), user["id"], answer, result["score"], result["feedback"], "gemini", iso_now()),
    )
    goal = record_spoken_turn(user["id"], "look_speak", answer) if audio is not None else daily_goal(user["id"])
    return {**result, "ai_mode": "gemini", "transcript": answer, "voice_mode": voice_mode,
            "daily_goal": goal,
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "note": "Mức phù hợp nội dung do Gemini đề xuất, không phải điểm phát âm được kiểm định."}


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=80)
    grade: int | None = Field(default=None, ge=1, le=5)


class AdminUserCreate(BaseModel):
    """Administrator-managed account creation with explicit passwords, no email OTP."""
    full_name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=120)
    password: str = Field(min_length=12, max_length=128)
    role: str = Field(default="student", pattern="^(student|teacher)$")
    grade: int | None = Field(default=None, ge=1, le=5)
    guardian_confirmed: bool = False


class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)


@app.patch("/api/v1/profile")
def update_profile(payload: ProfileUpdate, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    new_grade = payload.grade if user["role"] == "student" else None
    db.execute("UPDATE users SET full_name=?, grade=? WHERE id=?", (payload.full_name.strip(), new_grade, user["id"]))
    updated = db.fetchone("SELECT * FROM users WHERE id=?", (user["id"],))
    return public_user(updated)


@app.post("/api/v1/profile/password")
def update_password(payload: PasswordUpdate, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, str]:
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=422, detail='Hai mật khẩu mới không trùng khớp')
    if not verify_password(payload.current_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không đúng")
    if verify_password(payload.new_password, user['password_hash']):
        raise HTTPException(status_code=422, detail='Mật khẩu mới cần khác mật khẩu cũ')
    db.execute("UPDATE users SET password_hash=?, token_version=token_version+1 WHERE id=?", (hash_password(payload.new_password), user["id"]))
    db.execute('UPDATE account_links SET used=1 WHERE user_id=?', (user['id'],))
    return {"message": "Đã cập nhật mật khẩu"}


@app.get("/api/v1/curriculum/books")
def curriculum_books(user: dict[str, Any] = Depends(require_roles("student"))):
    from .curriculum import prompts_for_student, source_books
    names = {p.get("book") for p in prompts_for_student(user)}
    return [book for book in source_books() if book["name"] in names]


@app.get("/api/v1/conversation/topics")
def conversation_topics(user: dict[str, Any] = Depends(require_roles("student"))) -> dict[str, Any]:
    grade = int(user.get("grade") or 3)
    rows = db.fetchall("""SELECT DISTINCT l.topic FROM lessons l WHERE l.grade=? AND l.active=1
        AND (l.owner_teacher_id IS NULL OR EXISTS
             (SELECT 1 FROM teacher_lesson_assignments a WHERE a.lesson_id=l.id AND a.student_id=?))
        ORDER BY l.topic""",(grade,user['id']))
    topics = [r["topic"] for r in rows]
    return {"grade": grade, "topics": topics, "custom_topic_enabled": True}


@app.get("/api/v1/speaking/today")
def speaking_today(user: dict[str, Any] = Depends(require_roles("student"))) -> dict[str, Any]:
    return daily_goal(user["id"])


@app.get("/api/v1/progress/me")
def progress(user: dict[str, Any] = Depends(require_roles("student"))) -> dict[str, Any]:
    rows = db.fetchall(
        """
        SELECT a.*, l.topic, l.target_text FROM attempts a
        JOIN lessons l ON l.id = a.lesson_id
        WHERE a.user_id = ? AND a.ai_mode <> 'demo' ORDER BY a.created_at DESC LIMIT 20
        """,
        (user["id"],),
    )
    if not rows:
        return {"attempts": [], "count": 0, "averages": None, "daily_goal": daily_goal(user["id"]), "recommendation": "Complete your first pronunciation lesson."}
    keys = ["accuracy", "fluency", "completeness", "prosody", "overall"]
    averages = {k: round(sum(float(r[k]) for r in rows) / len(rows), 1) for k in keys}
    weakest = min(["accuracy", "fluency", "completeness", "prosody"], key=lambda k: averages[k])
    recommendations = {
        "accuracy": "Repeat short chunks and compare the words carefully.",
        "fluency": "Use shadowing to reduce pauses between individual words.",
        "completeness": "Slow down once and make sure every target word is included.",
        "prosody": "Practise sentence stress and natural pauses.",
    }
    return {"attempts": rows, "count": len(rows), "averages": averages, "weakest": weakest, "recommendation": recommendations[weakest], "daily_goal": daily_goal(user["id"])}


@app.get("/api/v1/teacher/overview")
def teacher_overview(user: dict[str, Any] = Depends(require_roles("teacher", "admin"))) -> dict[str, Any]:
    students = db.fetchall(
        """
        SELECT u.id,u.full_name,u.email,u.grade,
               COUNT(a.id) AS attempts,
               ROUND(AVG(a.overall),1) AS average_score,
               MAX(a.created_at) AS last_practice
        FROM users u LEFT JOIN attempts a ON a.user_id=u.id AND a.ai_mode <> 'demo'
        WHERE u.role='student' AND u.active=1 AND
              (?='admin' OR EXISTS (SELECT 1 FROM teacher_students t
                                  WHERE t.student_id=u.id AND t.teacher_id=?))
        GROUP BY u.id,u.full_name,u.email,u.grade
        ORDER BY u.full_name
        """,
        (user["role"], user["id"]),
    )
    today = daily_goal(user["id"])["date"]
    for learner in students:
        row = db.fetchone("SELECT COUNT(*) AS n FROM speaking_events WHERE user_id=? AND day_local=?", (learner["id"], today))
        learner["speaking_today"] = int(row["n"]) if row else 0
    return {"students": students, "total_students": len(students), "speaking_goal": 3}



# V12 curriculum-based teacher-authored lessons: an assignment always requires a teacher/student link.
from .curriculum import prompts_for_student, teacher_access_to_student, GRADE_MAX_WORDS

class TeacherLessonInput(BaseModel):
    grade: int = Field(ge=1, le=5)
    topic: str = Field(min_length=2, max_length=80)
    target_text: str = Field(min_length=1, max_length=180)
    hint: str = Field(default='', max_length=200)
    student_ids: list[str] = Field(default_factory=list, max_length=100)


def _validate_teacher_lesson(payload: TeacherLessonInput, teacher_id: str) -> None:
    text = payload.target_text.strip()
    if len(text.split()) > GRADE_MAX_WORDS[payload.grade]:
        raise HTTPException(status_code=422, detail='Câu quá dài so với mức luyện đọc được thiết kế cho lớp này')
    if not text or not any(ch.isalpha() for ch in text):
        raise HTTPException(status_code=422, detail='Cần nhập từ hoặc câu tiếng Anh hợp lệ')
    for student_id in payload.student_ids:
        if not teacher_access_to_student(teacher_id,student_id,payload.grade):
            raise HTTPException(status_code=403, detail='Không thể giao bài cho HS ngoài lớp phụ trách hoặc khác khối lớp')


@app.get('/api/v1/teacher/lessons')
def teacher_lessons(user: dict[str,Any] = Depends(require_roles('teacher','admin'))) -> dict[str,Any]:
    if user['role']=='teacher':
        rows = db.fetchall('SELECT id,grade,topic,target_text,hint,active,created_at FROM lessons WHERE owner_teacher_id=? ORDER BY created_at DESC', (user['id'],))
    else:
        rows = db.fetchall('SELECT id,grade,topic,target_text,hint,active,created_at FROM lessons WHERE owner_teacher_id IS NOT NULL ORDER BY created_at DESC')
    for row in rows:
        row['student_ids'] = [r['student_id'] for r in db.fetchall('SELECT student_id FROM teacher_lesson_assignments WHERE lesson_id=?',(row['id'],))]
    return {'lessons':rows}


@app.post('/api/v1/teacher/lessons',status_code=201)
def teacher_add_lesson(payload: TeacherLessonInput, user: dict[str,Any] = Depends(require_roles('teacher'))):
    _validate_teacher_lesson(payload,user['id'])
    lesson_id = 'GV-'+str(uuid.uuid4())
    db.execute('INSERT INTO lessons(id,grade,topic,target_text,hint,focus_sound,active,created_at,owner_teacher_id) VALUES(?,?,?,?,?,?,?,?,?)',
        (lesson_id,payload.grade,payload.topic.strip(),payload.target_text.strip(),payload.hint.strip(),'',1,iso_now(),user['id']))
    for student_id in set(payload.student_ids):
        db.execute('INSERT INTO teacher_lesson_assignments(lesson_id,student_id) VALUES(?,?)',(lesson_id,student_id))
    return {'id':lesson_id,'message':'Đã tạo bài luyện và giao cho HS đã chọn.'}


@app.put('/api/v1/teacher/lessons/{lesson_id}')
def teacher_update_lesson(lesson_id:str,payload:TeacherLessonInput,user:dict[str,Any]=Depends(require_roles('teacher'))):
    row=db.fetchone('SELECT id FROM lessons WHERE id=? AND owner_teacher_id=?',(lesson_id,user['id']))
    if not row:
        raise HTTPException(status_code=404,detail='Không tìm thấy bài do GV này tạo')
    _validate_teacher_lesson(payload,user['id'])
    db.execute('UPDATE lessons SET grade=?,topic=?,target_text=?,hint=? WHERE id=?',
               (payload.grade,payload.topic.strip(),payload.target_text.strip(),payload.hint.strip(),lesson_id))
    db.execute('DELETE FROM teacher_lesson_assignments WHERE lesson_id=?',(lesson_id,))
    for student_id in set(payload.student_ids):
        db.execute('INSERT INTO teacher_lesson_assignments(lesson_id,student_id) VALUES(?,?)',(lesson_id,student_id))
    return {'message':'Đã cập nhật bài và danh sách HS nhận bài.'}


@app.delete('/api/v1/teacher/lessons/{lesson_id}')
def teacher_delete_lesson(lesson_id:str,user:dict[str,Any]=Depends(require_roles('teacher'))):
    row=db.fetchone('SELECT id FROM lessons WHERE id=? AND owner_teacher_id=?',(lesson_id,user['id']))
    if not row:
        raise HTTPException(status_code=404,detail='Không tìm thấy bài do GV này tạo')
    db.execute('UPDATE lessons SET active=0 WHERE id=?',(lesson_id,))
    db.execute('DELETE FROM teacher_lesson_assignments WHERE lesson_id=?',(lesson_id,))
    return {'message':'Đã ẩn bài luyện, giữ lịch sử các lượt đã thực hiện.'}


@app.get('/api/v1/live/prompts')
def live_student_prompts(user:dict[str,Any]=Depends(require_roles('student'))):
    prompts=prompts_for_student(user)
    return {'grade':int(user.get('grade') or 3), 'prompts':prompts, 'curriculum':'original_global_success_aligned'}


@app.get("/api/v1/admin/overview")
def admin_overview(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    users = db.fetchall("SELECT id,email,full_name,role,grade,verified,active,created_at FROM users ORDER BY created_at DESC")
    lessons_count = db.fetchone("SELECT COUNT(*) AS n FROM lessons WHERE active=1") or {"n": 0}
    attempts_count = db.fetchone("SELECT COUNT(*) AS n FROM attempts") or {"n": 0}
    return {"users": users, "lesson_count": int(lessons_count["n"]), "attempt_count": int(attempts_count["n"])}


@app.post("/api/v1/admin/users", status_code=201)
def admin_create_user(
    payload: AdminUserCreate,
    user: dict[str, Any] = Depends(require_roles("admin")),
) -> dict[str, Any]:
    """Admin-only creation. Never send passwords by email or expose them in API responses."""
    if APP_ENV != 'local' and payload.role == 'student' and not payload.guardian_confirmed:
        raise HTTPException(status_code=422, detail='Cần xác nhận đã có sự đồng ý của người giám hộ')
    email = payload.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Invalid email")
    if payload.role == "student" and payload.grade is None:
        raise HTTPException(status_code=422, detail="Student grade is required")
    if db.fetchone("SELECT id FROM users WHERE email=?", (email,)):
        raise HTTPException(status_code=409, detail="Account already exists")
    account_id = str(uuid.uuid4())
    db.execute(
        """INSERT INTO users(id,email,password_hash,full_name,role,grade,verified,active,created_at)
           VALUES(?,?,?,?,?,?,?,?,?)""",
        (account_id, email, hash_password(payload.password), payload.full_name.strip(),
         payload.role, payload.grade if payload.role == "student" else None, 1, 1, iso_now()),
    )
    created = db.fetchone("SELECT * FROM users WHERE id=?", (account_id,))
    return {"message": "Account created by administrator", "user": public_user(created)}


class AdminInviteRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=120)
    role: str = Field(default='student', pattern='^(student|teacher)$')
    grade: int | None = Field(default=None, ge=1, le=5)
    guardian_confirmed: bool = False


@app.post('/api/v1/admin/invitations', status_code=201)
def admin_invite_user(
    payload: AdminInviteRequest,
    administrator: dict[str, Any] = Depends(require_roles('admin')),
) -> dict[str, Any]:
    """Send a one-time password-setup link; never email plaintext passwords."""
    if not email_ready():
        raise HTTPException(status_code=503, detail='Hãy cấu hình RESEND_API_KEY và MAIL_FROM hoặc SMTP trước khi gửi lời mời')
    email = payload.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail='Email không hợp lệ')
    if payload.role == 'student' and payload.grade is None:
        raise HTTPException(status_code=422, detail='Cần chọn lớp cho học sinh')
    if payload.role == 'student' and not payload.guardian_confirmed:
        raise HTTPException(status_code=422, detail='Cần xác nhận đã có sự đồng ý của người giám hộ')
    if db.fetchone('SELECT id FROM users WHERE email=?', (email,)):
        raise HTTPException(status_code=409, detail='Email đã có tài khoản')
    import secrets
    uid = str(uuid.uuid4())
    db.execute(
        'INSERT INTO users(id,email,password_hash,full_name,role,grade,verified,active,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
        (uid, email, hash_password(secrets.token_urlsafe(44)), payload.full_name.strip(), payload.role,
         payload.grade if payload.role=='student' else None, 0, 1, iso_now()),
    )
    token = _issue_account_link(uid,'invite',lifetime_minutes=1440)
    sent = send_transactional_email(
        email, 'BrightSpeakAI – Lời mời kích hoạt tài khoản',
        'Xin chào ' + payload.full_name.strip() + ',\n'
        'Tài khoản BrightSpeakAI đã được quản trị viên tạo.\n'
        'Email đăng nhập: ' + email + '\n'
        'Bấm liên kết để tự đặt mật khẩu trong vòng 24 giờ: ' + _link_url(token) + '\n'
        'Nếu bạn không mong đợi lời mời này, hãy bỏ qua email.',
    )
    if not sent:
        db.execute('DELETE FROM account_links WHERE user_id=?',(uid,))
        db.execute('DELETE FROM users WHERE id=?',(uid,))
        raise HTTPException(status_code=502, detail='Dịch vụ email chưa gửi được. Tài khoản chưa được tạo.')
    return {'message': 'Đã gửi lời mời tạo mật khẩu qua email', 'user': public_user(db.fetchone('SELECT * FROM users WHERE id=?',(uid,)))}


@app.patch("/api/v1/admin/users/{user_id}/active")
def admin_toggle_user(
    user_id: str,
    active: bool,
    user: dict[str, Any] = Depends(require_roles("admin")),
) -> dict[str, Any]:
    target = db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target["id"] == user["id"] and not active:
        raise HTTPException(status_code=400, detail="Admin cannot disable their own account")
    db.execute("UPDATE users SET active = ? WHERE id = ?", (1 if active else 0, user_id))
    return {"message": "Account status updated", "active": active}


@app.post("/api/v1/admin/lessons", status_code=201)
def admin_create_lesson(
    payload: LessonCreateRequest,
    user: dict[str, Any] = Depends(require_roles("admin")),
) -> dict[str, Any]:
    if db.fetchone("SELECT id FROM lessons WHERE id = ?", (payload.id,)):
        raise HTTPException(status_code=409, detail="Lesson ID already exists")
    db.execute(
        "INSERT INTO lessons(id,grade,topic,target_text,hint,focus_sound,active,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (payload.id, payload.grade, payload.topic, payload.target_text, payload.hint, payload.focus_sound, 1, iso_now()),
    )
    return {"message": "Lesson created", "id": payload.id}


@app.post("/api/v1/admin/teacher-students")
def assign_student_to_teacher(
    teacher_id: str = Form(...), student_id: str = Form(...),
    user: dict[str, Any] = Depends(require_roles("admin")),
) -> dict[str, str]:
    teacher = db.fetchone("SELECT role FROM users WHERE id=?", (teacher_id,))
    student = db.fetchone("SELECT role FROM users WHERE id=?", (student_id,))
    if not teacher or teacher["role"] != "teacher" or not student or student["role"] != "student":
        raise HTTPException(status_code=400, detail="Teacher/student IDs are invalid")
    if not db.fetchone("SELECT teacher_id FROM teacher_students WHERE teacher_id=? AND student_id=?", (teacher_id, student_id)):
        db.execute("INSERT INTO teacher_students(teacher_id,student_id) VALUES(?,?)", (teacher_id, student_id))
    return {"status": "assigned"}

# Authenticated streaming audio/video proxy for face-to-face English practice.
from .live import router as live_router
app.include_router(live_router)


@app.get('/api/v1/learning/recommendations')
def learning_recommendations(user: dict[str, Any] = Depends(require_roles('student'))):
    eligible = lessons(user=user)
    attempts = db.fetchall("SELECT * FROM attempts WHERE user_id=? AND ai_mode <> 'demo' ORDER BY created_at DESC LIMIT 100", (user['id'],))
    return {'items': recommend_lessons(eligible, attempts),
        'method': 'explainable-grade-history-rules-v13',
        'notice': 'Gợi ý dựa trên khối lớp và kết quả luyện tập; GV có thể điều chỉnh.'}


@app.post('/api/v1/admin/ai/check')
async def check_ai(user: dict[str, Any] = Depends(require_roles('admin'))):
    if not gemini.enabled:
        return {'ok': False, 'code': 'missing_key', 'message': 'Chưa cấu hình Gemini API key ở máy chủ.'}
    try:
        # Minimal real model probe. Does not transmit student information.
        await run_in_threadpool(gemini._call, [{'text': 'Reply with OK only.'}], 0.0)
        return {'ok': True, 'model': gemini.model, 'live_model': GEMINI_LIVE_MODEL,
            'message': 'Đã kết nối model hội thoại. Gemini Live cần kiểm tra riêng bằng mic.',
            'live_verified': False}
    except Exception as exc:
        return {'ok': False, 'model': gemini.model, 'code': getattr(exc, 'code', 'provider_error'),
            'message': str(exc), 'live_verified': False}


@app.get('/api/v1/admin/ml/status')
def ml_status(user: dict[str, Any] = Depends(require_roles('admin'))):
    path = ROOT_DIR / 'ml' / 'models' / 'keyword_spotter_metrics.json'
    return {'keyword_metrics': json.loads(path.read_text()) if path.exists() else None,
        'model_bundled': (ROOT_DIR / 'ml' / 'models' / 'keyword_spotter.joblib').exists(),
        'cnn_model_bundled': (ROOT_DIR / 'ml' / 'models' / 'keyword_cnn.pt').exists(),
        'notice': 'Nhận diện 8 từ khóa thử nghiệm; không dùng kết quả này làm độ chính xác chấm phát âm HS.'}

from .speaking_review import router as speaking_review_router
app.include_router(speaking_review_router)
