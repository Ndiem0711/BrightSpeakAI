"""Validate that a key is configured, without contacting Gemini or revealing secrets."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import GEMINI_API_KEY
if not GEMINI_API_KEY or GEMINI_API_KEY.strip().lower() in {"your-key", "your_api_key", "paste-here"}:
    print("ERROR: GEMINI_API_KEY is missing or looks like a placeholder. Edit GEMINI_KEY.txt or .env.")
    raise SystemExit(1)
print("Gemini key detected (external API/quota not verified).")
