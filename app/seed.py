from __future__ import annotations

import json
import uuid
import os
from pathlib import Path

from .auth import hash_password, iso_now
from .config import ROOT_DIR, APP_ENV
from .db import db


DEMO_USERS = [
    ("demo-student", "student@demo.com", "student123", "Minh Anh", "student", 3),
    ("demo-teacher", "teacher@demo.com", "teacher123", "Ms. Diem", "teacher", None),
    ("demo-admin", "admin@demo.com", "admin123", "System Admin", "admin", None),
]


def seed_cloud_admin() -> None:
    """Provision a one-time administrator from *secret-backed* deployment env vars.

    This only creates a missing account, never resets a password. Remove the
    bootstrap secret from Cloud Run after the first successful deployment.
    """
    if APP_ENV != "cloud":
        return
    email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "").strip()
    if not email and not password:
        return
    if not email or "@" not in email or len(password) < 12:
        raise RuntimeError("Invalid cloud admin bootstrap configuration")
    if db.fetchone("SELECT id FROM users WHERE email=?", (email,)):
        return
    db.execute(
        """INSERT INTO users(id,email,password_hash,full_name,role,grade,verified,active,created_at)
           VALUES(?,?,?,?,?,?,?,?,?)""",
        (str(uuid.uuid4()), email, hash_password(password), "BrightSpeak Administrator", "admin", None, 1, 1, iso_now()),
    )


def seed_defaults() -> None:
    seed_cloud_admin()
    for user_id, email, password, full_name, role, grade in (DEMO_USERS if APP_ENV == "local" else []):
        existing = db.fetchone("SELECT id FROM users WHERE email = ?", (email,))
        if not existing:
            db.execute(
                """
                INSERT INTO users(id,email,password_hash,full_name,role,grade,verified,active,created_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (user_id, email, hash_password(password), full_name, role, grade, 1, 1, iso_now()),
            )

    lessons_path = ROOT_DIR / "data" / "lessons.json"
    lessons = json.loads(lessons_path.read_text(encoding="utf-8"))
    for lesson in lessons:
        existing = db.fetchone("SELECT id FROM lessons WHERE id = ?", (lesson["id"],))
        if not existing:
            db.execute(
                """
                INSERT INTO lessons(id,grade,topic,target_text,hint,focus_sound,active,created_at)
                VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    lesson["id"], lesson["grade"], lesson["topic"], lesson["target_text"],
                    lesson.get("hint", ""), lesson.get("focus_sound", ""), 1, iso_now(),
                ),
            )

    if APP_ENV == "local" and not db.fetchone("SELECT teacher_id FROM teacher_students WHERE teacher_id=? AND student_id=?", ("demo-teacher", "demo-student")):
        db.execute("INSERT INTO teacher_students(teacher_id,student_id) VALUES(?,?)", ("demo-teacher", "demo-student"))
