# SRS: BrightSpeak AI English Speaking Lab

## Goal
Support grade 1–5 English speaking practice, transparent AI assisted feedback and teacher oversight. Do not replace official assessment.

## Functional requirements

- FR01: Student registration, verification, login, logout, password change, profile edit, own-grade selection.
- FR02: Grade-specific pronunciation lessons and original curriculum-themed text dataset.
- FR03: Record PCM WAV; obtain real transcription through Gemini or optional Whisper; calculate heuristic feedback; store progression, never claim phonemic validation.
- FR04: Student text and voice conversation with user-selectable or original topic; backend Gemini REST with no key in frontend.
- FR05: Look & Speak accepts picture + actual audio recording; ASR transcript and Gemini image analysis; no fabricated score on API failure.
- FR06: Gemini Live WebSocket audio output/input plus opt-in video frame streaming; do not infer emotions, personality, intelligence or performance from faces.
- FR07: Teacher sees only assigned students; admin can activate/deactivate accounts, assign students and add lessons.
- FR08: Local first-run PowerShell launcher prompts Gemini key and starts one FastAPI server.
- FR09: Cloud Run and Cloud SQL deployment templates; actual deployment requires credentials, SMTP and secure secrets.
- FR10: Optional pretrained Whisper DL and speaker-held-out Speech Commands keyword model training.

## Non-functional requirements

- Mic/camera on HTTPS or loopback; useful error messages on denied access; cleanup of stopped streams.
- User data protected behind authenticated endpoints and server-enforced roles; no raw audio or webcam storage in application by default.
- Secure JWT secret and real OTP delivery required in production; no demo users on Cloud.
- Explicit caregiver consent before sending camera frames; separate privacy policy needed for school or business deployments.
- Key must never be hardcoded in frontend or shared files.

## Not implemented / not claimed

- Validated child emotion or eye-gaze scoring; phoneme-level expert-validated pronunciation scoring; fully licensed Global Success copyrighted lessons; deployment to the user's GCP account; per-school tenancy; paid subscriptions and payment integration.
