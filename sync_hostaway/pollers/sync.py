import logging

from sync_hostaway.config import DRY_RUN
from sync_hostaway.logging_config import setup_logging
from sync_hostaway.services.sync import sync_all_accounts

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


def main() -> None:
    # Run a full sync across all active accounts
    sync_all_accounts(dry_run=DRY_RUN)


if __name__ == "__main__":
    main()
