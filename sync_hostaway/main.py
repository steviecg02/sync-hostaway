import logging

from sync_hostaway.services.sync import run_sync

logger = logging.getLogger(__name__)


def run():
    run_sync()


if __name__ == "__main__":
    run()
