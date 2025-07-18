from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from sync_hostaway.config import SCHEMA
from sync_hostaway.models.base import Base


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = {"schema": SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=False)  # Hostaway listing ID
    raw_payload = Column(JSONB, nullable=False)  # Full raw listing blob

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
