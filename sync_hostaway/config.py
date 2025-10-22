import os

from dotenv import load_dotenv

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
DEBUG = LOG_LEVEL == "DEBUG"

DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL must be set in the environment")

SCHEMA = "hostaway"

ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS")
if not ALLOWED_ORIGINS_RAW:
    raise ValueError("ALLOWED_ORIGINS must be set in the environment")

ALLOWED_ORIGINS: list[str] = [
    origin.strip() for origin in ALLOWED_ORIGINS_RAW.split(",")
]
