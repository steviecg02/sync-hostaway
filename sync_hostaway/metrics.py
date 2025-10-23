"""
Prometheus metrics for monitoring sync operations, API calls, and database operations.

This module defines all Prometheus metrics used throughout the application for
observability and monitoring. Metrics are exposed via the /metrics endpoint for
scraping by Prometheus.

Metric Types:
    - Counter: Cumulative metrics that only increase (e.g., total API requests)
    - Histogram: Observations bucketed by value (e.g., request latency)
    - Gauge: Point-in-time value that can go up or down (e.g., active accounts)

Example:
    >>> from sync_hostaway.metrics import poll_duration, records_synced
    >>> with poll_duration.labels(account_id=123, entity_type="listings").time():
    ...     listings = fetch_listings(123)
    ...     records_synced.labels(account_id=123, entity_type="listings").inc(len(listings))
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# =============================================================================
# Poll Metrics
# =============================================================================

poll_total = Counter(
    "hostaway_polls_total",
    "Total number of polling operations (success and failure)",
    ["account_id", "entity_type", "status"],
)
"""
Counter for total polling operations.

Labels:
    account_id: Hostaway account ID
    entity_type: Type of entity being polled (listings, reservations, messages)
    status: success or failure
"""

poll_duration = Histogram(
    "hostaway_poll_duration_seconds",
    "Duration of polling operations in seconds",
    ["account_id", "entity_type"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, float("inf")),
)
"""
Histogram for polling operation duration.

Labels:
    account_id: Hostaway account ID
    entity_type: Type of entity being polled

Buckets: 0.5s, 1s, 2.5s, 5s, 10s, 30s, 60s, 120s, 300s, +Inf
"""

records_synced = Counter(
    "hostaway_records_synced_total",
    "Total number of records synced to database",
    ["account_id", "entity_type"],
)
"""
Counter for total records synced.

Labels:
    account_id: Hostaway account ID
    entity_type: Type of entity synced (listings, reservations, messages)
"""

# =============================================================================
# API Metrics
# =============================================================================

api_requests = Counter(
    "hostaway_api_requests_total",
    "Total Hostaway API requests made",
    ["endpoint", "status_code"],
)
"""
Counter for API requests to Hostaway.

Labels:
    endpoint: API endpoint path (e.g., "listings", "conversations/123/messages")
    status_code: HTTP status code (e.g., "200", "403", "429")
"""

api_latency = Histogram(
    "hostaway_api_latency_seconds",
    "Hostaway API request latency in seconds",
    ["endpoint"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf")),
)
"""
Histogram for API request latency.

Labels:
    endpoint: API endpoint path

Buckets: 0.1s, 0.25s, 0.5s, 1s, 2.5s, 5s, 10s, +Inf
"""

# =============================================================================
# Database Metrics
# =============================================================================

db_operations = Counter(
    "hostaway_db_operations_total",
    "Total database operations performed",
    ["operation", "table"],
)
"""
Counter for database operations.

Labels:
    operation: Type of operation (insert, update, upsert, select)
    table: Database table name (accounts, listings, reservations, messages)
"""

db_query_duration = Histogram(
    "hostaway_db_query_duration_seconds",
    "Database query execution time in seconds",
    ["operation"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, float("inf")),
)
"""
Histogram for database query duration.

Labels:
    operation: Type of operation (insert, update, upsert, select)

Buckets: 0.01s, 0.05s, 0.1s, 0.25s, 0.5s, 1s, 2.5s, 5s, +Inf
"""

# =============================================================================
# System Metrics
# =============================================================================

active_accounts = Gauge(
    "hostaway_active_accounts",
    "Number of active Hostaway accounts configured in the system",
)
"""
Gauge for active accounts.

This is a point-in-time measurement of how many Hostaway accounts are
currently configured and active in the system.
"""

# =============================================================================
# Token Cache Metrics (Optional)
# =============================================================================

token_cache_hits = Counter(
    "hostaway_token_cache_hits_total",
    "Total number of token cache hits",
)
"""Counter for token cache hits (cache found valid token)."""

token_cache_misses = Counter(
    "hostaway_token_cache_misses_total",
    "Total number of token cache misses",
)
"""Counter for token cache misses (cache had no token or expired token)."""

token_refreshes = Counter(
    "hostaway_token_refreshes_total",
    "Total number of token refresh operations",
    ["account_id"],
)
"""
Counter for token refresh operations.

Labels:
    account_id: Hostaway account ID
"""
