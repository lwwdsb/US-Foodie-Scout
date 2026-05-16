"""
Integration tests for the FastAPI application.

Uses fakeredis (no real Redis needed) and mocks run_agent_stream
(no real DeepSeek calls). Tests the full HTTP layer: request parsing,
SSE format, session persistence, and rate limiting.
"""

import json
import pytest
from unittest.mock import patch


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _collect_sse(response) -> list[dict]:
    """Parse SSE lines from an httpx streaming response into a list of chunks."""
    chunks = []
    async for line in response.aiter_lines():
        if line.startswith("data:"):
            raw = line[5:].strip()
            if raw:
                chunks.append(json.loads(raw))
    return chunks


async def _fake_agent(**kwargs):
    yield {"type": "text", "content": "推荐结果"}
    yield {"type": "recommendations", "content": []}
    yield {"type": "done"}


VALID_BODY = {"message": "推荐川菜", "session_id": "test-session-001"}


# ── /health ───────────────────────────────────────────────────────────────────

class TestHealth:
    async def test_returns_200(self, http_client):
        resp = await http_client.get("/health")
        assert resp.status_code == 200

    async def test_redis_ok_with_fake(self, http_client):
        data = resp = await http_client.get("/health")
        data = resp.json()
        assert data["redis"] is True

    async def test_version_present(self, http_client):
        resp = await http_client.get("/health")
        assert "version" in resp.json()


# ── POST /chat ────────────────────────────────────────────────────────────────

class TestChat:
    async def test_valid_request_returns_200(self, http_client):
        with patch("agent.react_agent.run_agent_stream", side_effect=_fake_agent):
            async with http_client.stream("POST", "/chat", json=VALID_BODY) as resp:
                assert resp.status_code == 200

    async def test_sse_content_type(self, http_client):
        with patch("agent.react_agent.run_agent_stream", side_effect=_fake_agent):
            async with http_client.stream("POST", "/chat", json=VALID_BODY) as resp:
                assert "text/event-stream" in resp.headers["content-type"]

    async def test_sse_chunks_include_text_and_done(self, http_client):
        with patch("agent.react_agent.run_agent_stream", side_effect=_fake_agent):
            async with http_client.stream("POST", "/chat", json=VALID_BODY) as resp:
                chunks = await _collect_sse(resp)

        types = [c["type"] for c in chunks]
        assert "text" in types
        assert "done" in types

    async def test_sse_text_chunk_has_content(self, http_client):
        with patch("agent.react_agent.run_agent_stream", side_effect=_fake_agent):
            async with http_client.stream("POST", "/chat", json=VALID_BODY) as resp:
                chunks = await _collect_sse(resp)

        text_chunks = [c for c in chunks if c["type"] == "text"]
        assert len(text_chunks) == 1
        assert text_chunks[0]["content"] == "推荐结果"

    async def test_empty_message_returns_422(self, http_client):
        resp = await http_client.post("/chat", json={"message": "", "session_id": "abc"})
        assert resp.status_code == 422

    async def test_whitespace_message_returns_422(self, http_client):
        resp = await http_client.post("/chat", json={"message": "   ", "session_id": "abc"})
        assert resp.status_code == 422

    async def test_empty_session_id_returns_422(self, http_client):
        resp = await http_client.post("/chat", json={"message": "推荐", "session_id": ""})
        assert resp.status_code == 422

    async def test_missing_message_returns_422(self, http_client):
        resp = await http_client.post("/chat", json={"session_id": "abc"})
        assert resp.status_code == 422

    async def test_with_budget_and_cuisine(self, http_client):
        body = {**VALID_BODY, "budget": "$$", "cuisine": "川菜"}
        with patch("agent.react_agent.run_agent_stream", side_effect=_fake_agent):
            async with http_client.stream("POST", "/chat", json=body) as resp:
                assert resp.status_code == 200


# ── Session persistence ───────────────────────────────────────────────────────

class TestSession:
    async def test_history_empty_before_chat(self, http_client):
        resp = await http_client.get("/session/brand-new-session/history")
        assert resp.status_code == 200
        assert resp.json()["history"] == []

    async def test_history_saved_after_chat(self, http_client):
        session_id = "persist-test-session"
        body = {"message": "推荐川菜", "session_id": session_id}

        with patch("agent.react_agent.run_agent_stream", side_effect=_fake_agent):
            async with http_client.stream("POST", "/chat", json=body) as resp:
                await resp.aread()

        history_resp = await http_client.get(f"/session/{session_id}/history")
        history = history_resp.json()["history"]
        assert len(history) == 2  # user + assistant turns
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "推荐川菜"
        assert history[1]["role"] == "assistant"

    async def test_delete_clears_history(self, http_client):
        session_id = "delete-test-session"
        body = {"message": "推荐餐厅", "session_id": session_id}

        with patch("agent.react_agent.run_agent_stream", side_effect=_fake_agent):
            async with http_client.stream("POST", "/chat", json=body) as resp:
                await resp.aread()

        await http_client.delete(f"/session/{session_id}")

        history_resp = await http_client.get(f"/session/{session_id}/history")
        assert history_resp.json()["history"] == []

    async def test_delete_returns_cleared_status(self, http_client):
        resp = await http_client.delete("/session/any-session")
        assert resp.json() == {"status": "cleared"}


# ── Rate limiting ─────────────────────────────────────────────────────────────

class TestRateLimit:
    async def test_sixth_request_returns_429(self, http_client):
        """Default limit: 5 req/60s per IP."""
        body = {"message": "推荐", "session_id": "rl-test"}

        with patch("agent.react_agent.run_agent_stream", side_effect=_fake_agent):
            for _ in range(5):
                async with http_client.stream("POST", "/chat", json=body) as resp:
                    await resp.aread()

        resp = await http_client.post("/chat", json=body)
        assert resp.status_code == 429

    async def test_429_includes_retry_after(self, http_client):
        body = {"message": "推荐", "session_id": "rl-test-2"}

        with patch("agent.react_agent.run_agent_stream", side_effect=_fake_agent):
            for _ in range(5):
                async with http_client.stream("POST", "/chat", json=body) as resp:
                    await resp.aread()

        resp = await http_client.post("/chat", json=body)
        detail = resp.json()["detail"]
        assert "retry_after_seconds" in detail
