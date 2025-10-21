from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from sync_hostaway.config import SCHEMA
from sync_hostaway.models.base import Base


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = {"schema": SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=False)  # Hostaway listing ID
    account_id = Column(
        Integer,
        ForeignKey(f"{SCHEMA}.accounts.account_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id = Column(UUID, nullable=True, index=True)  # To be defined
    raw_payload = Column(JSONB, nullable=False)  # Full raw listing blob
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
