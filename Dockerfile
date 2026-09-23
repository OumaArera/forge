# ---------------------------------------------------------------------------
# FORGE backend
#
# Containerised specifically so that the platform can be migrated onto
# University infrastructure at any time the University wishes, without the
# student team having to be involved. Nothing here depends on a particular
# cloud provider: it needs a container runtime, PostgreSQL and Redis.
# ---------------------------------------------------------------------------

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user. If the container is ever compromised, this is the
# difference between an incident and a much worse incident.
RUN useradd --create-home --uid 10001 forge \
 && mkdir -p /app/staticfiles /app/media \
 && chown -R forge:forge /app
USER forge

RUN DJANGO_SETTINGS_MODULE=config.settings.dev \
    DJANGO_SECRET_KEY=build-time-only \
    python manage.py collectstatic --noinput --clear

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:8000/healthz/ || exit 1

CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
