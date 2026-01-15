# ═══════════════════════════════════════════════════════════════════════════
# MRAYEH - Sales Tracking & Planning Platform
# ═══════════════════════════════════════════════════════════════════════════

FROM python:3.12-slim

# Build args
ARG APP_ENV=production

# Labels
LABEL org.opencontainers.image.title="mrayeh"
LABEL org.opencontainers.image.description="Sales tracking and planning platform for food production"
LABEL org.opencontainers.image.source="https://github.com/djwawa/mrayeh"

# Environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_ENV=${APP_ENV}

# Working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY scripts/ ./scripts/

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command (can be overridden)
CMD ["python", "-m", "src.main"]
