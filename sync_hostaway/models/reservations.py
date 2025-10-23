# models/reservations.py

from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from sync_hostaway.config import SCHEMA
from sync_hostaway.models.base import Base


class Reservation(Base):
    """
    ORM model for Hostaway reservations (bookings).

    Stores the complete raw JSON payload from Hostaway's reservations API endpoint.
    Each reservation represents a guest booking for a specific listing within a date range.
    The raw_payload contains all booking details including guest information, check-in/out
    dates, pricing, payment status, and booking channel information.
    """

    __tablename__ = "reservations"
    __table_args__ = {"schema": SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=False)  # Hostaway reservation ID
    account_id = Column(
        Integer,
        ForeignKey(f"{SCHEMA}.accounts.account_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id = Column(UUID, nullable=True, index=True)  # To be defined
    listing_id = Column(
        Integer, ForeignKey(f"{SCHEMA}.listings.id", ondelete="CASCADE"), nullable=False
    )
    raw_payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
