from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID

from sync_hostaway.config import SCHEMA
from sync_hostaway.models.base import Base


class MessageThread(Base):
    """
    ORM model for guest-host message conversations (threads).

    Stores all messages for a reservation as a normalized JSON array in raw_messages.
    Each thread is associated with a single reservation and contains the complete
    conversation history between the guest and property manager. Messages are fetched
    from Hostaway's conversations API endpoint and normalized before storage.

    The raw_messages field contains an array of message objects, each with:
    - message content
    - sender information
    - timestamp
    - channel (Airbnb, Booking.com, etc.)
    """

    __tablename__ = "messages"
    __table_args__ = {"schema": SCHEMA}

    account_id = Column(
        Integer,
        ForeignKey(f"{SCHEMA}.accounts.account_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id = Column(UUID, nullable=True, index=True)  # To be defined
    reservation_id = Column(
        Integer,
        ForeignKey(f"{SCHEMA}.reservations.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    raw_messages = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
