# Dockerfile
FROM python:3.13-slim

# Install system dependencies (C++ compiler for scraper)
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project code
COPY . .

# Copy entrypoint and make executable
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose port for Gunicorn
EXPOSE 8000

# Run entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]