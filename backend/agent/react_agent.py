"""
Deterministic pipeline backed by DeepSeek (OpenAI-compatible API).

Architecture: fixed 3-step pipeline instead of ReAct agent loop.
  Step 1 — call search_restaurants tool (always)
  Step 2 — call get_xhs_sentiment for each result (always)
  Step 3 — LLM generates recommendation text from real data (streaming)

This avoids agent reasoning loops, hallucinated restaurant names, and
intermediate thought leakage — all problems inherent to open-ended ReAct
when the workflow is deterministic.
"""

import json
import asyncio
import hashlib
import logging
import re
from typing import AsyncIterator

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from core.config import get_settings
from core.circuit_breaker import CircuitBreaker
from schemas.models import RestaurantCard, PriceLevel, compute_authenticity_tag

settings = get_settings()

# One breaker per external service — module-level singleton
_xhs_breaker = CircuitBreaker(name="xhs_sentiment", failure_threshold=3, recovery_timeout=30.0)

RECOMMENDATION_SYSTEM_PROMPT = """\
你是「北美华人美食侦探」，专为洛杉矶华人社区提供餐厅推荐服务。

你将收到一批已经搜集好的餐厅数据（包含Google评分和小红书社区评价），直接根据这些真实数据向用户推荐。

【评分体系说明】
- 🔥 华人必打卡：Google评分≥75 AND 小红书评分≥75
- 💎 隐藏宝藏：小红书评分≥75，Google偏低（华人圈口碑好但知名度低）
- ⚠️ 网红店慎入：Google评分≥75，小红书偏低（可能是tourist trap）
- ⭐ 普通推荐：两端均一般

【回复格式】
- 用用户的输入语言回复，默认中文
- 开头一句话总结本次推荐的亮点
- 每家餐厅用1-2句话说明推荐理由，引用小红书关键词增强可信度
- 结尾可补充实用小贴士（如停车、等位时间等）
- 不要重复展示评分数字（前端卡片已展示），专注叙述推荐理由
"""

# ── LLM ───────────────────────────────────────────────────────────────────────

def build_llm(streaming: bool = False) -> ChatOpenAI:
    if not settings.deepseek_api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY is not set. Add it to .env before starting the server."
        )
    return ChatOpenAI(
        base_url=settings.deepseek_base_url + "/v1",
        api_key=settings.deepseek_api_key,
        model=settings.deepseek_model,
        temperature=0.7,
        streaming=streaming,
    )


# ── History helpers ────────────────────────────────────────────────────────────

def _to_messages(history: list[dict]) -> list:
    msgs = []
    for turn in history:
        if turn["role"] == "user":
            msgs.append(HumanMessage(content=turn["content"]))
        elif turn["role"] == "assistant":
            msgs.append(AIMessage(content=turn["content"]))
    return msgs


# ── Card builder ───────────────────────────────────────────────────────────────

def _build_cards(
    places: dict[str, dict],
    xhs_data: dict[str, dict],
) -> list[RestaurantCard]:
    price_map = {
        "$": PriceLevel.budget,
        "$$": PriceLevel.moderate,
        "$$$": PriceLevel.expensive,
        "$$$$": PriceLevel.luxury,
    }

    def find_xhs(name: str) -> dict | None:
        if name in xhs_data:
            return xhs_data[name]
        nl = name.lower()
        for k, v in xhs_data.items():
            if k.lower() in nl or nl in k.lower():
                return v
        return None

    cards = []
    for p in places.values():
        xhs = find_xhs(p["name"])
        xhs_score = xhs["xhs_score"] if xhs else 50.0
        top_kw = xhs.get("top_keywords", []) if xhs else []

        cards.append(
            RestaurantCard(
                name=p["name"],
                name_zh=p.get("name_zh"),
                address=p["address"],
                lat=p["lat"],
                lng=p["lng"],
                google_score=p["google_score"],
                xhs_score=xhs_score,
                price_level=price_map.get(p.get("price_level", "$$"), PriceLevel.moderate),
                authenticity_tag=compute_authenticity_tag(xhs_score, p["google_score"]),
                cuisine_type=p["cuisine_type"],
                google_maps_url=p["google_maps_url"],
                xhs_post_count=xhs.get("post_count", 0) if xhs else 0,
                highlight="、".join(top_kw[:3]) if top_kw else None,
                photo_url=p.get("photo_url"),
            )
        )

    tag_order = {"华人必打卡": 0, "隐藏宝藏": 1, "网红店慎入": 2, "普通推荐": 3}
    cards.sort(key=lambda c: (tag_order.get(c.authenticity_tag.value, 9), -c.xhs_score))
    return cards


