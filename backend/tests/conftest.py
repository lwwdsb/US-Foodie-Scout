"""
Shared fixtures for all tests.

fakeredis replaces the real Redis singleton so tests run offline.
The http_client fixture starts the full ASGI app (lifespan included).
The mock_agent fixture patches run_agent_stream so integration tests
never call DeepSeek.
"""

import sys
import os
from pathlib import Path

# Ensure `backend/` is on sys.path so `from core.config import ...` works
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import pytest
from fakeredis import FakeAsyncRedis
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch


# ── SSE event-loop reset ────────────────────────────────────────────────────────
# sse_starlette caches a module-level asyncio.Event (AppStatus.should_exit_event),
# bound to the loop of the first SSE response. pytest-asyncio gives each test a fresh
# loop, so the stale Event raises "bound to a different event loop" on later tests.
# Reset it before every test so each gets a clean, loop-local Event.

@pytest.fixture(autouse=True)
def _reset_sse_appstatus():
    from sse_starlette.sse import AppStatus
    AppStatus.should_exit_event = None
    yield
    AppStatus.should_exit_event = None


# ── Fake Redis ────────────────────────────────────────────────────────────────

@pytest.fixture
async def fake_redis():
    """In-process async Redis replacement. Injected before any Redis call."""
    import core.rate_limiter as rl_module
    client = FakeAsyncRedis(decode_responses=True)
    rl_module._redis_client = client
    yield client
    rl_module._redis_client = None
    await client.aclose()


# ── Test HTTP client ──────────────────────────────────────────────────────────

@pytest.fixture
async def http_client(fake_redis):
    """Full ASGI app with fake Redis already wired."""
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


# ── Mock LLM agent (avoids real DeepSeek calls in integration tests) ──────────

@pytest.fixture
def mock_agent():
    """
    Patches agent.react_agent.run_agent_stream to return deterministic chunks.
    The /chat endpoint re-imports it each call, so patching the module attribute works.
    """
    async def _fake_stream(**kwargs):
        yield {"type": "text", "content": "为您推荐以下餐厅："}
        yield {
            "type": "recommendations",
            "content": [],
        }
        yield {"type": "done"}

    with patch("agent.react_agent.run_agent_stream", side_effect=_fake_stream) as m:
        yield m
