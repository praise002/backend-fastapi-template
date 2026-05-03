# ================================
# STAGE 1: builder
# Install deps in an isolated venv
# ================================
ARG PYTHON_VERSION=3.12-slim-bullseye
FROM python:${PYTHON_VERSION} AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtualenv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip

# Copy and install requirements
# This layer is cached — only re-runs if requirements change
COPY requirements/prod.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt


# ================================
# STAGE 2: runner
# Lean final image — no build tools
# ================================
FROM python:${PYTHON_VERSION} AS runner

# Runtime-only OS dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python env settings
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"
ENV ENVIRONMENT=production

# Copy the venv from builder — NOT gcc, NOT pip, NOT build tools
COPY --from=builder /opt/venv /opt/venv

WORKDIR /code

# Copy project files
COPY . .

# Copy and make runner script executable
COPY scripts/runner.sh ./scripts/runner.sh
RUN chmod +x ./scripts/runner.sh

EXPOSE 8000

CMD ["./scripts/runner.sh"]