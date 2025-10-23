"""
In-memory token cache with TTL.

This module provides a simple in-memory cache for Hostaway access tokens to reduce
database queries. Each token is cached with a TTL (time-to-live) and automatically
invalidated when expired or when tokens are refreshed.

For distributed deployments with multiple instances, consider migrating to Redis.
"""

from datetime import datetime, timedelta


class TokenCache:
    """
    In-memory token cache with time-to-live (TTL) expiration.

    This cache stores access tokens by account_id to avoid repeated database queries.
    Tokens are automatically removed when they expire based on the configured TTL.

    Attributes:
        ttl: Time-to-live for cached tokens (default: 1 hour)
        _cache: Internal storage mapping account_id to (token, expires_at) tuples

    Example:
        >>> cache = TokenCache(ttl_seconds=3600)
        >>> cache.set(12345, "token-abc-123")
        >>> token = cache.get(12345)
        >>> cache.invalidate(12345)
    """

    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize token cache with specified TTL.

        Args:
            ttl_seconds: Time-to-live in seconds for cached tokens (default: 3600 = 1 hour)
        """
        self.ttl = timedelta(seconds=ttl_seconds)
        self._cache: dict[int, tuple[str, datetime]] = {}

    def get(self, account_id: int) -> str | None:
        """
        Get cached token if not expired.

        Args:
            account_id: Hostaway account ID

        Returns:
            Cached token string if found and not expired, None otherwise
        """
        if account_id in self._cache:
            token, expires_at = self._cache[account_id]
            if datetime.utcnow() < expires_at:
                return token
            # Expired - remove from cache
            del self._cache[account_id]
        return None

    def set(self, account_id: int, token: str) -> None:
        """
        Cache token with TTL.

        Args:
            account_id: Hostaway account ID
            token: Access token to cache
        """
        expires_at = datetime.utcnow() + self.ttl
        self._cache[account_id] = (token, expires_at)

    def invalidate(self, account_id: int) -> None:
        """
        Remove token from cache.

        This should be called when a token is refreshed to ensure
        stale tokens aren't served from cache.

        Args:
            account_id: Hostaway account ID
        """
        self._cache.pop(account_id, None)

    def clear(self) -> None:
        """
        Clear all cached tokens.

        Useful for testing or emergency cache invalidation.
        """
        self._cache.clear()

    def size(self) -> int:
        """
        Get current cache size (number of cached tokens).

        Returns:
            Number of tokens currently in cache
        """
        return len(self._cache)


# Global cache instance
# TTL of 86400 seconds (24 hours) balances freshness vs performance.
# Note: Hostaway access tokens expire after 24 months, so the cache TTL is
# primarily to ensure eventual refresh rather than prevent token expiry.
token_cache = TokenCache(ttl_seconds=86400)
