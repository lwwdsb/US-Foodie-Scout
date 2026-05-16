"""
Real XHS sentiment implementation.

Activated by setting XHS_USE_REAL=true in .env.
Drops in as an exact replacement for xhs_sentiment_mock.get_xhs_sentiment()
— same function signature, same return type.

Search strategy:
  1. Search "{restaurant_name} {xhs_search_location}"
  2. If no results and name looks ASCII, also try with Chinese location hints.
  3. Return None if still no results (caller treats missing XHS as score=50).
"""

import logging
from typing import Optional

from core.config import get_settings
from tools.xhs_client import XhsSearchClient
from tools.xhs_scorer import (
    compute_xhs_score,
    extract_keywords,
    pick_sample_comment,
)
from tools.xhs_sentiment_mock import XHSSentimentResult  # reuse the dataclass

logger = logging.getLogger(__name__)
settings = get_settings()

_client: Optional[XhsSearchClient] = None


def _get_client() -> XhsSearchClient:
    global _client
    if _client is None:
        _client = XhsSearchClient(cookie=settings.xhs_cookie)
    return _client


async def get_xhs_sentiment(restaurant_name: str) -> Optional[XHSSentimentResult]:
    """
    Fetch real XHS sentiment for a restaurant.
    Same interface as xhs_sentiment_mock.get_xhs_sentiment().
    """
    client = _get_client()

    # Build candidate search queries, most specific first
    queries: list[str] = [restaurant_name]
    if all(ord(c) < 128 for c in restaurant_name):
        # English name — try with Chinese location context too
        queries.append(f"{restaurant_name} 洛杉矶")
        queries.append(f"{restaurant_name} 阿罕布拉")

    notes = []
    for query in queries:
        found = await client.search_restaurant(
            name=query,
            location=settings.xhs_search_location,
            max_notes=20,
        )
        if found:
            notes = found
            logger.debug("XHS: %d notes found for %r", len(notes), query)
            break

    if not notes:
        logger.info("XHS: no notes found for %r", restaurant_name)
        return None

    texts = [f"{n.title} {n.desc}" for n in notes]
    interactions = [
        {"likes": n.likes, "saves": n.saves, "comments": n.comments}
        for n in notes
    ]

    xhs_score = compute_xhs_score(
        post_count=len(notes),
        interactions=interactions,
        texts=texts,
    )
    positive_keywords, warning_keywords = extract_keywords(texts)
    sample = pick_sample_comment(texts)

    # Approximate star rating from score: 50→3.5, 80→3.74, 20→3.26
    avg_rating = round(max(1.0, min(5.0, 3.5 + (xhs_score - 50) / 120)), 1)

    return XHSSentimentResult(
        restaurant_name=restaurant_name,
        xhs_score=xhs_score,
        post_count=len(notes),
        avg_rating=avg_rating,
        top_keywords=positive_keywords,
        warning_keywords=warning_keywords,
        sample_comment=sample,
    )
