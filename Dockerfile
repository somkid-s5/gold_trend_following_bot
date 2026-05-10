# --- STAGE 1: Build Frontend ---
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- STAGE 2: Run Unified Backend & Engine ---
FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install (MT5 will be skipped automatically on Linux)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Project Files
COPY src/ ./src/
COPY api/ ./api/
COPY config/ ./config/
COPY main.py .

# Copy built frontend
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Unified Entry Point: รันทั้ง API และ Dashboard ในคำสั่งเดียว
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
