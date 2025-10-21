"""FastAPI app definition and route registration."""

from fastapi import FastAPI

from sync_hostaway.logging_config import setup_logging
from sync_hostaway.routes.accounts import router as accounts_router
from sync_hostaway.routes.webhook import router as webhook_router

setup_logging()

app = FastAPI()

# Register routers
app.include_router(accounts_router, prefix="/accounts")
app.include_router(webhook_router, prefix="/webhook")
