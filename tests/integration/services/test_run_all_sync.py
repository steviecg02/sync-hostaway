import logging

logger = logging.getLogger(__name__)


def run_all_syncs() -> None:
    """
    Orchestrates sync for each PMS account in the system.

    Not implemented yet. Will query `pms` table and call `run_sync()` with account-scoped config.
    """
    logger.warning("run_all_syncs() called, but multi-account sync is not implemented yet.")
