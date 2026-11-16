from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_env_file(ROOT_DIR / "AI_MODELS.txt")
_load_env_file(ROOT_DIR / ".env")

APP_ENV = os.getenv("APP_ENV", "local")
APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", "8765"))
SECRET_KEY = os.getenv("SECRET_KEY", "brightspeak-local-only-replace-before-cloud").strip()
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "120"))
REFRESH_TOKEN_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", "7"))
DEMO_OTP = os.getenv("DEMO_OTP", "true").lower() in {"1", "true", "yes", "on"}
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview").strip() or "gemini-3.1-pro-preview"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///runtime/brightspeak.db").strip()
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_FROM = os.getenv("SMTP_FROM", "").strip()
GCS_BUCKET = os.getenv("GCS_BUCKET", "").strip()

GEMINI_LIVE_MODEL = os.getenv("GEMINI_LIVE_MODEL", "gemini-3.8-live").strip()
ASR_ENGINE = os.getenv("ASR_ENGINE", "auto").strip().lower()  # auto | gemini | whisper
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "tiny.en").strip()
if APP_ENV == "cloud" and not DATABASE_URL.startswith(("postgresql://", "postgres://")):
    raise RuntimeError("Cloud requires persistent PostgreSQL DATABASE_URL; SQLite is not safe on Cloud Run")
if APP_ENV == "cloud" and (SECRET_KEY.startswith("brightspeak-local-") or DEMO_OTP):
    raise RuntimeError("Cloud security: set SECRET_KEY using Secret Manager, and DEMO_OTP=false")

# Transactional email over HTTPS is supported on free cloud hosts that block SMTP.
RESEND_API_KEY = os.getenv('RESEND_API_KEY', '').strip()
MAIL_FROM = os.getenv('MAIL_FROM', '').strip() or SMTP_FROM
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', '').strip() or f'http://127.0.0.1:{APP_PORT}'

AUDIO_FEEDBACK_ENABLED = os.getenv("AUDIO_FEEDBACK_ENABLED", "true").lower() in {"true", "1", "yes"}

if APP_ENV == 'cloud' and (len(SECRET_KEY) < 32 or SECRET_KEY == 'brightspeak-local-only-replace-before-cloud'):
    raise RuntimeError('Cloud requires a unique SECRET_KEY of at least 32 characters')
if APP_ENV == 'cloud' and DEMO_OTP:
    raise RuntimeError('Cloud requires DEMO_OTP=false')

# V13.0.1: direct signup is intentional; SMTP is optional for this flow.
REGISTRATION_MODE = os.getenv('REGISTRATION_MODE', 'direct').strip().lower()
if REGISTRATION_MODE not in {'direct', 'otp'}:
    raise RuntimeError('REGISTRATION_MODE must be direct or otp')
