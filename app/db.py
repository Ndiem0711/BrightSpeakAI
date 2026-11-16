from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import DATABASE_URL, ROOT_DIR


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        self.is_postgres = url.startswith("postgresql://") or url.startswith("postgres://")
        if not self.is_postgres:
            if url.startswith("sqlite:///"):
                rel = url.removeprefix("sqlite:///")
                self.sqlite_path = (ROOT_DIR / rel).resolve()
            else:
                self.sqlite_path = (ROOT_DIR / "runtime" / "brightspeak.db").resolve()
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[Any]:
        if self.is_postgres:
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as exc:
                raise RuntimeError(
                    "PostgreSQL mode requires requirements-cloud.txt. "
                    "Install it or use the default SQLite DATABASE_URL."
                ) from exc
            conn = psycopg.connect(self.url, row_factory=dict_row, autocommit=False)
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        else:
            conn = sqlite3.connect(self.sqlite_path, timeout=15, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _sql(self, sql: str) -> str:
        return sql.replace("?", "%s") if self.is_postgres else sql

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with self.connect() as conn:
            conn.execute(self._sql(sql), params)

    def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connect() as conn:
            cur = conn.execute(self._sql(sql), params)
            row = cur.fetchone()
            return dict(row) if row is not None else None

    def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            cur = conn.execute(self._sql(sql), params)
            return [dict(row) for row in cur.fetchall()]

    def init_schema(self) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL,
                grade INTEGER,
                verified INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                token_version INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS otp_codes (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                code TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS account_links (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                purpose TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS lessons (
                id TEXT PRIMARY KEY,
                grade INTEGER NOT NULL,
                topic TEXT NOT NULL,
                target_text TEXT NOT NULL,
                hint TEXT,
                focus_sound TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                owner_teacher_id TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS attempts (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                lesson_id TEXT NOT NULL,
                transcript TEXT NOT NULL,
                accuracy REAL NOT NULL,
                fluency REAL NOT NULL,
                completeness REAL NOT NULL,
                prosody REAL NOT NULL,
                overall REAL NOT NULL,
                duration REAL NOT NULL,
                ai_mode TEXT NOT NULL,
                feedback TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(lesson_id) REFERENCES lessons(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS conversation_logs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                topic TEXT NOT NULL,
                user_text TEXT NOT NULL,
                ai_text TEXT NOT NULL,
                ai_mode TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS teacher_students (
                teacher_id TEXT NOT NULL,
                student_id TEXT NOT NULL,
                PRIMARY KEY(teacher_id, student_id),
                FOREIGN KEY(teacher_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS teacher_lesson_assignments (
                lesson_id TEXT NOT NULL,
                student_id TEXT NOT NULL,
                PRIMARY KEY (lesson_id, student_id),
                FOREIGN KEY (lesson_id) REFERENCES lessons(id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS speaking_events (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                source TEXT NOT NULL,
                transcript TEXT NOT NULL,
                day_local TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS look_speak_logs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                answer_text TEXT NOT NULL,
                score REAL NOT NULL,
                feedback TEXT NOT NULL,
                ai_mode TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
        ]
        statements.append("""CREATE TABLE IF NOT EXISTS assessment_details (
            attempt_id TEXT PRIMARY KEY, method TEXT NOT NULL,
            alignment_json TEXT NOT NULL, feedback_json TEXT,
            FOREIGN KEY(attempt_id) REFERENCES attempts(id) ON DELETE CASCADE)""")
        with self.connect() as conn:
            for statement in statements:
                conn.execute(self._sql(statement))
            # Schema migration for existing V10 accounts. Never discard user data.
            if self.is_postgres:
                conn.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0')
            else:
                cols={r['name'] for r in conn.execute('PRAGMA table_info(users)').fetchall()}
                if 'token_version' not in cols:
                    conn.execute('ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0')
            if self.is_postgres:
                conn.execute('ALTER TABLE lessons ADD COLUMN IF NOT EXISTS owner_teacher_id TEXT')
            else:
                lesson_columns = {r['name'] for r in conn.execute('PRAGMA table_info(lessons)').fetchall()}
                if 'owner_teacher_id' not in lesson_columns:
                    conn.execute('ALTER TABLE lessons ADD COLUMN owner_teacher_id TEXT')
            # Activation and actual email verification are distinct states.
            if self.is_postgres:
                conn.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified INTEGER NOT NULL DEFAULT 0')
            else:
                user_cols={row['name'] for row in conn.execute('PRAGMA table_info(users)').fetchall()}
                if 'email_verified' not in user_cols:
                    conn.execute('ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0')
            # Useful indexes for dashboards and progress queries.
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_attempts_user_created ON attempts(user_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_lessons_grade ON lessons(grade)",
                "CREATE INDEX IF NOT EXISTS idx_teacher_lesson_owner ON lessons(owner_teacher_id)",
                "CREATE INDEX IF NOT EXISTS idx_teacher_assign_student ON teacher_lesson_assignments(student_id)",
                "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
                "CREATE INDEX IF NOT EXISTS idx_account_links_user ON account_links(user_id,created_at)",
                "CREATE INDEX IF NOT EXISTS idx_speaking_user_day ON speaking_events(user_id, day_local)",
            ]
            for statement in indexes:
                conn.execute(self._sql(statement))


db = Database(DATABASE_URL)
