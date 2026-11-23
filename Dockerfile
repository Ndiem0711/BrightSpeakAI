FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt requirements-cloud.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-cloud.txt
COPY app ./app
COPY data ./data
COPY ml ./ml
COPY scripts ./scripts
COPY .env.example AI_MODELS.txt VERSION.txt ./
RUN mkdir -p /app/runtime /app/logs
ENV APP_ENV=cloud APP_HOST=0.0.0.0 PORT=8080
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
