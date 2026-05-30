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
from schemas.models import RestaurantCard, PriceLevel, AuthenticityTag, compute_authenticity_tag

settings = get_settings()

# One breaker per external service — module-level singleton
_xhs_breaker = CircuitBreaker(name="xhs_sentiment", failure_threshold=3, recovery_timeout=30.0)

RECOMMENDATION_SYSTEM_PROMPT = """\
你是「北美华人美食侦探」，专为洛杉矶华人社区提供餐厅推荐服务。

你将收到餐厅数据，数据来源分两种：
1. 【批量数据】：Google评分 + 小红书社区评分（真实离线采集）
2. 【网络搜索】：Google评分 + 网络搜索片段（实时获取，小红书无离线数据）

【评分徽章说明】
- 🔥 华人必打卡：Google≥75 AND 小红书≥70（批量数据）
- 💎 隐藏宝藏：小红书≥70，Google偏低（华人圈口碑好）
- ⚠️ 网红店慎入：Google≥75，小红书偏低
- ⭐ 普通推荐：两端均一般
- 🔍 网络口碑：无小红书离线数据，根据网络搜索片段评价

【处理网络搜索数据的要求】
- 收到「小红书（网络搜索片段）」时，仔细阅读片段内容
- 综合片段中华人社区的评价倾向，给出1-2句定性描述
- 明确说明「基于网络信息」，不捏造具体评分或打卡数
- 若片段不含该餐厅的有效信息，坦诚说明暂无华人社区评价

【严格规则 — 必须遵守】
- 只推荐「已获取的餐厅数据」中列出的餐厅，绝不凭记忆或训练数据推荐数据之外的餐厅
- 若数据中标注「未找到 X，以下为相近替代」，说明用户点名的店未收录或不在服务范围，
  直接介绍实际找到的替代餐厅，不要编写关于未找到那家店的任何内容

【回复格式】
- 用用户的输入语言回复，默认中文
- 开头一句话总结本次推荐亮点
- 每家餐厅1-2句推荐理由，批量数据引用小红书关键词，网络搜索数据给出定性判断
- 结尾可补充实用小贴士
- 不重复展示评分数字（前端卡片已展示）
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
    authenticity_pref: str | None = None,
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

    def _extract_reviews(xhs: dict | None) -> list[str]:
        """Pull 1-2 short review snippets from XHS data (batch or web_search)."""
        if not xhs:
            return []
        src = xhs.get("xhs_source", "batch")
        if src == "batch":
            comment = (xhs.get("sample_comment") or "").strip()
            return [comment[:400]] if comment else []
        if src == "web_search":
            raw = xhs.get("web_snippets", "")
            snippets = [s.strip() for s in raw.split("\n---\n") if s.strip()]
            return [s[:400] for s in snippets[:2]]
        return []

    cards = []
    for p in places.values():
        xhs = find_xhs(p["name"])
        is_web = xhs and xhs.get("xhs_source") == "web_search"

        if is_web:
            xhs_score = 50.0
            tag = AuthenticityTag.web_sentiment
            top_kw = []
            post_count = 0
            xhs_source = "web_search"
        elif xhs:
            xhs_score = xhs["xhs_score"]
            top_kw = xhs.get("top_keywords", [])
            post_count = xhs.get("post_count", 0)
            xhs_source = "batch"
            tag = compute_authenticity_tag(
                xhs_score, p["google_score"],
                xhs_threshold=settings.xhs_high_threshold,
                google_threshold=settings.google_high_threshold,
            )
        else:
            xhs_score = 50.0
            top_kw = []
            post_count = 0
            xhs_source = "none"
            tag = compute_authenticity_tag(
                xhs_score, p["google_score"],
                xhs_threshold=settings.xhs_high_threshold,
                google_threshold=settings.google_high_threshold,
            )

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
                authenticity_tag=tag,
                cuisine_type=p["cuisine_type"],
                google_maps_url=p["google_maps_url"],
                xhs_post_count=post_count,
                highlight="、".join(top_kw[:3]) if top_kw else None,
                photo_url=p.get("photo_url"),
                xhs_source=xhs_source,
                reviews=_extract_reviews(xhs),
            )
        )

    tag_order = {"华人必打卡": 0, "隐藏宝藏": 1, "网红店慎入": 2, "普通推荐": 3}
    _pref_tag = {
        "隐藏宝藏": AuthenticityTag.hidden_gem,
        "必打卡":  AuthenticityTag.must_visit,
    }.get(authenticity_pref or "")

    def _sort_key(c: RestaurantCard) -> tuple:
        base = tag_order.get(c.authenticity_tag.value, 9)
        if _pref_tag and c.authenticity_tag == _pref_tag:
            base = -1   # boost matched-pref cards to the top
        return (base, -c.xhs_score)

    cards.sort(key=_sort_key)
    return cards


# ── Step implementations (called directly, no agent loop) ──────────────────────

def _places_cache_key(query: str, budget: PriceLevel | None, cuisine: str | None, area: str | None = None) -> str:
    raw = f"{query}|{budget}|{cuisine}|{area}"
    digest = hashlib.md5(raw.encode()).hexdigest()[:12]
    return f"places:{digest}"


async def _fetch_places(
    query: str, budget: PriceLevel | None, cuisine: str | None,
    area: str | None = None, exclude_names: list[str] | None = None,
) -> list[dict]:
    from core.rate_limiter import get_redis

    cache_key = _places_cache_key(query, budget, cuisine, area)
    # exclude_names are session-specific: skip cache entirely when exclusions are active
    # so a cached full result set never bypasses the exclusion filter.
    use_cache = not exclude_names

    # Cache read
    if use_cache:
        try:
            redis = await get_redis()
            cached = await redis.get(cache_key)
            if cached:
                logging.getLogger(__name__).debug("Places cache hit: %s", cache_key)
                return json.loads(cached)
        except Exception as e:
            logging.getLogger(__name__).warning("Places cache read failed: %s", e)

    # Cache miss — call data source (google_source: "mock" | "real")
    if settings.google_source == "real":
        from tools.google_places import search_restaurants as _search, search_restaurants_live as _search_live
    else:
        from tools.google_places_mock import search_restaurants as _search
        _search_live = None
    results = await _search(query=query, budget=budget, cuisine=cuisine,
                           area=area, exclude_names=exclude_names)

    # Live fallback path 1: area specified but nothing in static DB for that area
    # (USC, South LA, Westside, etc.) → live Google knows real geography
    if area and _search_live:
        from tools.google_places_mock import _matches_area
        from tools.google_places import _load
        area_in_db = any(_matches_area(p, area) for p in _load())
        if not area_in_db:
            logging.getLogger(__name__).info(
                "Area %r not in static DB — trying live Google search", area)
            live = await _search_live(query=query, budget=budget, area=area)
            if live:
                results = live

    # Live fallback path 2: exclusions emptied the results (user wants fresh picks)
    elif not results and exclude_names and _search_live:
        logging.getLogger(__name__).info(
            "All static results excluded — trying live Google search for fresh picks")
        results = await _search_live(query=query, budget=budget, area=area)

    # Live fallback path 3: no results at all
    elif not results and _search_live:
        logging.getLogger(__name__).info(
            "Static DB miss for %r — trying live Google search", query)
        results = await _search_live(query=query, budget=budget, area=area)

    # Live supplement: static returned results but fewer than threshold
    # → call live Google and append non-duplicate results for better coverage
    _SUPPLEMENT_THRESHOLD = 3
    if 0 < len(results) < _SUPPLEMENT_THRESHOLD and _search_live:
        logging.getLogger(__name__).info(
            "Only %d static result(s) — supplementing with live Google search", len(results))
        live = await _search_live(query=query, budget=budget, area=area)
        seen_ids   = {p.place_id for p in results}
        seen_names = {p.name.lower() for p in results}
        for p in live:
            if p.place_id not in seen_ids and p.name.lower() not in seen_names:
                results.append(p)
                seen_ids.add(p.place_id)
                seen_names.add(p.name.lower())

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

    # Cache write (skip when exclusions were applied — result is session-specific)
    if use_cache:
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
    # xhs_source: "mock" | "bazhuayu" | "xhs_py". Legacy xhs_use_real → xhs_py.
    source = settings.xhs_source
    if source == "xhs_py" or (source == "mock" and settings.xhs_use_real):
        from tools.xhs_sentiment import get_xhs_sentiment as _get_xhs
        timeout = 15.0   # real network call can be slow
    elif source == "bazhuayu":
        from tools.xhs_bazhuayu import get_xhs_sentiment as _get_xhs
        timeout = 3.0    # local cache read, fast
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

    # ── Cache write (batch) ──────────────────────────────────────────────────
    if result:
        result["xhs_source"] = "batch"
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

    # ── Tavily web-search fallback ───────────────────────────────────────────
    from tools.xhs_web_search import search_xhs_sentiment
    snippets = await search_xhs_sentiment(restaurant_name)
    if snippets:
        web_result = {"xhs_source": "web_search", "web_snippets": snippets}
        try:
            redis = await get_redis()
            await redis.setex(
                cache_key,
                settings.xhs_cache_ttl_seconds // 2,   # shorter TTL for web data
                json.dumps(web_result, ensure_ascii=False),
            )
        except Exception as e:
            logging.getLogger(__name__).warning("XHS web cache write failed: %s", e)
        return web_result

    return None


def _build_context_for_llm(
    user_message: str,
    places: list[dict],
    xhs_map: dict[str, dict],
    xhs_available: bool,
    not_found_name: str | None = None,
) -> str:
    """Build structured context string for the LLM recommendation prompt."""
    header = f"用户需求：{user_message}\n"
    if not_found_name:
        header += f"⚠️ 未找到「{not_found_name}」（未收录或不在服务范围），以下为相近替代推荐，请只介绍这些餐厅：\n"
    lines = [header, "已获取的餐厅数据："]
    for p in places:
        xhs = xhs_map.get(p["name"])
        xhs_src = xhs.get("xhs_source", "batch") if xhs else None

        if xhs_src == "web_search":
            snippets = xhs.get("web_snippets", "")
            lines.append(
                f"\n【{p['name_zh'] or p['name']}】\n"
                f"  Google评分：{p['google_score']}/100\n"
                f"  小红书（网络搜索片段，请综合评价）：\n{snippets}\n"
                f"  价格：{p['price_level']} | 菜系：{p['cuisine_type']}"
            )
        elif xhs_src == "batch":
            xhs_score = xhs["xhs_score"]
            top_kw = "、".join(xhs["top_keywords"][:3]) if xhs["top_keywords"] else "无"
            warning = "、".join(xhs["warning_keywords"][:2]) if xhs["warning_keywords"] else "无"
            sample = xhs["sample_comment"] or "无"
            lines.append(
                f"\n【{p['name_zh'] or p['name']}】\n"
                f"  Google评分：{p['google_score']}/100\n"
                f"  小红书评分：{xhs_score}/100\n"
                f"  小红书关键词：{top_kw}\n"
                f"  差评提示：{warning}\n"
                f"  代表性评论：{sample}\n"
                f"  价格：{p['price_level']} | 菜系：{p['cuisine_type']}"
            )
        else:
            lines.append(
                f"\n【{p['name_zh'] or p['name']}】\n"
                f"  Google评分：{p['google_score']}/100\n"
                f"  小红书：暂无数据\n"
                f"  价格：{p['price_level']} | 菜系：{p['cuisine_type']}"
            )
    if not xhs_available:
        lines.append("\n⚠️ 小红书离线数据不可用。")
    return "\n".join(lines)


# ── Main streaming runner ──────────────────────────────────────────────────────

async def run_agent_stream(
    message: str,
    history: list[dict],
    budget: PriceLevel | None = None,
    cuisine: str | None = None,
) -> AsyncIterator[dict]:
    """
    Deterministic pipeline:
      0. extract_intent (DeepSeek JSON) — fuzzy NL → structured fields
      1. search_restaurants (direct call, driven by intent)
      2. get_xhs_sentiment for each result (direct calls, parallel)
      3. LLM generates recommendation text (real streaming)
    No agent loop — no hallucination, no repeated phrases.
    """
    try:
        # ── Step 0: Intent extraction (degrades to raw message on failure) ─────
        from agent.intent_rewrite import extract_intent
        intent = await extract_intent(
            message,
            ui_budget=budget,
            ui_cuisine=cuisine,
            history=history,
        )

        # Named-restaurant query → search by name (skip keyword filtering, keep
        # the out-of-DB live fallback). Otherwise drive search from intent fields.
        if intent.restaurant_name:
            search_query = intent.restaurant_name
        else:
            search_query = " ".join(intent.keywords) if intent.keywords else message

        # ── Step 1: Search (UI precedence already applied inside extract_intent) ─
        places = await _fetch_places(
            query=search_query,
            budget=intent.price_level,
            cuisine=intent.cuisine,
            area=intent.area,
            exclude_names=intent.exclude_names or None,
        )

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
        cards = _build_cards(places_dict, xhs_map, authenticity_pref=intent.authenticity_pref)

        # ── Step 4: LLM generates recommendation text (real SSE streaming) ─────
        # Detect named-restaurant miss: user asked for a specific place we couldn't find
        not_found = None
        if intent.restaurant_name:
            name_lower = intent.restaurant_name.lower()
            if not any(name_lower in p["name"].lower() or p["name"].lower() in name_lower
                       for p in places):
                not_found = intent.restaurant_name

        context = _build_context_for_llm(message, places, xhs_map, xhs_available,
                                          not_found_name=not_found)
        chat_history = _to_messages(history[-12:])  # last 6 turns for context

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
