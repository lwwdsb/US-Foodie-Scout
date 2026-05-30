"""
XHS web-search fallback — used when a restaurant is not in xhs_notes.json.

Queries Tavily for Chinese-community / 小红书 mentions and returns raw snippets
for the LLM to synthesize into a qualitative assessment.

Activate by setting TAVILY_API_KEY in .env.
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_SNIPPET_LEN = 400
_MAX_SNIPPETS = 5


async def search_xhs_sentiment(restaurant_name: str) -> Optional[str]:
    """
    Search for XHS / Chinese-community sentiment about a restaurant.
    Returns raw concatenated snippets (≤~2 KB) for the LLM to synthesize, or None.
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
            f"{restaurant_name} 小红书 评价",
            f"{restaurant_name} 好吃 推荐 Los Angeles",
        ]
        snippets: list[str] = []
        for q in queries:
            result = await asyncio.to_thread(
                client.search, q,
                search_depth="basic",
                max_results=3,
                include_answer=False,
            )
            for item in result.get("results", []):
                content = (item.get("content") or "").strip()
                if content:
                    snippets.append(content[:_MAX_SNIPPET_LEN])
            if len(snippets) >= _MAX_SNIPPETS:
                break

        if not snippets:
            return None
        return "\n---\n".join(snippets[:_MAX_SNIPPETS])

    except Exception as e:
        logger.warning("XHS web search failed for %r: %s", restaurant_name, e)
        return None
