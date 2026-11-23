from __future__ import annotations

import base64
import json
import mimetypes
import time
import urllib.error
import urllib.request
from typing import Any

from .config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_FALLBACK_MODEL, GEMINI_FAST_MODEL, GEMINI_FAST_FALLBACK_MODEL, GEMINI_FAST_TIMEOUT
from .ai_errors import AIServiceError, provider_error


class GeminiService:
    def __init__(self) -> None:
        self.api_key = GEMINI_API_KEY
        self.model = GEMINI_MODEL

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _call(self, parts: list[dict[str, Any]], temperature: float = 0.25, *, fast: bool = False, response_json: bool = False) -> str:
        if not self.enabled:
            raise AIServiceError('missing_key', 'Chưa cấu hình Gemini API key trên máy chủ.')
        body = {
            'contents': [{'role': 'user', 'parts': parts}],
            'generationConfig': {'temperature': temperature},
        }
        if fast:
            body['generationConfig']['maxOutputTokens'] = 384 if response_json else 192
        if response_json:
            body['generationConfig']['responseMimeType'] = 'application/json'
        request_bytes = json.dumps(body).encode('utf-8')
        # When the primary model is temporarily overloaded or unavailable, a
        # separately configured stable Flash model can serve as the fallback.
        models = [GEMINI_FAST_MODEL if fast else self.model]
        backup = GEMINI_FAST_FALLBACK_MODEL if fast else GEMINI_FALLBACK_MODEL
        if backup and backup not in models:
            models.append(backup)
        last_error = None
        transient = {408, 429, 500, 502, 503, 504}
        for model in models:
            endpoint = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
            request = urllib.request.Request(endpoint, data=request_bytes,
                        headers={'Content-Type': 'application/json','x-goog-api-key':self.api_key}, method='POST')
            for attempt in range(1 if fast else 3):
                try:
                    with urllib.request.urlopen(request, timeout=GEMINI_FAST_TIMEOUT if fast else 40) as response:
                        payload = json.loads(response.read().decode('utf-8'))
                    content = payload['candidates'][0]['content']['parts']
                    result = ''.join(part.get('text','') for part in content).strip()
                    if not result:
                        raise AIServiceError('empty_response','Dịch vụ AI không trả về nội dung. Vui lòng thử lại.')
                    return result
                except urllib.error.HTTPError as exc:
                    last_error = provider_error(exc.code)
                    if exc.code in transient and attempt < (0 if fast else 2):
                        retry_header = getattr(exc, 'headers', None)
                        raw_retry = retry_header.get('Retry-After') if retry_header else None
                        try:
                            delay = max(0.3, min(3.0, float(raw_retry))) if raw_retry else 0.7 * (attempt + 1)
                        except (TypeError, ValueError):
                            delay = 0.7 * (attempt + 1)
                        time.sleep(delay)
                        continue
                    if exc.code in transient or exc.code == 404:
                        break  # Try alternate configured model, if one exists.
                    raise last_error from None
                except AIServiceError:
                    raise
                except (urllib.error.URLError, TimeoutError, OSError):
                    last_error=AIServiceError('network_error','Không kết nối được AI. Kiểm tra mạng rồi thử lại.')
                    if attempt < (0 if fast else 2):
                        time.sleep(0.7 * (attempt + 1))
                        continue
                    break
                except (ValueError, KeyError, IndexError, TypeError):
                    raise AIServiceError('invalid_response','Dịch vụ AI trả về dữ liệu không đúng cấu trúc.') from None
        raise (last_error or AIServiceError('provider_unavailable','Dịch vụ AI chưa sẵn sàng.'))

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
            temperature=0.0, fast=True,
        )

    def conversation_reply(self, grade: int, topic: str, student_text: str, history: list[dict[str, str]] | None = None) -> str:
        from .curriculum import unit_context
        prompt = f"""
You are Bibi, a warm English speaking tutor for a Vietnamese primary-school learner in Grade {grade}.
Topic: {topic}.
{unit_context(grade, topic)}
For identity and home lessons, role-play imaginary characters using made-up details.
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

    @staticmethod
    def _picture_result(raw: str) -> dict[str, Any]:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            data = json.loads(clean)
            if not isinstance(data, dict) or not isinstance(data.get("score"), (int, float)):
                raise ValueError("Missing score")
            score = float(data["score"])
            if not 0 <= score <= 100:
                raise ValueError("Score outside range")
            return {
                "score": score,
                "feedback": str(data.get("feedback", ""))[:350],
                "model_sentence": str(data.get("model_sentence", ""))[:250],
                "next_question": str(data.get("next_question", ""))[:250],
                "transcript": str(data.get("transcript", "")).strip()[:700],
            }
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            raise AIServiceError("invalid_response", "Gemini trả về kết quả chưa đúng định dạng. Em hãy thử lại.") from None

    def look_and_speak(self, image_bytes: bytes, mime_type: str, answer: str, grade: int) -> dict[str, Any]:
        """Text mode: one fast Gemini request to inspect the image."""
        prompt = (
            f"You are a friendly Grade {grade} English picture-speaking tutor. "
            f"Student typed this description: {answer!r}. Assess the picture relevance ONLY, not pronunciation. "
            'Return JSON ONLY with numeric score 0-100 and brief strings feedback, model_sentence, next_question. '
            'Be kind and age-appropriate. No inferred emotion or intelligence.'
        )
        raw = self._call([
            {"text": prompt},
            {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode("ascii")}},
        ], temperature=0.1, fast=True, response_json=True)
        result = self._picture_result(raw)
        result["transcript"] = answer
        return result

    def look_and_speak_audio(self, image_bytes: bytes, mime_type: str, wav_bytes: bytes, grade: int) -> dict[str, Any]:
        """Speech + picture: one Gemini request rather than serial ASR and vision calls."""
        prompt = (
            f"You are a kind Grade {grade} English picture-speaking tutor. "
            "First listen to the actual audio and transcribe the child's spoken English VERBATIM, "
            "without silently correcting mistakes. If unintelligible, put an empty transcript. "
            "Then inspect the picture and evaluate ONLY how relevant the transcribed speech is to it. "
            'Return JSON ONLY: {"transcript":"exact heard words or empty","score":0,'
            '"feedback":"one short supportive sentence","model_sentence":"one short example",'
            '"next_question":"one simple question"}. "score" is numeric 0-100 for IMAGE RELEVANCE, '
            "NOT speech pronunciation. Never guess the transcript from the image or lesson context. "
            "Do not infer the learner's emotions, intelligence or personal traits."
        )
        raw = self._call([
            {"text": prompt},
            {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode("ascii")}},
            {"inline_data": {"mime_type": "audio/wav", "data": base64.b64encode(wav_bytes).decode("ascii")}},
        ], temperature=0.0, fast=True, response_json=True)
        result = self._picture_result(raw)
        if not result["transcript"]:
            raise AIServiceError("no_speech", "Gemini chưa nghe rõ lời nói. Em hãy ghi âm lại một câu ngắn, nói gần microphone hơn.")
        return result


gemini = GeminiService()
