"""SQLAlchemy model for Hostaway-connected PMS accounts."""

from sqlalchemy import TIMESTAMP, Boolean, Column, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID

from sync_hostaway.models.base import Base


class Account(Base):
    """
    ORM model for connected Hostaway accounts.

    Each account is uniquely identified by Hostaway's provided account_id.
    Credentials and tokens are stored per account, with optional webhook auth support.
    """

    __tablename__ = "accounts"
    __table_args__ = {"schema": "hostaway"}

    account_id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(UUID, nullable=True, index=True)  # To be defined
    client_secret = Column(String, nullable=True)
    access_token = Column(String, nullable=True)
    webhook_login = Column(String, nullable=True)
    webhook_password = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default=text("TRUE"))
    last_sync_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
