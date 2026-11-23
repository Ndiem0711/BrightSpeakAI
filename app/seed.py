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
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    if not email and not password:
        return
    if not email or "@" not in email or len(password) < 12:
        raise RuntimeError("Invalid cloud admin bootstrap configuration")
    existing = db.fetchone("SELECT role FROM users WHERE email=?", (email,))
    if existing:
        if existing["role"] != "admin":
            import logging
            logging.getLogger(__name__).warning("Bootstrap email belongs to a non-admin. Configure an unused administrator email.")
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

    from .curriculum import curated_prompts, legacy_catalog
    now = iso_now()
    rows = [(p["id"], p["grade"], p["topic"], p["sample_answer"],
             p["skill"] + " · " + p["question"], "", 1, now) for p in curated_prompts()]
    with db.connect() as conn:
        with_cursor = conn.cursor()
        try:
            with_cursor.executemany(db._sql(
                "INSERT INTO lessons(id,grade,topic,target_text,hint,focus_sound,active,created_at) "
                "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING"), rows)
            with_cursor.executemany(db._sql(
                "UPDATE lessons SET active=0 WHERE id=? AND owner_teacher_id IS NULL AND active=1"),
                [(item,) for item in legacy_catalog()["retired_lesson_ids"]])
        finally:
            with_cursor.close()

    if APP_ENV == "local" and not db.fetchone("SELECT teacher_id FROM teacher_students WHERE teacher_id=? AND student_id=?", ("demo-teacher", "demo-student")):
        db.execute("INSERT INTO teacher_students(teacher_id,student_id) VALUES(?,?)", ("demo-teacher", "demo-student"))
