# Build stage
FROM python:3.10-alpine as builder

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/hospital_management

# Install only the build dependencies needed for psycopg2 (PostgreSQL Python adapter)
RUN apk add --no-cache \
    postgresql-dev \
    gcc \
    python3-dev

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.10-alpine

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/hospital_management \
    PATH="/opt/venv/bin:$PATH"

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Install only the runtime dependencies needed for PostgreSQL client
RUN apk add --no-cache \
    postgresql-libs \
    postgresql-client \
    supervisor \
    && addgroup -S hospital_group \
    && adduser -S hospital_user -G hospital_group -h "${APP_HOME}" -s /bin/sh

# Create necessary directories
RUN mkdir -p ${APP_HOME}/static \
            ${APP_HOME}/mediafiles \
            ${APP_HOME}/staticfiles

WORKDIR ${APP_HOME}

# Copy configuration files and project files
COPY --chown=hospital_user:hospital_group entrypoint.sh ${APP_HOME}/entrypoint.sh
COPY --chown=hospital_user:hospital_group . .

# Set permissions
RUN chmod +x ${APP_HOME}/entrypoint.sh && \
    chmod -R 775 "${APP_HOME}/staticfiles"

USER hospital_user

EXPOSE 8000

ENTRYPOINT ["sh", "entrypoint.sh"]
