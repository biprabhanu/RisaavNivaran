# PlumeProof: one container. FastAPI serves the API (/api/*, /docs) AND the built React app (/).

# ---------- Stage 1: build the React frontend ----------
FROM node:22-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: Python runtime ----------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    PLUMEPROOF_DB=/tmp/plumeproof.db \
    FRONTEND_DIST=/app/frontend/dist
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend /build/frontend/dist /app/frontend/dist
# Copy the docs too so POST /api/evaluate can refresh docs/EVALUATION.md inside the container.
COPY docs/ /app/docs/
EXPOSE 8000
# Render (and most PaaS) inject $PORT; default 8000 locally. The DB is seeded automatically on startup.
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
