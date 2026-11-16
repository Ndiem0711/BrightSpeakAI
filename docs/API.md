# API summary

- GET `/api/v1/system/health` — environment & AI readiness
- POST `/api/v1/auth/register`, `/api/v1/auth/verify`, `/api/v1/auth/login`, `/api/v1/auth/refresh` — account workflow
- GET `/api/v1/auth/me`, PATCH `/api/v1/profile`, POST `/api/v1/profile/password` — profile and password
- GET `/api/v1/lessons?grade=3` — lesson bank by grade
- POST `/api/v1/pronunciation/analyze` — form `lesson_id`, `audio` (WAV), optional `demo_transcript`; score heuristic, optional keyword ML metadata
- GET `/api/v1/conversation/topics` — teacher-reviewed topics per student grade
- POST `/api/v1/conversation/message` — JSON `topic`, `text`, Gemini response
- POST `/api/v1/conversation/voice` — form `topic`, `audio` WAV; actual ASR + Gemini reply
- POST `/api/v1/multimodal/look-speak` — form `image`, optional `audio` WAV OR `answer`, returns Gemini image relevance and transcript
- WS `/api/v1/live/ws` — initial JSON authentication, PCM 16 kHz input, optional JPEG frames with consent, receives PCM 24 kHz output + transcript
- GET `/api/v1/progress/me`, GET `/api/v1/teacher/overview` — student progress and assigned teacher scope
- GET `/api/v1/admin/overview`, PATCH `/api/v1/admin/users/{id}/active?active=true`, POST `/api/v1/admin/teacher-students`, POST `/api/v1/admin/lessons` — admin

All learning and personal-data APIs require bearer token; public-only `/api/v1/system/health` exposes no secrets.
