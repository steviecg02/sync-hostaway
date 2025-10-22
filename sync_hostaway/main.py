# sync_hostaway/main.py

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sync_hostaway.config import ALLOWED_ORIGINS
from sync_hostaway.logging_config import setup_logging
from sync_hostaway.routes.accounts import router as accounts_router
from sync_hostaway.routes.webhook import router as webhook_router

# Initialize structured logging
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Hostaway Sync API",
    description="API for managing Hostaway account sync and credentials",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if "*" not in ALLOWED_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(accounts_router, prefix="/hostaway", tags=["Accounts"])
app.include_router(webhook_router, prefix="/hostaway", tags=["Webhooks"])

logger.info("FastAPI application initialized")
