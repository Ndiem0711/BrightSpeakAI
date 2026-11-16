from __future__ import annotations

import base64
import json
import mimetypes
import urllib.error
import urllib.request
from typing import Any

from .config import GEMINI_API_KEY, GEMINI_MODEL
from .ai_errors import AIServiceError, provider_error


class GeminiService:
    def __init__(self) -> None:
        self.api_key = GEMINI_API_KEY
        self.model = GEMINI_MODEL

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _call(self, parts: list[dict[str, Any]], temperature: float = 0.25) -> str:
        if not self.enabled:
            raise RuntimeError("Gemini API key is not configured")
        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        body = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": temperature},
        }
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=75) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise provider_error(exc.code) from None
        except Exception as exc:
            raise AIServiceError("network_error", "Không kết nối được AI. Kiểm tra mạng rồi thử lại.") from None
        try:
            parts_out = payload["candidates"][0]["content"]["parts"]
            text = "".join(part.get("text", "") for part in parts_out).strip()
            if not text:
                raise KeyError("empty response")
            return text
        except Exception as exc:
            raise RuntimeError("Gemini returned an unexpected response") from exc

    def transcribe_wav(self, wav_bytes: bytes) -> str:
        prompt = (
            "Transcribe the child's English speech VERBATIM. Preserve mistakes and missing words. "
            "Return only the spoken transcript, with no explanation and no quotation marks."
        )
        return self._call(
            [
                {"text": prompt},
                {"inline_data": {"mime_type": "audio/wav", "data": base64.b64encode(wav_bytes).decode("ascii")}},
            ],
            temperature=0.0,
        )

    def conversation_reply(self, grade: int, topic: str, student_text: str, history: list[dict[str, str]] | None = None) -> str:
        prompt = f"""
You are Bibi, a warm English speaking tutor for a Vietnamese primary-school learner in Grade {grade}.
Topic: {topic}.
Last five exchanges (for continuity): {history or []!r}
Student said: {student_text!r}
Rules:
- Reply in simple English suitable for Grade {grade}.
- Praise effort briefly.
- Correct at most ONE important language error, gently.
- Give one short model sentence only when useful.
- End with ONE natural follow-up question.
- Avoid long explanations and avoid grading personality/confidence.
- Do not ask for real names, address, personal contacts or private details.
Return 2-4 short sentences, plain text only.
""".strip()
        return self._call([{"text": prompt}], temperature=0.45)

    def look_and_speak(self, image_bytes: bytes, mime_type: str, answer: str, grade: int) -> dict[str, Any]:
        prompt = f"""
You are assessing a Grade {grade} primary learner's English picture-speaking response.
Student answer: {answer!r}
Inspect the image and evaluate only whether the answer is relevant and understandable.
Return ONLY valid JSON with this exact structure:
{{"score": 0-100, "feedback": "one supportive sentence", "model_sentence": "one improved simple sentence", "next_question": "one simple question"}}
Do not infer emotion, intelligence, or personality.
""".strip()
        text = self._call(
            [
                {"text": prompt},
                {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode("ascii")}},
            ],
            temperature=0.2,
        )
        cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            data = json.loads(cleaned)
            return {
                "score": max(0.0, min(100.0, float(data.get("score", 70)))),
                "feedback": str(data.get("feedback", "Good effort!")),
                "model_sentence": str(data.get("model_sentence", answer)),
                "next_question": str(data.get("next_question", "What else can you see?")),
            }
        except Exception as exc:
            raise RuntimeError("Gemini image analysis did not return valid scoring JSON") from exc


gemini = GeminiService()
