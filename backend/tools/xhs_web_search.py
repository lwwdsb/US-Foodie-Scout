"""
XHS web-search fallback — used when a restaurant is not in xhs_notes.json.

Queries Tavily for Chinese-community / 小红书 mentions and returns filtered
snippets for the LLM to synthesize into a qualitative assessment.

Activate by setting TAVILY_API_KEY in .env.
"""
import asyncio
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_SNIPPET_LEN = 400
_MAX_SNIPPETS = 5
_MIN_SNIPPET_LEN = 30

# Snippets containing any of these patterns are spam / off-topic and dropped.
_SPAM_PATTERNS = re.compile(
    r"开房记录|手机号|身份证|同住人|酒店入住|查询记录|联系客服|客服微信"
    r"|casino|adult|escort|sex|porn"
    r"|加微信|私信|代理|刷单|兼职招聘"
    r"|download now|click here|subscribe now",
    re.IGNORECASE,
)

# Snippets must mention at least one food/review signal to be kept.
_FOOD_SIGNALS = re.compile(
    r"餐厅|好吃|推荐|菜|味道|评分|评价|review|restaurant|food|menu|delicious"
    r"|口感|服务|环境|分|星|rating|yelp|google|小红书|种草|打卡",
    re.IGNORECASE,
)


def _is_relevant(snippet: str, restaurant_name: str) -> bool:
    """Return True only if the snippet is food-related and not spam."""
    if len(snippet) < _MIN_SNIPPET_LEN:
        return False
    if _SPAM_PATTERNS.search(snippet):
        return False
    # Must have a food signal OR mention the restaurant name
    name_tokens = re.findall(r"[A-Za-z一-鿿]+", restaurant_name)
    name_mentioned = any(t.lower() in snippet.lower() for t in name_tokens if len(t) > 1)
    return name_mentioned or bool(_FOOD_SIGNALS.search(snippet))


async def search_xhs_sentiment(restaurant_name: str) -> Optional[str]:
    """
    Search for XHS / Chinese-community sentiment about a restaurant.
    Returns filtered concatenated snippets (≤~2 KB) for the LLM to synthesize, or None.
    Spam and off-topic snippets are dropped before returning.
    """
    from core.config import get_settings
    key = get_settings().tavily_api_key
    if not key:
        logger.debug("TAVILY_API_KEY not set — skipping XHS web search for %s", restaurant_name)
        return None

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=key)

        queries = [
            f"{restaurant_name} 小红书 餐厅评价",
            f'"{restaurant_name}" restaurant review Los Angeles',
        ]
        snippets: list[str] = []
        for q in queries:
            result = await asyncio.to_thread(
                client.search, q,
                search_depth="basic",
                max_results=4,
                include_answer=False,
            )
            for item in result.get("results", []):
                content = (item.get("content") or "").strip()
                if content and _is_relevant(content, restaurant_name):
                    snippets.append(content[:_MAX_SNIPPET_LEN])
            if len(snippets) >= _MAX_SNIPPETS:
                break

        if not snippets:
            return None
        return "\n---\n".join(snippets[:_MAX_SNIPPETS])

    except Exception as e:
        logger.warning("XHS web search failed for %r: %s", restaurant_name, e)
        return None
