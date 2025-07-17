import logging

from sync_hostaway.config import LOG_LEVEL


def setup_logging():
    """
    Configures logging globally, with file + line number, and suppresses noisy libraries.
    """
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s %(levelname)s %(name)s [%(filename)s:%(lineno)d] %(message)s",
    )

    # Suppress noise from common libraries
    for noisy_logger in ["urllib3", "requests", "botocore", "boto3"]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)
