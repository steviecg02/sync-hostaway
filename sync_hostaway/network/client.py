import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from math import ceil
from typing import Any, Dict, List, Optional, cast
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.hostaway.com/v1/"
MAX_CONCURRENT_REQUESTS = 4
MAX_IP_RPS = 15 / 10  # 1.5 req/sec per IP
REQUEST_DELAY = 1 / MAX_IP_RPS
MAX_RETRIES = 2


def should_retry(res: Optional[requests.Response], err: Optional[Exception]) -> bool:
    """
    Determine whether a request should be retried based on the response or exception.

    Args:
        res (Optional[requests.Response]): The HTTP response object (if any).
        err (Optional[Exception]): The raised exception (if any).

    Returns:
        bool: True if retry should be attempted, False otherwise.
    """
    if res and res.status_code == 429:
        return True  # Rate limited
    if isinstance(err, requests.Timeout):
        return True  # Transient network issue
    if res and 500 <= res.status_code < 600:
        return True  # Server error
    return False


def fetch_page(
    endpoint: str,
    token: str,
    page_number: int = 0,
    offset: Optional[int] = None,
    limit: Optional[int] = 100,
) -> dict[str, Any]:
    """
    Fetch a single page of results from a Hostaway API endpoint with bounded retry logic.

    Args:
        endpoint (str): Relative Hostaway API endpoint (e.g., "listings").
        token (str): Bearer token for Hostaway authentication.
        page_number (int, optional): Page number to fetch. Defaults to 0.
        offset (Optional[int], optional): Offset parameter for pagination. Defaults to None.
        limit (Optional[int], optional): Maximum number of records per page. Defaults to 100.

    Returns:
        dict: Parsed JSON response from Hostaway API.

    Raises:
        requests.RequestException: If the request ultimately fails after retries.
    """
    url = urljoin(BASE_URL, endpoint)
    headers = {"Authorization": f"Bearer {token}"}
    params = {"limit": 100, "page": page_number}
    if offset is not None:
        params["offset"] = offset

    retries = 0

    while True:
        try:
            logger.debug("Requesting %s page=%d offset=%s", endpoint, page_number, offset)
            res = requests.get(url, headers=headers, params=params, timeout=5)

            if res.status_code == 429:
                logger.warning(
                    "Rate limited on page %d. Sleeping %.1fs", page_number, REQUEST_DELAY * 2
                )
                time.sleep(REQUEST_DELAY * 2)
                retries += 1
                if retries > MAX_RETRIES:
                    res.raise_for_status()
                continue

            res.raise_for_status()
            return cast(dict[str, Any], res.json())

        except requests.RequestException as err:
            logger.warning("Error fetching %s page=%d: %s", endpoint, page_number, str(err))
            retries += 1

            if retries > MAX_RETRIES or not should_retry(res if "res" in locals() else None, err):
                raise

            time.sleep(REQUEST_DELAY * retries)  # Linear backoff


def fetch_paginated(endpoint: str, token: str, limit: Optional[int] = 100) -> List[Dict[str, Any]]:
    """
    Fetch all records from a paginated Hostaway endpoint using concurrency.

    Args:
        endpoint (str): The Hostaway API endpoint to fetch from (e.g., 'listings', 'reservations').
        token (str): The Bearer token used for authentication with the Hostaway API.
        limit (Optional[int], optional): Maximum number of records per page. Defaults to 100.

    Returns:
        List[Dict]: A combined list of all result records retrieved from all pages.
    """
    first = fetch_page(endpoint=endpoint, token=token, page_number=0, limit=limit)
    results = list(first.get("result", []))
    total_count = first.get("count", len(results))
    total_pages = ceil(total_count / limit)

    logger.info("Fetching %d total records across %d pages", total_count, total_pages)

    if total_pages > 1:
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as pool:
            futures = [
                pool.submit(fetch_page, endpoint, token, i, limit) for i in range(1, total_pages)
            ]
            for future in as_completed(futures):
                response = future.result()
                results.extend(response.get("result", []))

    return results
