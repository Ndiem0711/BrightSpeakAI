"""Real ASR: Gemini API or optional local Whisper (pretrained deep learning)."""
from __future__ import annotations
import io
import tempfile
import os
from pathlib import Path
from .config import ASR_ENGINE, WHISPER_MODEL
from .gemini import gemini

class ASRUnavailable(RuntimeError):
    pass

class _ASR:
    _model = None
    def available(self):
        return gemini.enabled or self._whisper_installed()
    @staticmethod
    def _whisper_installed():
        try:
            import faster_whisper  # noqa: F401
            return True
        except ImportError:
            return False
    def __call__(self, wav: bytes) -> tuple[str,str]:
        # Prefer configured Gemini; optional Whisper can run without cloud.
        if ASR_ENGINE in {"auto", "gemini"} and gemini.enabled:
            try:
                result = gemini.transcribe_wav(wav).strip()
                if result: return result, "gemini"
            except Exception as exc:
                if ASR_ENGINE == "gemini": raise ASRUnavailable(f"Gemini ASR failed: {str(exc)[:140]}") from exc
        if ASR_ENGINE in {"auto", "whisper"} and self._whisper_installed():
            try:
                from faster_whisper import WhisperModel
                if self._model is None:
                    self._model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
                    handle.write(wav)
                    filename = handle.name
                try:
                    segments, _info = self._model.transcribe(filename, language="en", beam_size=3)
                    result = " ".join(seg.text.strip() for seg in segments).strip()
                finally:
                    Path(filename).unlink(missing_ok=True)
                if result: return result, "whisper-dl"
            except Exception as exc:
                raise ASRUnavailable(f"Offline Whisper failed: {str(exc)[:180]}") from exc
        raise ASRUnavailable("Chưa có ASR thật: hãy nhập Gemini API key trong PowerShell hoặc cài requirements-ml.txt để dùng Whisper. Không tạo điểm phát âm giả.")
transcribe_audio = _ASR()
