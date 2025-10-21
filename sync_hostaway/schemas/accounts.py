from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AccountCreatePayload(BaseModel):
    """
    Schema for creating a new account with optional customer_id.
    """

    account_id: int = Field(..., description="Hostaway account ID")
    client_secret: str = Field(..., description="Client secret for access token generation")
    customer_id: Optional[UUID] = Field(None, description="Internal customer UUID (optional)")


class AccountUpdatePayload(BaseModel):
    """
    Schema for updating an existing account. All fields are optional.
    Note: last_sync_at is automatically managed by the system.
    """

    customer_id: Optional[UUID] = Field(None, description="Internal customer UUID")
    client_secret: Optional[str] = Field(None, description="Client secret for access token generation")
    access_token: Optional[str] = Field(None, description="Access token (usually auto-generated)")
    webhook_login: Optional[str] = Field(None, description="Webhook authentication login")
    webhook_password: Optional[str] = Field(None, description="Webhook authentication password")
    is_active: Optional[bool] = Field(None, description="Account active status")
