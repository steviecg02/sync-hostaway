import logging

from sync_hostaway.services.sync import run_sync

logger = logging.getLogger(__name__)


def run() -> None:
    """Run the main sync process."""
    run_sync()


def main() -> None:
    """Entrypoint for script execution."""
    run()


if __name__ == "__main__":
    main()
