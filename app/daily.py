"""Daily speaking goal: counts successfully transcribed *spoken* English turns.
Typed messages and text-only demos never count. No raw audio stored by this module.
"""
from __future__ import annotations
import re
import uuid
from datetime import datetime, timedelta, timezone
from .db import db

# Vietnam observes UTC+07:00 year-round (no daylight saving time).
# Fixed-offset tzinfo avoids ZoneInfoNotFoundError on clean Windows installs
# where IANA tzdata is not bundled with Python.
VIETNAM_TZ = timezone(timedelta(hours=7), name="Asia/Ho_Chi_Minh")
GOAL = 3

def local_day() -> str:
    return datetime.now(VIETNAM_TZ).date().isoformat()

def daily_goal(user_id: str) -> dict:
    day = local_day()
    row = db.fetchone("SELECT COUNT(*) AS n FROM speaking_events WHERE user_id=? AND day_local=?", (user_id, day))
    count = int(row["n"]) if row else 0
    return {"date": day, "count": count, "target": GOAL,
            "remaining": max(0, GOAL - count), "completed": count >= GOAL}

def record_spoken_turn(user_id: str, source: str, transcript: str) -> dict:
    # Only called AFTER successful recognition of real microphone audio (not typed/demo text).
    cleaned = " ".join(str(transcript).split())[:500]
    # Reject empty/noisy artifacts and single-word ASR fragments.
    if len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", cleaned)) < 2:
        return daily_goal(user_id)
    if source not in {"voice_chat", "look_speak", "gemini_live"}:
        return daily_goal(user_id)
    db.execute("INSERT INTO speaking_events(id,user_id,source,transcript,day_local,created_at) VALUES(?,?,?,?,?,?)",
        (str(uuid.uuid4()), user_id, source, cleaned, local_day(), datetime.now(VIETNAM_TZ).isoformat()))
    return daily_goal(user_id)
