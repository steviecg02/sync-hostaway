from typing import Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from sync_hostaway.config import DRY_RUN
from sync_hostaway.db.engine import engine
from sync_hostaway.db.readers.accounts import get_account_with_sync_status
from sync_hostaway.db.writers.accounts import (
    hard_delete_account,
    insert_accounts,
    soft_delete_account,
    update_account,
)
from sync_hostaway.routes._account_helpers import (
    should_trigger_sync_on_update,
    validate_account_exists_or_404,
    validate_account_not_exists_or_422,
    validate_client_secret_or_400,
)
from sync_hostaway.schemas.accounts import AccountCreatePayload, AccountUpdatePayload
from sync_hostaway.services.account_cache import remove_account_from_cache
from sync_hostaway.services.sync import sync_account

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/accounts", status_code=status.HTTP_201_CREATED)
def create_account(
    payload: AccountCreatePayload,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """
    Create or upsert a Hostaway account if it does not exist.

    Args:
        payload: Payload containing account_id, client_secret, and optional customer_id
        background_tasks: FastAPI background task runner

    Returns:
        dict: Message confirming account creation and async sync start
    """
    try:
        # Validate inputs
        validate_client_secret_or_400(payload.client_secret)

        with engine.connect() as conn:
            validate_account_not_exists_or_422(conn, payload.account_id)

        # Insert new account
        insert_accounts(
            engine=engine,
            data=[
                {
                    "account_id": payload.account_id,
                    "client_secret": payload.client_secret,
                    "customer_id": payload.customer_id,
                    "access_token": None,
                    "webhook_id": None,
                }
            ],
        )

        logger.info("account_created", account_id=payload.account_id)

        # Schedule initial sync in background
        background_tasks.add_task(
            sync_account,
            account_id=payload.account_id,
            dry_run=DRY_RUN,
        )

        return {"message": "Account created. Token configuration scheduled in background."}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("account_creation_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/accounts/{account_id}/sync", status_code=status.HTTP_202_ACCEPTED)
def trigger_sync(
    account_id: int,
    background_tasks: BackgroundTasks,
    dry_run: Optional[bool] = Query(None, description="Override DRY_RUN setting"),
) -> dict[str, str]:
    """
    Manually trigger a full sync for an existing account.

    Performs a complete sync of all listings, reservations, and messages for
    the specified account. The sync runs in the background.

    Args:
        account_id: Hostaway account ID to sync
        background_tasks: FastAPI background task runner
        dry_run: Override DRY_RUN setting (optional)

    Returns:
        dict: Message confirming sync has been scheduled
    """
    try:
        # Validate account exists
        with engine.connect() as conn:
            validate_account_exists_or_404(conn, account_id)

        # Determine dry_run mode
        use_dry_run = DRY_RUN if dry_run is None else dry_run

        # Schedule sync in background
        background_tasks.add_task(
            sync_account,
            account_id=account_id,
            dry_run=use_dry_run,
        )

        logger.info("sync_triggered", account_id=account_id, dry_run=use_dry_run)

        return {"message": f"Sync scheduled for account {account_id} (dry_run={use_dry_run})"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("sync_trigger_failed", account_id=account_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/accounts/{account_id}", status_code=status.HTTP_200_OK)
def update_account_endpoint(
    account_id: int,
    payload: AccountUpdatePayload,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """
    Update an existing account. Triggers sync if client_secret changed and never synced before.

    Args:
        account_id: Hostaway account ID to update
        payload: Fields to update
        background_tasks: FastAPI background task runner

    Returns:
        dict: Message confirming update
    """
    try:
        with engine.begin() as conn:
            # Get current account state
            account_info = get_account_with_sync_status(conn, account_id)

            if not account_info or not account_info["is_active"]:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Account {account_id} not found or inactive",
                )

            # Build update dict (only non-None values)
            update_data = {k: v for k, v in payload.model_dump().items() if v is not None}

            if not update_data:
                return {"message": "No fields to update"}

            # Execute update
            update_account(conn, account_id, update_data)

        # Check if we should trigger sync
        if should_trigger_sync_on_update(account_info, update_data):
            background_tasks.add_task(
                sync_account,
                account_id=account_id,
                dry_run=DRY_RUN,
            )
            logger.info(
                "account_updated_sync_triggered",
                account_id=account_id,
                reason="credentials_changed_never_synced",
            )
            return {
                "message": (
                    f"Account {account_id} updated. "
                    f"Sync triggered (new credentials, never synced before)."
                )
            }

        logger.info("account_updated", account_id=account_id)
        return {"message": f"Account {account_id} updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("account_update_failed", account_id=account_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/accounts/{account_id}", status_code=status.HTTP_200_OK)
def delete_account_endpoint(
    account_id: int,
    soft: bool = Query(True, description="Soft delete (set is_active=false) vs hard delete"),
) -> dict[str, str]:
    """
    Delete an account (soft delete by default).

    Args:
        account_id: Hostaway account ID to delete
        soft: If True, soft delete (set is_active=false). If False, permanently delete

    Returns:
        dict: Message confirming deletion
    """
    try:
        with engine.begin() as conn:
            # Validate account exists
            validate_account_exists_or_404(conn, account_id)

            if soft:
                soft_delete_account(conn, account_id)
                logger.info("account_soft_deleted", account_id=account_id)
                message = f"Account {account_id} deactivated (soft delete)"
            else:
                hard_delete_account(conn, account_id)
                logger.info("account_hard_deleted", account_id=account_id)
                message = f"Account {account_id} permanently deleted"

        # Remove from cache so webhooks fail for this account
        remove_account_from_cache(account_id)

        return {"message": message}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("account_deletion_failed", account_id=account_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")
