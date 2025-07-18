import logging

from sync_hostaway.config import DRY_RUN
from sync_hostaway.logging_config import setup_logging
from sync_hostaway.services.sync import run_sync

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


def main() -> None:
    run_sync(dry_run=DRY_RUN)


if __name__ == "__main__":
    main()
