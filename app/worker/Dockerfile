FROM python:3.10-slim

# Install system dependencies for analysis tools
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install TruffleHog (v3)
RUN curl -sSfL https://raw.githubusercontent.com/trufflehog/trufflehog/main/scripts/install.sh | sh -s -- -b /usr/local/bin

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Default command: run the SQS worker loop
CMD ["python", "main.py"]
