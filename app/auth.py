from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import ACCESS_TOKEN_MINUTES, REFRESH_TOKEN_DAYS, SECRET_KEY
from .db import db

security = HTTPBearer(auto_error=False)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utcnow().isoformat()


def hash_password(password: str) -> str:
    # PBKDF2-HMAC-SHA256 is in the Python standard library, avoiding native
    # package build issues while still using a salted adaptive KDF.
    salt = secrets.token_bytes(16)
    iterations = 310_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, iterations_s, salt_hex, digest_hex = encoded.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations_s),
        )
        return hmac.compare_digest(actual.hex(), digest_hex)
    except Exception:
        return False


def create_token(user: dict[str, Any], token_type: str) -> str:
    now = utcnow()
    if token_type == "access":
        exp = now + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    elif token_type == "refresh":
        exp = now + timedelta(days=REFRESH_TOKEN_DAYS)
    else:
        raise ValueError("Unsupported token type")
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "type": token_type,
        "pv": int(user.get("token_version", 0)),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def token_pair(user: dict[str, Any]) -> dict[str, str]:
    return {
        "access_token": create_token(user, "access"),
        "refresh_token": create_token(user, "refresh"),
        "token_type": "bearer",
    }


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    if payload.get("type") != expected_type:
        raise HTTPException(status_code=401, detail=f"Expected {expected_type} token")
    return payload


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, Any]:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    payload = decode_token(credentials.credentials, "access")
    user = db.fetchone("SELECT * FROM users WHERE id = ?", (payload["sub"],))
    if not user or not int(user["active"]):
        raise HTTPException(status_code=401, detail="Account unavailable")
    if int(payload.get('pv', 0)) != int(user.get('token_version', 0)):
        raise HTTPException(status_code=401, detail="Session has been revoked. Please log in again.")
    return user


def require_roles(*roles: str):
    def dependency(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return dependency
