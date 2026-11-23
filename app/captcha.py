"""Short-lived, database-backed visual CAPTCHA for student self-signup.

CAPTCHA helps discourage casual scripted registrations; it does NOT verify
ownership of the email address, and is not a substitute for moderation or
identity verification on a public school deployment.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import random
import secrets
import uuid
from datetime import timedelta

from fastapi import HTTPException
from PIL import Image, ImageDraw, ImageFont

from .auth import iso_now, utcnow
from .config import SECRET_KEY
from .db import db

ALPHABET = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
EXPIRY_MINUTES = 5
MAX_ATTEMPTS = 5
MAX_ISSUED_PER_IP = 120


def _digest(challenge_id: str, code: str) -> str:
    material = f'{challenge_id}:{code.upper()}'.encode('utf-8')
    return hmac.new(SECRET_KEY.encode('utf-8'), material, hashlib.sha256).hexdigest()


def _render_png(code: str) -> bytes:
    image = Image.new('RGB', (238, 84), '#f5f6ff')
    draw = ImageDraw.Draw(image)
    rng = random.SystemRandom()
    for _ in range(12):
        draw.line((rng.randrange(238), rng.randrange(84), rng.randrange(238), rng.randrange(84)), fill=(175, 188, 213), width=1)
    try:
        font = ImageFont.truetype('DejaVuSans-Bold.ttf', 38)
    except OSError:
        font = ImageFont.load_default()
    for i, letter in enumerate(code):
        color = rng.choice(('#283f82', '#65519b', '#20717d', '#824663'))
        draw.text((14+i*42, rng.randrange(12, 26)), letter, fill=color, font=font)
    for _ in range(155):
        x, y = rng.randrange(238), rng.randrange(84)
        draw.point((x, y), fill=(rng.randrange(130,200),rng.randrange(130,200),rng.randrange(170,230)))
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def new_challenge(ip_address: str) -> dict[str, str | int]:
    ip = (ip_address or 'unknown')[:100]
    now = utcnow()
    # Restrict repeated issuance, including unsuccessful attempts.
    recent = db.fetchone('SELECT COUNT(*) AS n FROM captcha_challenges WHERE issued_ip=? AND created_at>=?',
                         (ip, (now - timedelta(minutes=10)).isoformat()))
    if recent and int(recent['n']) >= MAX_ISSUED_PER_IP:
        raise HTTPException(status_code=429, detail='Bạn yêu cầu CAPTCHA quá nhiều lần. Hãy thử lại sau.')
    code = ''.join(secrets.choice(ALPHABET) for _ in range(5))
    challenge_id = str(uuid.uuid4())
    db.execute('INSERT INTO captcha_challenges(id,code_hash,issued_ip,attempts,used,created_at,expires_at) '
               'VALUES(?,?,?,0,0,?,?)',
               (challenge_id, _digest(challenge_id, code), ip, now.isoformat(),
                (now + timedelta(minutes=EXPIRY_MINUTES)).isoformat()))
    return {
        'captcha_id': challenge_id,
        'image_data': 'data:image/png;base64,' + base64.b64encode(_render_png(code)).decode('ascii'),
        'expires_in_seconds': EXPIRY_MINUTES * 60,
    }


def consume(challenge_id: str, answer: str) -> None:
    if not challenge_id or len(challenge_id) > 80 or not answer or len(answer) > 12:
        raise HTTPException(status_code=422, detail='Mã CAPTCHA không hợp lệ. Vui lòng lấy mã mới.')
    now = utcnow().isoformat()
    with db.connect() as conn:
        # Increment attempts atomically to invalidate stale/replayed challenges.
        row = conn.execute(db._sql('SELECT code_hash,attempts,used,expires_at FROM captcha_challenges WHERE id=?'), (challenge_id,)).fetchone()
        if row is None or row['used'] or row['expires_at'] <= now or int(row['attempts']) >= MAX_ATTEMPTS:
            raise HTTPException(status_code=422, detail='CAPTCHA đã hết hạn hoặc được sử dụng. Hãy lấy mã mới.')
        correct = hmac.compare_digest(str(row['code_hash']), _digest(challenge_id, answer.strip().upper()))
        cursor = conn.execute(db._sql('UPDATE captcha_challenges SET attempts=attempts+1, used=? WHERE id=? AND attempts=? AND used=0 AND expires_at>?'),
                              (int(correct), challenge_id, int(row['attempts']), now))
        if cursor.rowcount != 1:
            raise HTTPException(status_code=422, detail='CAPTCHA đã được sử dụng. Hãy lấy mã mới.')
        # Raise after transaction has committed so incorrect attempts cannot be retried forever.
    if not correct:
        raise HTTPException(status_code=422, detail='Mã CAPTCHA chưa đúng. Hãy kiểm tra và nhập lại.')
