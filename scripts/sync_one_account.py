import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging

from sync_hostaway.logging_config import setup_logging
from sync_hostaway.services.sync import SyncMode, sync_account

setup_logging()
logger = logging.getLogger(__name__)


def main() -> None:
    """
    Sync a single hardcoded Hostaway account (ID: 59808) using FULL sync mode.
    """
    account_id = 59808

    logger.info("Starting FULL sync for account_id=%s", account_id)

    try:
        sync_account(
            account_id=account_id,
            mode=SyncMode.FULL,
            dry_run=False,  # Set True if you only want to log
        )
        logger.info("Sync completed for account_id=%s", account_id)
    except Exception:
        logger.exception("Sync failed for account_id=%s", account_id)
        raise


if __name__ == "__main__":
    main()