# ── Step implementations (called directly, no agent loop) ──────────────────────

def _places_cache_key(query: str, budget: PriceLevel | None, cuisine: str | None) -> str:
    raw = f"{query}|{budget}|{cuisine}"
    digest = hashlib.md5(raw.encode()).hexdigest()[:12]
    return f"places:{digest}"


async def _fetch_places(
    query: str, budget: PriceLevel | None, cuisine: str | None
) -> list[dict]:
    from core.rate_limiter import get_redis

    cache_key = _places_cache_key(query, budget, cuisine)

    # Cache read
    try:
        redis = await get_redis()
        cached = await redis.get(cache_key)
        if cached:
            logging.getLogger(__name__).debug("Places cache hit: %s", cache_key)
            return json.loads(cached)
    except Exception as e:
        logging.getLogger(__name__).warning("Places cache read failed: %s", e)

    # Cache miss — call data source
    from tools.google_places_mock import search_restaurants as _search
    results = await _search(query=query, budget=budget, cuisine=cuisine)
    places = [
        {
            "place_id": p.place_id,
            "name": p.name,
            "name_zh": p.name_zh,
            "address": p.address,
            "lat": p.lat,
            "lng": p.lng,
            "google_score": p.google_score,
            "price_level": p.price_level.value,
            "cuisine_type": p.cuisine_type,
            "google_maps_url": p.google_maps_url,
            "photo_url": p.photo_url,
        }
        for p in results
    ]

    # Cache write
    try:
        redis = await get_redis()
        await redis.setex(cache_key, settings.places_cache_ttl_seconds, json.dumps(places, ensure_ascii=False))
        logging.getLogger(__name__).debug("Places cached (%ds TTL): %s", settings.places_cache_ttl_seconds, cache_key)
    except Exception as e:
        logging.getLogger(__name__).warning("Places cache write failed: %s", e)

    return places


async def _fetch_xhs(restaurant_name: str) -> dict | None:
    from core.rate_limiter import get_redis

    # ── Cache read ──────────────────────────────────────────────────────────
    cache_key = f"xhs:{hashlib.md5(restaurant_name.encode()).hexdigest()[:12]}"
    try:
        redis = await get_redis()
        cached = await redis.get(cache_key)
        if cached:
            logging.getLogger(__name__).debug("XHS cache hit: %s", cache_key)
            return json.loads(cached)
    except Exception as e:
        logging.getLogger(__name__).warning("XHS cache read failed: %s", e)

    # ── Choose implementation ───────────────────────────────────────────────
    if settings.xhs_use_real:
        from tools.xhs_sentiment import get_xhs_sentiment as _get_xhs
        timeout = 15.0   # real network call can be slow
    else:
        from tools.xhs_sentiment_mock import get_xhs_sentiment as _get_xhs
        timeout = 3.0

    async def _call():
        result = await asyncio.wait_for(_get_xhs(restaurant_name), timeout=timeout)
        if not result:
            return None
        return {
            "restaurant_name": result.restaurant_name,
            "xhs_score": result.xhs_score,
            "post_count": result.post_count,
            "top_keywords": result.top_keywords,
            "warning_keywords": result.warning_keywords,
            "sample_comment": result.sample_comment,
        }

    result = await _xhs_breaker.call(_call())

    # ── Cache write ─────────────────────────────────────────────────────────
    if result:
        try:
            redis = await get_redis()
            await redis.setex(
                cache_key,
                settings.xhs_cache_ttl_seconds,
                json.dumps(result, ensure_ascii=False),
            )
        except Exception as e:
            logging.getLogger(__name__).warning("XHS cache write failed: %s", e)

    return result


