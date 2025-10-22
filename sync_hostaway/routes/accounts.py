import logging
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from sync_hostaway.config import DRY_RUN
from sync_hostaway.db.engine import engine
from sync_hostaway.db.readers.accounts import account_exists, get_account_with_sync_status
from sync_hostaway.db.writers.accounts import (
    hard_delete_account,
    insert_accounts,
    soft_delete_account,
    update_account,
)
from sync_hostaway.schemas.accounts import AccountCreatePayload, AccountUpdatePayload
from sync_hostaway.services.sync import sync_account

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/accounts", status_code=status.HTTP_201_CREATED)
def create_account(
    payload: AccountCreatePayload,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """
    Create or upsert a Hostaway account if it does not exist.

    Args:
        payload (AccountCreatePayload): Payload containing account_id, client_secret, and optional
                                        customer_id.
        background_tasks (BackgroundTasks): FastAPI background task runner

    Returns:
        dict: Message confirming account creation and async sync start.
    """
    try:
        if not payload.client_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Client secret is required"
            )

        with engine.connect() as conn:
            if account_exists(conn, payload.account_id):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Account {payload.account_id} already exists",
                )

        insert_accounts(
            engine=engine,
            data=[
                {
                    "account_id": payload.account_id,
                    "client_secret": payload.client_secret,
                    "customer_id": payload.customer_id,
                    "access_token": None,
                    "webhook_login": None,
                    "webhook_password": None,
                }
            ],
        )

        logger.info("[POST /accounts] Account %s inserted into DB", payload.account_id)

        background_tasks.add_task(
            sync_account,
            account_id=payload.account_id,
            dry_run=DRY_RUN,
        )

        return {"message": "Account created. Token configuration scheduled in background."}

    except HTTPException:
        raise

    except Exception:
        logger.exception("Unexpected error during account creation")
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
        with engine.connect() as conn:
            if not account_exists(conn, account_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Account {account_id} not found",
                )

        use_dry_run = DRY_RUN if dry_run is None else dry_run

        background_tasks.add_task(
            sync_account,
            account_id=account_id,
            dry_run=use_dry_run,
        )

        logger.info(
            "[POST /accounts/%s/sync] Sync triggered (dry_run=%s)",
            account_id, use_dry_run
        )

        return {"message": f"Sync scheduled for account {account_id} (dry_run={use_dry_run})"}

    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error triggering sync for account %s", account_id)
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
            # Check if account exists and get current state
            account_info = get_account_with_sync_status(conn, account_id)
            
            if not account_info or not account_info["is_active"]:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Account {account_id} not found or inactive",
                )
            
            # Build update dict with only non-None values
            update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
            
            if not update_data:
                return {"message": "No fields to update"}
            
            # Execute update
            update_account(conn, account_id, update_data)
            
            # Check if we should trigger sync
            client_secret_changed = (
                "client_secret" in update_data and 
                update_data["client_secret"] != account_info["client_secret"]
            )
            never_synced = account_info["last_sync_at"] is None
            
            if client_secret_changed and never_synced:
                background_tasks.add_task(
                    sync_account,
                    account_id=account_id,
                    dry_run=DRY_RUN,
                )
                logger.info(
                    "[PATCH /accounts/%s] Updated and triggered sync (credentials changed, never synced)",
                    account_id
                )
                return {"message": f"Account {account_id} updated. Sync triggered (new credentials, never synced before)."}
            
            logger.info("[PATCH /accounts/%s] Account updated", account_id)
            return {"message": f"Account {account_id} updated successfully"}
    
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error updating account %s", account_id)
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
        soft: If True, soft delete (set is_active=false). If False, permanently delete.
    
    Returns:
        dict: Message confirming deletion
    """
    try:
        with engine.begin() as conn:
            # Check if account exists
            if not account_exists(conn, account_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Account {account_id} not found",
                )
            
            if soft:
                # Soft delete - set is_active to false
                soft_delete_account(conn, account_id)
                logger.info("[DELETE /accounts/%s] Account soft deleted", account_id)
                return {"message": f"Account {account_id} deactivated (soft delete)"}
            else:
                # Hard delete - permanently remove
                hard_delete_account(conn, account_id)
                logger.info("[DELETE /accounts/%s] Account hard deleted", account_id)
                return {"message": f"Account {account_id} permanently deleted"}
    
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error deleting account %s", account_id)
        raise HTTPException(status_code=500, detail="Internal server error")
