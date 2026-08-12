# Multi-stage build kept single-stage deliberately — this is a Django
# app with no compiled frontend assets of its own to build away; the
# only "build step" is pip install, which layers cleanly on its own.
FROM python:3.12-slim

# psycopg2 (Postgres driver) needs libpq at runtime; build-essential is
# only needed transiently to compile it if a wheel isn't available for
# this exact platform, so it's removed in the same layer to keep the
# final image smaller.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home appuser
RUN mkdir -p /app/staticfiles /app/media && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
# Daphne (ASGI), not Gunicorn (WSGI) — this app now serves both ordinary
# HTTP requests AND WebSocket connections (see nsaabodeeq/asgi.py,
# realtime/consumers.py) through one process, which a WSGI server like
# Gunicorn has no protocol for at all.
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "nsaabodeeq.asgi:application"]
