FROM python:3.12-slim

# Security: don't run as root
RUN groupadd -r vigil && useradd -r -g vigil vigil

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt requirements-test.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Copy skills and prompts from repo root
# (In Docker Compose, these are mounted from the repo root)
# RUN mkdir -p /skills /prompts

# Ensure no write permissions on source
RUN chown -R vigil:vigil /app
USER vigil

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
