# Use Python 3.10 slim as the base image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Install basic system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    xvfb \
    xauth \
    which \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and browser dependencies for Chromium
# This automatically handles downloading chromium and running apt-get for OS library dependencies
RUN playwright install --with-deps chromium

# Copy the rest of the application code
COPY . .

# Expose port
EXPOSE 8000

# Default command to start the FastAPI server.
# We run uvicorn directly (using shell execution format to dynamically bind to the $PORT assigned by Railway).
# Xvfb is not needed by the main server process because all browser operations are isolated in short-lived subprocesses.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]


