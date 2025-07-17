from sqlalchemy import create_engine

from sync_hostaway.config import DATABASE_URL


def get_engine():
    """
    Returns a SQLAlchemy engine using DATABASE_URL.
    """
    if not DATABASE_URL:
        raise Exception("DATABASE_URL is not set in environment.")
    return create_engine(DATABASE_URL)
