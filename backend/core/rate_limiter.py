import logging
import redis.asyncio as aioredis
from fastapi import Request, HTTPException
from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def check_rate_limit(request: Request) -> None:
    """
    Redis sliding window rate limiter: N req/window per IP.
    INCR + EXPIRE are issued in a single pipeline to eliminate the
    race condition where a crash between the two commands leaves the
    key without a TTL (and permanently blocks the IP).
    Fails open: if Redis is unreachable, the request is allowed through.
    """
    client_ip = request.client.host if request.client else "unknown"
    key = f"rl:{client_ip}"

    try:
        redis = await get_redis()
        pipe = redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, settings.rate_limit_window_seconds)
        count, _ = await pipe.execute()
    except Exception as e:
        logger.warning("Rate limiter Redis error (fail-open): %s", e)
        return  # fail-open: let the request through

    if count > settings.rate_limit_requests:
        try:
            ttl = await redis.ttl(key)
        except Exception:
            ttl = settings.rate_limit_window_seconds
        raise HTTPException(
            status_code=429,
            detail={
                "error": "请求过于频繁，请稍后再试",
                "retry_after_seconds": ttl,
            },
        )
