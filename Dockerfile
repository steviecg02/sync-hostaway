# ----------- Build stage (installs dependencies) -----------
    FROM python:3.11-slim AS builder

    WORKDIR /app

    # Install build tools for psycopg2
    RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ libpq-dev curl build-essential && \
        rm -rf /var/lib/apt/lists/*

    COPY requirements.txt dev-requirements.txt ./
    RUN pip install --upgrade pip
    RUN pip install --prefix=/install -r requirements.txt -r dev-requirements.txt


    # ----------- Runtime stage -----------
    FROM python:3.11-slim AS runtime

    WORKDIR /app

    # Install runtime dependencies for PostgreSQL
    RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 && \
        rm -rf /var/lib/apt/lists/*

    # Copy installed dependencies from builder stage
    COPY --from=builder /install /usr/local
    COPY . .

    # Copy and set up entrypoint script
    COPY entrypoint.sh /entrypoint.sh
    RUN chmod +x /entrypoint.sh

    ENV PYTHONUNBUFFERED=1

    ENTRYPOINT ["/entrypoint.sh"]
    CMD ["uvicorn", "sync_hostaway.main:app", "--host", "0.0.0.0", "--port", "8000"]
