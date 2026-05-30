"""
Intent extraction (query-rewrite layer) — Phase 1.

Turns a fuzzy natural-language query ("想吃辣的火锅，朋友聚餐，SGV，别太贵") into a
structured IntentResult, so the deterministic restaurant filter can retrieve well
instead of substring-matching the raw message.

One DeepSeek call in JSON mode (response_format=json_object), low temperature.
ALWAYS degrades gracefully: any failure (no key, timeout, bad JSON) returns a
fallback IntentResult(keywords=[message]) — equivalent to the pre-rewrite behavior,
so the pipeline never breaks.

Phase 1 is standalone: extract_intent is not yet wired into run_agent_stream.
"""

import asyncio
import json
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from core.config import get_settings
from schemas.models import IntentResult, PriceLevel

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 8.0

_SYSTEM_PROMPT = """\
你是餐厅查询的意图抽取器。把用户的中文/英文自然语言需求抽取成 JSON。

只输出一个 JSON 对象，字段如下（无法判断的字段用 null，keywords 用空数组）：
{
  "restaurant_name": 用户点名的具体餐厅名（如"101 Noodle Express怎么样"→"101 Noodle Express"），没点名则 null,
  "cuisine": 菜系（如 川菜/火锅/粤式海鲜/日本料理/墨西哥菜/意大利菜），没提则 null,
  "price_level": 预算，必须是 "$"/"$$"/"$$$"/"$$$$" 之一（便宜→$，别太贵→$$，高档→$$$$），没提则 null,
  "area": 地区（如 SGV/Alhambra/Arcadia/Irvine/Koreatown/DTLA），没提则 null,
  "authenticity_pref": 偏好，只能是 "隐藏宝藏"（华人圈口碑好但低调）或 "必打卡"（人气热门），没提则 null,
  "keywords": 描述菜品/氛围的关键词数组（如 ["辣","聚餐","环境好"]）
}

示例输入："想吃辣的火锅，朋友聚餐，SGV，别太贵"
示例输出：{"restaurant_name":null,"cuisine":"火锅","price_level":"$$","area":"SGV","authenticity_pref":null,"keywords":["辣","聚餐"]}
"""


def _build_intent_llm() -> ChatOpenAI:
    settings = get_settings()
    if not settings.deepseek_api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not set")
    return ChatOpenAI(
        base_url=settings.deepseek_base_url + "/v1",
        api_key=settings.deepseek_api_key,
        model=settings.deepseek_model,
        temperature=0.0,
        model_kwargs={"response_format": {"type": "json_object"}},
    )


def _fallback(message: str) -> IntentResult:
    """Degrade to raw-message-as-keywords — equivalent to pre-rewrite behavior."""
    return IntentResult(keywords=[message])


def _parse(raw: str) -> IntentResult:
    """Parse the LLM JSON string into an IntentResult, dropping invalid fields."""
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("intent JSON is not an object")

    # price_level must be a valid enum value, else drop it
    price = data.get("price_level")
    if price not in (pl.value for pl in PriceLevel):
        price = None

    kw = data.get("keywords") or []
    if not isinstance(kw, list):
        kw = []

    return IntentResult(
        restaurant_name=data.get("restaurant_name") or None,
        cuisine=data.get("cuisine") or None,
        price_level=price,
        area=data.get("area") or None,
        authenticity_pref=data.get("authenticity_pref") or None,
        keywords=[str(k) for k in kw if k],
    )


async def extract_intent(
    message: str,
    ui_budget: PriceLevel | None = None,
    ui_cuisine: str | None = None,
) -> IntentResult:
    """
    Extract structured intent from a fuzzy query.

    UI-provided budget/cuisine take precedence over text-extracted values
    (the user set them explicitly via dropdowns). Never raises — any failure
    returns a fallback that preserves the pre-rewrite behavior.
    """
    try:
        llm = _build_intent_llm()
        resp = await asyncio.wait_for(
            llm.ainvoke([
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=message),
            ]),
            timeout=_TIMEOUT_SECONDS,
        )
        intent = _parse(resp.content if hasattr(resp, "content") else str(resp))
    except Exception as e:
        logger.warning("Intent extraction failed for %r: %s — using fallback", message, e)
        intent = _fallback(message)

    # UI dropdowns win over text-extracted values (explicit user choice).
    if ui_budget is not None:
        intent.price_level = ui_budget
    if ui_cuisine:
        intent.cuisine = ui_cuisine

    return intent
