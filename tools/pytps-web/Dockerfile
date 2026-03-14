# Stage 1: Build frontend
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend + frontend static files
FROM python:3.11-slim

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY --from=frontend /app/frontend/dist ./frontend/dist
COPY backend/data/ ./default-data/
COPY docker/entrypoint.sh /usr/local/bin/pytps-entrypoint
RUN chmod +x /usr/local/bin/pytps-entrypoint

RUN mkdir -p /data/images /data/output /data/config

EXPOSE 8000

ENTRYPOINT ["pytps-entrypoint"]
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
