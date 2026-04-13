"""
Shared production utilities: TTL cache, circuit breaker, async retry.
"""

import asyncio
import functools
import hashlib
import json
import logging
import time
from collections import defaultdict
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger("utils.resilience")


# ---------------------------------------------------------------------------
# TTL Cache
# ---------------------------------------------------------------------------

class TTLCache:
    """Thread-safe in-memory cache with per-entry TTL."""

    def __init__(self, ttl_seconds: int = 3600, max_size: int = 512):
        self._store: Dict[str, Tuple[Any, float]] = {}
        self._ttl = ttl_seconds
        self._max_size = max_size

    def _key(self, *args, **kwargs) -> str:
        raw = json.dumps({"a": args, "k": kwargs}, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        if len(self._store) >= self._max_size:
            # Evict oldest
            oldest_key = min(self._store, key=lambda k: self._store[k][1])
            del self._store[oldest_key]
        self._store[key] = (value, time.monotonic() + self._ttl)

    def make_key(self, *args, **kwargs) -> str:
        return self._key(*args, **kwargs)

    def __len__(self) -> int:
        return len(self._store)


obis_cache = TTLCache(ttl_seconds=3600, max_size=512)


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Simple circuit breaker.
    CLOSED  → normal operation
    OPEN    → fail fast (raises CircuitOpenError)
    HALF_OPEN → probe with one request
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
    ):
        self.name = name
        self._threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failures = 0
        self._state = CircuitState.CLOSED
        self._opened_at: Optional[float] = None

    @property
    def state(self) -> str:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._opened_at >= self._recovery_timeout:
                logger.info("Circuit %s → HALF_OPEN (probing)", self.name)
                self._state = CircuitState.HALF_OPEN
        return self._state

    def record_success(self) -> None:
        self._failures = 0
        if self._state != CircuitState.CLOSED:
            logger.info("Circuit %s → CLOSED", self.name)
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._threshold:
            logger.warning(
                "Circuit %s → OPEN after %d failures", self.name, self._failures
            )
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()

    def is_available(self) -> bool:
        return self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)


class CircuitOpenError(Exception):
    pass


_breakers: Dict[str, CircuitBreaker] = {}


def get_breaker(name: str, failure_threshold: int = 5, recovery_timeout: int = 60) -> CircuitBreaker:
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(name, failure_threshold, recovery_timeout)
    return _breakers[name]


# ---------------------------------------------------------------------------
# Async retry with exponential back-off
# ---------------------------------------------------------------------------

def async_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple = (Exception,),
):
    """Decorator: retry an async function with exponential back-off."""
    def decorator(fn: Callable):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            delay = base_delay
            last_exc: Optional[Exception] = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await fn(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        break
                    logger.warning(
                        "%s: attempt %d/%d failed (%s), retrying in %.1fs",
                        fn.__name__, attempt, max_attempts, exc, delay,
                    )
                    await asyncio.sleep(delay)
                    delay *= backoff_factor
            raise last_exc
        return wrapper
    return decorator