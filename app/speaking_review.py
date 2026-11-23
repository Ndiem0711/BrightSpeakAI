"""Personal read-aloud practice. Compare only a requested reading, never a free reply."""
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from .asr import ASRUnavailable, transcribe_audio
from .auth import iso_now, require_roles
from .curriculum import legacy_review_prompts, prompts_for_student, resolve_student_prompt
from .db import db
from .daily import record_spoken_turn
from .scoring import acoustic_features, align_words, normalize_text, validate_speech_signal

router = APIRouter()


def assess_reading(student, prompt, transcript):
    spoken = normalize_text(transcript).split()
    if not spoken:
        raise ValueError("Bibi chưa nghe rõ. Em thử nói lại nhé.")
    target = prompt["sample_answer"]
    alignment = align_words(normalize_text(target).split(), spoken[:160])
    errors = [row for row in alignment if row["status"] != "matched"]
    words = list(dict.fromkeys(row["expected"] for row in errors if row["expected"]))
    if words:
        hint = f'Bibi chưa nghe rõ từ “{words[0]}”. Em nghe từ đó, đọc chậm rồi nối vào cả câu nhé.'
    elif errors:
        hint = "Bibi nghe thêm từ ngoài câu mẫu. Em nghe lại rồi đọc từng cụm nhé."
    else:
        hint = "Bibi nghe đủ các từ theo đúng thứ tự rồi!"
    db.execute("""INSERT INTO speaking_reviews(user_id,prompt_id,target,words,pending,updated_at)
                  VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,prompt_id) DO UPDATE SET
                  target=excluded.target,words=excluded.words,pending=excluded.pending,updated_at=excluded.updated_at""",
               (student["id"], prompt["id"], target, json.dumps(words), int(bool(errors)), iso_now()))
    return dict(prompt_id=prompt["id"], topic=prompt["topic"], target=target, words=words,
                heard=transcript, hint=hint, pending=bool(errors))


@router.get("/api/v1/speaking/review")
def review_list(user=Depends(require_roles("student"))):
    eligible = {p["id"]: p for p in prompts_for_student(user)}
    eligible.update(legacy_review_prompts(user))
    rows = db.fetchall("SELECT * FROM speaking_reviews WHERE user_id=? AND pending=1 ORDER BY updated_at DESC", (user["id"],))
    return [dict(prompt_id=p["id"], topic=p["topic"], target=p["sample_answer"], words=json.loads(r["words"]))
            for r in rows if (p := eligible.get(r["prompt_id"])) and p["sample_answer"] == r["target"]]


@router.post("/api/v1/speaking/read")
async def read_sample(prompt_id: str = Form(...), audio: UploadFile = File(...), user=Depends(require_roles("student"))):
    prompt = resolve_student_prompt(user, prompt_id)
    if not prompt:
        raise HTTPException(404, "Câu này hiện chưa có trong bài của em.")
    from .upload_validation import limited_upload, MAX_WAV_BYTES
    wav = await limited_upload(audio, MAX_WAV_BYTES, "Bản ghi âm")
    try:
        validate_speech_signal(acoustic_features(wav))
        text, _ = await run_in_threadpool(transcribe_audio, wav)
        result = assess_reading(user, prompt, text)
        result["goal"] = record_spoken_turn(user["id"], "guided_reading", text)
        return result
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ASRUnavailable as exc:
        raise HTTPException(503, "Chưa nhận dạng được giọng nói. Em có thể nghe mẫu rồi thử lại sau.") from exc
