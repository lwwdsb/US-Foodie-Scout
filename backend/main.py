import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from core.config import get_settings
from core.rate_limiter import check_rate_limit, get_redis
from schemas.models import ChatRequest

logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = await get_redis()
    await redis.ping()
    print(f"✅ Redis connected: {settings.redis_url}")
    yield
    await redis.aclose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Session helpers ────────────────────────────────────────────────────────────

async def load_session_history(session_id: str) -> list[dict]:
    try:
        redis = await get_redis()
        raw = await redis.get(f"session:{session_id}")
        return json.loads(raw) if raw else []
    except Exception as e:
        logger.warning("Failed to load session history for %s: %s", session_id, e)
        return []


async def save_session_history(session_id: str, history: list[dict]) -> None:
    try:
        redis = await get_redis()
        trimmed = history[-(settings.session_max_turns * 2):]
        await redis.setex(
            f"session:{session_id}",
            settings.session_ttl_seconds,
            json.dumps(trimmed, ensure_ascii=False),
        )
    except Exception as e:
        logger.warning("Failed to save session history for %s: %s", session_id, e)


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    redis = await get_redis()
    try:
        await redis.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    return {"status": "ok", "redis": redis_ok, "version": "0.1.0"}


# ── POST /chat ─────────────────────────────────────────────────────────────────

@app.post("/chat")
async def chat(
    request: Request,
    body: ChatRequest,
    _: None = Depends(check_rate_limit),
):
    """
    SSE streaming chat endpoint.
    Streams: text chunks → recommendations JSON → done signal.
    """
    from agent.react_agent import run_agent_stream

    history = await load_session_history(body.session_id)
    full_reply_parts: list[str] = []

    async def event_generator():
        try:
            async for chunk in run_agent_stream(
                message=body.message,
                history=history,
                budget=body.budget,
                cuisine=body.cuisine,
            ):
                if chunk["type"] == "text":
                    full_reply_parts.append(chunk["content"])

                yield {"data": json.dumps(chunk, ensure_ascii=False)}
        except Exception as e:
            logger.exception("Unhandled error in event_generator: %s", e)
            yield {"data": json.dumps({"type": "error", "content": "服务异常，请稍后重试"}, ensure_ascii=False)}
            yield {"data": json.dumps({"type": "done"}, ensure_ascii=False)}
            return

        # Persist turn after streaming completes
        full_reply = "".join(full_reply_parts)
        updated = history + [
            {"role": "user", "content": body.message},
            {"role": "assistant", "content": full_reply},
        ]
        await save_session_history(body.session_id, updated)

    return EventSourceResponse(event_generator())


# ── Session endpoints ──────────────────────────────────────────────────────────

@app.get("/session/{session_id}/history")
async def get_history(session_id: str):
    history = await load_session_history(session_id)
    return {"session_id": session_id, "history": history}


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    redis = await get_redis()
    await redis.delete(f"session:{session_id}")
    return {"status": "cleared"}
