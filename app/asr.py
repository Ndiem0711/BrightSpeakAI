"""Gemini-only ASR. Never substitute lesson text for a failed recording."""
from __future__ import annotations
import logging
from .gemini import gemini
from .ai_errors import AIServiceError

logger = logging.getLogger(__name__)

class ASRUnavailable(RuntimeError):
    def __init__(self, message: str, code: str = "asr_unavailable"):
        self.code = code
        super().__init__(message)

class _ASR:
    def available(self) -> bool:
        return gemini.enabled

    def provider(self) -> str:
        return "gemini" if gemini.enabled else "unavailable"

    def __call__(self, wav: bytes) -> tuple[str, str]:
        if not wav:
            raise ASRUnavailable("Bản ghi trống. Em hãy kiểm tra microphone và ghi lại.")
        if not gemini.enabled:
            raise ASRUnavailable("Chưa có Gemini API key. Hãy cấu hình GEMINI_KEY.txt (local) hoặc GEMINI_API_KEY (Cloud), rồi khởi động lại.")
        try:
            transcript = gemini.transcribe_wav(wav).strip()
        except AIServiceError as exc:
            logger.warning("Gemini ASR unavailable: %s", exc.code)
            raise ASRUnavailable(str(exc), code=exc.code) from None
        except (ValueError, TimeoutError, OSError) as exc:
            logger.warning("Gemini ASR technical error: %s", type(exc).__name__)
            raise ASRUnavailable("Không kết nối được Gemini để nhận dạng. Em hãy thử lại sau.") from None
        if not transcript:
            raise ASRUnavailable("Gemini chưa nghe rõ lời nói. Hãy kiểm tra mic, tránh tiếng ồn và nói lại một câu ngắn.")
        return transcript, "gemini"

transcribe_audio = _ASR()
