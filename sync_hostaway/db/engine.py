from sqlalchemy import create_engine

from sync_hostaway.config import DATABASE_URL

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set.")

engine = create_engine(DATABASE_URL, future=True)
