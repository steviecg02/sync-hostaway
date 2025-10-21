from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection


def account_exists(conn: Connection, account_id: int) -> bool:
    """
    Check if a Hostaway account already exists in the database.

    Args:
        conn (Connection): An active SQLAlchemy database connection.
        account_id (int): Hostaway account ID to check.

    Returns:
        bool: True if the account exists, False otherwise.
    """
    result = conn.execute(
        text("SELECT 1 FROM hostaway.accounts WHERE account_id = :account_id"),
        {"account_id": account_id},
    )
    return result.fetchone() is not None


def get_account_credentials(conn: Connection, account_id: int) -> Optional[dict[str, str]]:
    """
    Fetch access_token and client_secret for the given Hostaway account.

    Args:
        conn (Connection): An active SQLAlchemy database connection.
        account_id (int): Hostaway account ID

    Returns:
        Optional[dict[str, str]]: Dict with 'access_token' and 'client_secret' or None if not found
    """
    result = conn.execute(
        text(
            """
            SELECT access_token, client_secret
            FROM hostaway.accounts
            WHERE account_id = :account_id AND is_active = TRUE
        """
        ),
        {"account_id": account_id},
    )
    row = result.mappings().fetchone()
    return dict(row) if row else None


def get_client_secret(conn: Connection, account_id: int) -> Optional[str]:
    """
    Get the client_secret for a given account_id.

    Args:
        conn (Connection): SQLAlchemy DB connection.
        account_id (int): Hostaway account ID.

    Returns:
        Optional[str]: Client secret or None if not found.
    """
    result = conn.execute(
        text(
            """
            SELECT client_secret
            FROM hostaway.accounts
            WHERE account_id = :account_id AND is_active = TRUE
        """
        ),
        {"account_id": account_id},
    )
    row = result.fetchone()
    return row[0] if row else None


def get_access_token_only(conn: Connection, account_id: int) -> Optional[str]:
    """
    Get access_token for a given account_id.

    Args:
        conn (Connection): SQLAlchemy DB connection.
        account_id (int): Hostaway account ID.

    Returns:
        Optional[str]: Access token string or None
    """
    result = conn.execute(
        text(
            """
            SELECT access_token
            FROM hostaway.accounts
            WHERE account_id = :account_id AND is_active = TRUE
        """
        ),
        {"account_id": account_id},
    )
    row = result.fetchone()
    return row[0] if row else None


def get_account_with_sync_status(conn: Connection, account_id: int) -> Optional[dict[str, Any]]:
    """
    Get account details including sync status for update operations.
    
    Args:
        conn (Connection): SQLAlchemy DB connection.
        account_id (int): Hostaway account ID.
    
    Returns:
        Optional[dict]: Account details including client_secret and last_sync_at
    """
    result = conn.execute(
        text(
            """
            SELECT client_secret, last_sync_at, is_active
            FROM hostaway.accounts
            WHERE account_id = :account_id
        """
        ),
        {"account_id": account_id},
    )
    row = result.fetchone()
    if row:
        return {
            "client_secret": row[0],
            "last_sync_at": row[1],
            "is_active": row[2]
        }
    return None
