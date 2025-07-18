# ----------- Build stage (installs dependencies) -----------
    FROM python:3.11-slim AS builder

    WORKDIR /app

    # Install build tools for psycopg2-binary if needed
    RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libpq-dev curl && \
        rm -rf /var/lib/apt/lists/*

    COPY requirements.txt dev-requirements.txt ./
    RUN pip install --upgrade pip
    RUN pip install --prefix=/install -r requirements.txt -r dev-requirements.txt


    # ----------- Runtime stage -----------
    FROM python:3.11-slim AS runtime

    WORKDIR /app

    # Copy installed dependencies from builder stage
    COPY --from=builder /install /usr/local
    COPY . .

    ENV PYTHONUNBUFFERED=1

    CMD ["python", "-m", "sync_hostaway.main"]
