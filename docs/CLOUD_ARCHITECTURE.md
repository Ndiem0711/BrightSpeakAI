# BrightSpeakAI V13 cloud architecture

HTTPS browser → FastAPI HTTP/WebSocket service → persistent PostgreSQL. Backend calls Gemini Pro for text/image/audio requests and a separate Gemini Live model for streaming audio/video. Keys stay server-side.

`render.yaml` provisions a web service and PostgreSQL. `Dockerfile` is an alternative build source. Auth uses the existing server JWT/password implementation, not Firebase Authentication. There is no evidence of a deployed V13 URL at delivery. See `CLOUD_V13.md`.

Media is processed in memory by default; metadata and practice results are stored in the database. `assessment_details` stores the assessment method, word comparison and qualitative feedback linked to an attempt. Model input/output and recordings require an appropriate consent and retention policy before real school use.

Learning recommendations only include active lessons for the student's grade and valid teacher assignments. Manual transcript tests do not enter progress.
