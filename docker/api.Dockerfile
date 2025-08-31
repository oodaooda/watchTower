# Dockerfile for watchTower API service
# ------------------------------------
# Purpose: build a lean Python 3.11 image that runs the FastAPI app.
# Notes:
# - Uses a slim base image
# - Installs only what we need from requirements.txt
# - Exposes port 8000 and launches uvicorn

FROM python:3.11-slim

# Prevent .pyc files, enable unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Workdir inside the container
WORKDIR /app

# Install runtime deps
# - We keep build tools minimal; if you add packages needing system libs, extend this
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code (adjust if you restructure)
COPY app /app/app
COPY ops /app/ops

# Network port for uvicorn
EXPOSE 8000

# Default command: run the API (create tables first in docker-compose)
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
