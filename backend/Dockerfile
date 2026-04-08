FROM python:3.12-slim

WORKDIR /app

# Install system dependencies in a more reliable way
# Split into smaller, more specific installations
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install additional Python packages if not in requirements.txt
RUN pip install --no-cache-dir \
    beautifulsoup4==4.12.3 \
    lxml==5.2.2

# Copy application code
COPY . .

EXPOSE 8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}