def _build_context_for_llm(
    user_message: str,
    places: list[dict],
    xhs_map: dict[str, dict],
    xhs_available: bool,
) -> str:
    """Build structured context string for the LLM recommendation prompt."""
    lines = [f"用户需求：{user_message}\n", "已获取的餐厅数据："]
    for p in places:
        xhs = xhs_map.get(p["name"])
        xhs_score = xhs["xhs_score"] if xhs else "不可用"
        top_kw = "、".join(xhs["top_keywords"][:3]) if xhs else "无"
        warning = "、".join(xhs["warning_keywords"][:2]) if xhs and xhs["warning_keywords"] else "无"
        sample = xhs["sample_comment"] if xhs else "无"
        lines.append(
            f"\n【{p['name_zh'] or p['name']}】\n"
            f"  Google评分：{p['google_score']}/100\n"
            f"  小红书评分：{xhs_score}/100\n"
            f"  小红书关键词：{top_kw}\n"
            f"  差评提示：{warning}\n"
            f"  代表性评论：{sample}\n"
            f"  价格：{p['price_level']} | 菜系：{p['cuisine_type']}"
        )
    if not xhs_available:
        lines.append("\n⚠️ 小红书数据暂时不可用，以上评分为默认值。")
    return "\n".join(lines)


# ── Main streaming runner ──────────────────────────────────────────────────────

async def run_agent_stream(
    message: str,
    history: list[dict],
    budget: PriceLevel | None = None,
    cuisine: str | None = None,
) -> AsyncIterator[dict]:
    """
    Deterministic 3-step pipeline:
      1. search_restaurants (direct call)
      2. get_xhs_sentiment for each result (direct calls, parallel)
      3. LLM generates recommendation text (real streaming)
    No agent loop — no hallucination, no repeated phrases.
    """
    try:
        # ── Step 1: Search ─────────────────────────────────────────────────────
        places = await _fetch_places(query=message, budget=budget, cuisine=cuisine)

        if not places:
            yield {"type": "text", "content": "抱歉，未找到符合条件的餐厅。请尝试放宽预算或菜系条件。"}
            yield {"type": "done"}
            return

        # ── Step 2: XHS sentiment + Yelp photos (parallel fetch) ──────────────
        from tools.yelp_photos import get_restaurant_photo as _get_yelp_photo

        xhs_tasks = [_fetch_xhs(p["name"]) for p in places]
        yelp_tasks = [_get_yelp_photo(p["name"], p["address"]) for p in places]
        all_results = await asyncio.gather(*xhs_tasks, *yelp_tasks, return_exceptions=True)

        xhs_results = all_results[: len(places)]
        yelp_results = all_results[len(places) :]

        xhs_map: dict[str, dict] = {}
        xhs_available = False
        for p, xhs in zip(places, xhs_results):
            if isinstance(xhs, Exception):
                logging.getLogger(__name__).warning("XHS fetch failed for %s: %s", p["name"], xhs)
                continue
            if xhs:
                xhs_map[p["name"]] = xhs
                xhs_available = True

        # Overlay Yelp photos on top of mock Unsplash fallbacks
        for p, yelp_photo in zip(places, yelp_results):
            if isinstance(yelp_photo, str) and yelp_photo:
                p["photo_url"] = yelp_photo

        # ── Step 3: Build cards ────────────────────────────────────────────────
        places_dict = {p["place_id"]: p for p in places}
        cards = _build_cards(places_dict, xhs_map)

        # ── Step 4: LLM generates recommendation text (real SSE streaming) ─────
        context = _build_context_for_llm(message, places, xhs_map, xhs_available)
        chat_history = _to_messages(history[-6:])  # last 3 turns for context

        llm = build_llm(streaming=True)
        prompt_messages = [
            SystemMessage(content=RECOMMENDATION_SYSTEM_PROMPT),
            *chat_history,
            HumanMessage(content=context),
        ]

        async for chunk in llm.astream(prompt_messages):
            if chunk.content:
                yield {"type": "text", "content": chunk.content}

        # ── Step 5: Emit cards + done ──────────────────────────────────────────
        if cards:
            yield {"type": "recommendations", "content": [c.model_dump() for c in cards]}

        yield {"type": "done"}

    except Exception as e:
        yield {"type": "error", "content": f"服务异常：{str(e)}"}
