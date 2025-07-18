# models/reservations.py

from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from sync_hostaway.config import SCHEMA
from sync_hostaway.models.base import Base


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = {"schema": SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=False)  # Hostaway reservation ID
    listing_id = Column(
        Integer, ForeignKey(f"{SCHEMA}.listings.id", ondelete="CASCADE"), nullable=False
    )
    raw_payload = Column(JSONB, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
