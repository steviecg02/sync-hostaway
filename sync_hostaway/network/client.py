"""
Client module for fetching paginated resources from the Hostaway API
with support for retries, rate limiting, token refresh, and concurrency.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from math import ceil
from typing import Any, Dict, List, Optional, Tuple, cast
from urllib.parse import urljoin

import requests
import structlog

from sync_hostaway.metrics import api_latency, api_requests
from sync_hostaway.network.auth import get_or_refresh_token

logger = structlog.get_logger(__name__)

BASE_URL = "https://api.hostaway.com/v1/"
MAX_CONCURRENT_REQUESTS = 4
MAX_IP_RPS = 15 / 10  # 1.5 req/sec per IP
REQUEST_DELAY = 1 / MAX_IP_RPS
MAX_RETRIES = 2


def should_retry(res: Optional[requests.Response], err: Optional[Exception]) -> bool:
    """
    Determine whether the request should be retried based on response or error.

    Args:
        res (Optional[requests.Response]): Response object if available.
        err (Optional[Exception]): Exception raised by the request, if any.

    Returns:
        bool: True if the request should be retried, False otherwise.
    """
    if res and res.status_code == 429:
        return True
    if isinstance(err, requests.Timeout):
        return True
    if res and 500 <= res.status_code < 600:
        return True
    return False


def fetch_page(
    endpoint: str,
    token: str,
    page_number: int = 0,
    offset: Optional[int] = None,
    limit: Optional[int] = 100,
    account_id: Optional[int] = None,
) -> Tuple[Dict[str, Any], int]:
    """
    Fetch a single page of results from a Hostaway API endpoint.

    Args:
        endpoint (str): The Hostaway API endpoint (e.g. 'reservations').
        token (str): Bearer token for Hostaway authentication.
        page_number (int, optional): Page number for offset calculation. Defaults to 0.
        offset (Optional[int], optional): Explicit offset override. Defaults to None.
        limit (Optional[int], optional): Max records per page. Defaults to 100.
        account_id (Optional[int], optional): Hostaway account ID (used for token refresh).
                                              Defaults to None.

    Returns:
        Tuple[Dict[str, Any], int]: A tuple of the JSON response and HTTP status code.

    Raises:
        requests.RequestException: If the request fails after all retries.
    """
    url = urljoin(BASE_URL, endpoint)
    headers = {"Authorization": f"Bearer {token}"}
    page_limit = limit or 100
    params = {
        "limit": page_limit,
        "offset": offset if offset is not None else page_number * page_limit,
    }

    retries = 0

    while True:
        try:
            logger.debug("Requesting %s offset=%s", endpoint, params["offset"])

            # Track API latency
            start_time = time.time()
            res = requests.get(url, headers=headers, params=params, timeout=5)
            latency = time.time() - start_time

            # Record API metrics
            api_requests.labels(endpoint=endpoint, status_code=str(res.status_code)).inc()
            api_latency.labels(endpoint=endpoint).observe(latency)

            if res.status_code == 403 and account_id is not None:
                logger.warning(
                    "403 Unauthorized on %s offset=%s; refreshing token", endpoint, params["offset"]
                )
                token = get_or_refresh_token(account_id, prev_token=token)
                headers["Authorization"] = f"Bearer {token}"
                retries += 1
                if retries > MAX_RETRIES:
                    res.raise_for_status()
                continue

            if res.status_code == 429:
                logger.warning(
                    "Rate limited on offset=%s. Sleeping %.1fs", params["offset"], REQUEST_DELAY * 2
                )
                time.sleep(REQUEST_DELAY * 2)
                retries += 1
                if retries > MAX_RETRIES:
                    res.raise_for_status()
                continue

            res.raise_for_status()
            return cast(Dict[str, Any], res.json()), res.status_code

        except requests.RequestException as err:
            logger.warning("Error fetching %s offset=%s: %s", endpoint, params["offset"], str(err))
            retries += 1
            if retries > MAX_RETRIES or not should_retry(res if "res" in locals() else None, err):
                raise
            time.sleep(REQUEST_DELAY * retries)


def fetch_paginated(
    endpoint: str,
    account_id: int,
    limit: Optional[int] = 100,
) -> List[Dict[str, Any]]:
    """
    Fetch all paginated results from a Hostaway endpoint.

    Args:
        endpoint (str): The Hostaway API endpoint (e.g. 'reservations', 'messages').
        account_id (int): Hostaway account ID used for auth and token refresh.
        limit (Optional[int], optional): Max number of records per page. Defaults to 100.

    Returns:
        List[Dict[str, Any]]: Flattened list of all items across all pages.
    """
    token = get_or_refresh_token(account_id)

    first_page, _ = fetch_page(endpoint, token, page_number=0, limit=limit, account_id=account_id)
    results = list(first_page.get("result", []))
    total_count = first_page.get("count", len(results))
    total_pages = ceil(total_count / limit)

    logger.info("Fetching %d total records across %d pages", total_count, total_pages)

    if total_pages > 1:
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as pool:
            futures = [
                pool.submit(
                    fetch_page, endpoint, token, page_number=i, limit=limit, account_id=account_id
                )
                for i in range(1, total_pages)
            ]
            for future in as_completed(futures):
                page_data, _ = future.result()
                results.extend(page_data.get("result", []))

    return results
