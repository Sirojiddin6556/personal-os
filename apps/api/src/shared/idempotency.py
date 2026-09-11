"""Idempotency-Key support with Redis storage and fallback memory cache."""

import json
import logging
from typing import Any, Dict, Optional, Tuple
from uuid import UUID
from src.config import settings

logger = logging.getLogger(__name__)

# In-memory fallback cache for development/offline environments
_MEMORY_CACHE: Dict[str, Tuple[int, Dict[str, Any], float]] = {}


class IdempotencyService:
    """Manages Idempotency-Key lifecycle to guarantee exactly-once mutation semantics."""

    def __init__(self, redis_url: str = settings.redis_url):
        self.redis_url = redis_url
        self._redis_client = None

    async def get_client(self):
        if self._redis_client is None:
            try:
                import redis.asyncio as aioredis
                self._redis_client = aioredis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
                await self._redis_client.ping()
            except Exception as ex:
                logger.warning("Redis not available for idempotency (%s). Falling back to memory cache.", ex)
                self._redis_client = False
        return self._redis_client if self._redis_client is not False else None

    @staticmethod
    def _cache_key(workspace_id: UUID | str, idempotency_key: str) -> str:
        return f"idempotency:{str(workspace_id)}:{idempotency_key}"

    async def get(self, workspace_id: UUID | str, idempotency_key: str) -> Optional[Tuple[int, Dict[str, Any]]]:
        """Fetch previously stored response if present. Returns (status_code, body)."""
        key = self._cache_key(workspace_id, idempotency_key)
        client = await self.get_client()
        if client:
            try:
                data = await client.get(key)
                if data:
                    parsed = json.loads(data)
                    return parsed["status_code"], parsed["body"]
            except Exception as e:
                logger.error("Redis error fetching idempotency key: %s", e)

        # Check in-memory fallback
        import time
        now = time.time()
        if key in _MEMORY_CACHE:
            status_code, body, expire_at = _MEMORY_CACHE[key]
            if now < expire_at:
                return status_code, body
            else:
                del _MEMORY_CACHE[key]
        return None

    async def set(
        self,
        workspace_id: UUID | str,
        idempotency_key: str,
        status_code: int,
        body: Dict[str, Any],
        ttl_seconds: int = 86400,
    ) -> None:
        """Store response for idempotency key with TTL (default 24h)."""
        key = self._cache_key(workspace_id, idempotency_key)
        client = await self.get_client()
        payload = json.dumps({"status_code": status_code, "body": body})
        if client:
            try:
                await client.set(key, payload, ex=ttl_seconds)
                return
            except Exception as e:
                logger.error("Redis error saving idempotency key: %s", e)

        # In-memory fallback
        import time
        _MEMORY_CACHE[key] = (status_code, body, time.time() + ttl_seconds)


idempotency_service = IdempotencyService()
