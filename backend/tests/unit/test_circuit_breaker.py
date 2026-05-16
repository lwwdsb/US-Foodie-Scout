"""
Unit tests for core/circuit_breaker.py.

Covers all state transitions:
  CLOSED → OPEN (failure_threshold reached)
  OPEN   → fast fail (no call made)
  OPEN   → HALF_OPEN (recovery_timeout elapsed)
  HALF_OPEN → CLOSED (probe succeeds)
  HALF_OPEN → OPEN   (probe fails)
"""

import pytest
from unittest.mock import patch
from core.circuit_breaker import CircuitBreaker


async def _ok():
    return "result"


async def _fail():
    raise RuntimeError("service down")


class TestCircuitBreakerClosed:
    async def test_success_returns_result(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=30)
        result = await cb.call(_ok())
        assert result == "result"
        assert cb.state == "closed"

    async def test_single_failure_stays_closed(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=30)
        result = await cb.call(_fail())
        assert result is None
        assert cb.state == "closed"
        assert cb._failure_count == 1

    async def test_success_resets_failure_count(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=30)
        await cb.call(_fail())
        await cb.call(_ok())
        assert cb._failure_count == 0
        assert cb.state == "closed"


class TestCircuitBreakerTrips:
    async def test_trips_open_after_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=30)
        for _ in range(3):
            await cb.call(_fail())
        assert cb.state == "open"

    async def test_open_returns_none_without_calling(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=30)
        await cb.call(_fail())
        await cb.call(_fail())
        assert cb.state == "open"

        call_count = 0

        async def _tracked():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await cb.call(_tracked())
        assert result is None
        assert call_count == 0  # coro never ran


class TestCircuitBreakerRecovery:
    async def test_half_open_after_timeout(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=30)
        await cb.call(_fail())
        await cb.call(_fail())
        assert cb.state == "open"

        with patch("core.circuit_breaker.time") as mock_time:
            mock_time.monotonic.return_value = cb._last_failure_at + 31
            result = await cb.call(_ok())

        assert result == "result"
        assert cb.state == "closed"

    async def test_half_open_probe_failure_reopens(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=30)
        await cb.call(_fail())
        await cb.call(_fail())
        assert cb.state == "open"

        with patch("core.circuit_breaker.time") as mock_time:
            mock_time.monotonic.return_value = cb._last_failure_at + 31
            result = await cb.call(_fail())

        assert result is None
        assert cb.state == "open"

    async def test_still_open_before_timeout(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=30)
        await cb.call(_fail())
        await cb.call(_fail())

        with patch("core.circuit_breaker.time") as mock_time:
            mock_time.monotonic.return_value = cb._last_failure_at + 10  # < 30s
            result = await cb.call(_ok())

        assert result is None
        assert cb.state == "open"
