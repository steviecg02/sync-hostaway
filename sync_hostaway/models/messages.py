from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB

from sync_hostaway.config import SCHEMA
from sync_hostaway.models.base import Base


class MessageThread(Base):
    __tablename__ = "messages"
    __table_args__ = {"schema": SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=True)
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
