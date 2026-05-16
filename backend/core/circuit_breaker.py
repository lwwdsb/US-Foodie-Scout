"""
Simple async circuit breaker.

States:
  CLOSED   — normal operation, calls pass through
  OPEN     — tripped, fast-fail without calling the service
  HALF_OPEN — cooldown elapsed, one probe call allowed through

Transitions:
  CLOSED  → OPEN      : failure_count reaches failure_threshold
  OPEN    → HALF_OPEN : recovery_timeout seconds have elapsed
  HALF_OPEN → CLOSED  : probe call succeeds
  HALF_OPEN → OPEN    : probe call fails
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Awaitable

logger = logging.getLogger(__name__)


class _State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state = _State.CLOSED
        self._failure_count = 0
        self._last_failure_at: float | None = None
        self._lock = asyncio.Lock()

    # ── Public API ─────────────────────────────────────────────────────────────

    async def call(self, coro: Awaitable[Any]) -> Any | None:
        """
        Run `coro` through the breaker.
        Returns None (does NOT raise) when the circuit is OPEN — callers
        should treat None as a degraded / unavailable signal.
        """
        async with self._lock:
            if self._state == _State.OPEN:
                elapsed = time.monotonic() - (self._last_failure_at or 0)
                if elapsed < self.recovery_timeout:
                    logger.debug("CircuitBreaker[%s]: OPEN — fast fail", self.name)
                    # Close the unawaited coroutine to suppress ResourceWarning
                    if hasattr(coro, "close"):
                        coro.close()
                    return None
                self._state = _State.HALF_OPEN
                logger.info("CircuitBreaker[%s]: HALF_OPEN — probing after %.0fs", self.name, elapsed)
            # CLOSED or HALF_OPEN: fall through and execute

        try:
            result = await coro
        except Exception as exc:
            await self._on_failure(exc)
            return None

        await self._on_success()
        return result

    @property
    def state(self) -> str:
        return self._state.value

    # ── Internals ──────────────────────────────────────────────────────────────

    async def _on_success(self) -> None:
        async with self._lock:
            if self._state == _State.HALF_OPEN:
                logger.info("CircuitBreaker[%s]: CLOSED — service recovered", self.name)
            self._state = _State.CLOSED
            self._failure_count = 0
            self._last_failure_at = None

    async def _on_failure(self, exc: Exception) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_at = time.monotonic()
            if self._failure_count >= self.failure_threshold or self._state == _State.HALF_OPEN:
                self._state = _State.OPEN
                logger.warning(
                    "CircuitBreaker[%s]: OPEN after %d failure(s) — last error: %s",
                    self.name,
                    self._failure_count,
                    exc,
                )
