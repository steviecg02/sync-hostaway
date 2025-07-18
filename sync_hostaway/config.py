import os

from dotenv import load_dotenv

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
DEBUG = LOG_LEVEL == "DEBUG"

HOSTAWAY_ACCESS_TOKEN = os.getenv("HOSTAWAY_ACCESS_TOKEN")
HOSTAWAY_CLIENT_ID = os.getenv("HOSTAWAY_CLIENT_ID")
HOSTAWAY_CLIENT_SECRET = os.getenv("HOSTAWAY_CLIENT_SECRET")

DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

DATABASE_URL = os.getenv("DATABASE_URL")
SCHEMA = "hostaway"
