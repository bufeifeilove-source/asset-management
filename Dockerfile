FROM node:24-bookworm AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
ENV MEMORY_WEB_STATIC_DIR=/app/frontend/dist
ENV PYTHONUNBUFFERED=1
COPY pyproject.toml ./
COPY backend ./backend
COPY memory_client.py memory_config.py memory_queue.py memctl.py ./
RUN pip install --no-cache-dir .
COPY --from=frontend /app/frontend/dist ./frontend/dist
EXPOSE 8000
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
