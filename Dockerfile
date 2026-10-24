FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    BACKEND_HOST=0.0.0.0 \
    DB_PATH=/data/rupee.db

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

# Run as a non-root user; /data holds the SQLite file (mount a volume here).
RUN useradd --create-home --uid 1000 app \
    && mkdir /data \
    && chown app:app /data
USER app

# Both services share this image; docker-compose.prod.yml picks the command.
CMD ["python", "-m", "app.backend"]
