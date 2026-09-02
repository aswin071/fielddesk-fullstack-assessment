FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements /app/requirements
RUN pip install --upgrade pip && pip install -r /app/requirements/development.txt

COPY backend /app/backend
COPY backend/scripts /app/scripts
RUN chmod +x /app/scripts/*.sh

WORKDIR /app/backend
EXPOSE 8000

CMD ["/app/scripts/start-api.sh"]

