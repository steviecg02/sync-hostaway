"""
SQLAlchemy engine singleton with production-ready connection pooling.

This module creates a single engine instance with connection pooling configured
for high-load production environments. The pool settings are optimized for
typical web application workloads with concurrent requests.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from sync_hostaway.config import DATABASE_URL

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set.")

# Create engine with production-ready connection pooling
engine: Engine = create_engine(
    DATABASE_URL,
    future=True,
    # Connection pool settings
    pool_size=10,  # Number of connections to maintain in the pool
    max_overflow=20,  # Additional connections when pool is exhausted
    pool_pre_ping=True,  # Verify connections before using (detect stale connections)
    pool_recycle=3600,  # Recycle connections after 1 hour (prevents stale connections)
    # Logging (set to True for SQL debugging in development)
    echo=False,
)


def check_engine_health() -> bool:
    """
    Check if database engine is healthy and connections are working.

    This function is used by the /ready endpoint to verify database
    connectivity before allowing traffic to the service.

    Returns:
        bool: True if database is reachable and healthy, False otherwise

    Example:
        >>> if check_engine_health():
        ...     print("Database is healthy")
        ... else:
        ...     print("Database is down")
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
