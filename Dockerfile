FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PRODUCTION=true DEMO_MODE=false STATIC_DIR=/app/frontend/dist DATA_DIR=/data
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ ./backend/
# Rebuild synthetic-data models with the installed scikit-learn version.
RUN python -m backend.ml.train
COPY --from=frontend /build/dist ./frontend/dist
CMD ["python", "-m", "backend.deploy"]
