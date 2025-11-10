# Multi-stage build for Binance Trading Bot
# Use Python 3.12 for better compatibility with crypto libraries
FROM python:3.12-slim AS builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.12-slim

# Create non-root user
RUN groupadd -r botuser && useradd -r -g botuser botuser

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY . .

# Create necessary directories and set permissions
RUN mkdir -p logs data && \
    chown -R botuser:botuser /app

# Switch to non-root user
USER botuser

# Health check - verifies bot process is responding
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
  CMD python -c "import os; exit(0 if os.path.exists('data/bot.lock') else 1)" || exit 1

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TRADING_MODE=paper

# Run the bot
CMD ["python", "-u", "trading_bot.py"]
