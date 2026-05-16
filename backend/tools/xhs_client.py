"""
Thin async wrapper around the `xhs` PyPI package (github.com/ReaJason/xhs).

Setup:
  1. pip install xhs                    (add to requirements.txt)
  2. Open xiaohongshu.com in your browser, log in, then copy the full Cookie
     header from any request in DevTools → Network. Paste it into .env as:
       XHS_COOKIE=a1=xxx; web_session=xxx; ...
  3. Set XHS_USE_REAL=true in .env

Cookie lifetime: typically 30–90 days. When it expires you'll see auth errors
in the logs — just refresh from the browser and update .env.

The `xhs` package is synchronous; all calls are wrapped in asyncio.to_thread
to keep FastAPI's event loop unblocked.

Version note: if the package's API changes (XHS updates their signing scheme),
this file is the only place to update. The scorer and sentiment files are stable.
"""

import asyncio
import logging
from dataclasses import dataclass, field

from tools.xhs_scorer import parse_count

logger = logging.getLogger(__name__)


@dataclass
class XhsNote:
    note_id: str
    title: str
    desc: str
    likes: int
    saves: int
    comments: int
    tags: list[str] = field(default_factory=list)


class XhsSearchClient:
    """
    Wraps xhs.XhsClient for restaurant search.
    One instance per process (cookie is shared).
    """

    def __init__(self, cookie: str) -> None:
        if not cookie:
            raise ValueError(
                "XHS_COOKIE is not set. Copy it from your browser and add it to .env."
            )
        try:
            from xhs import XhsClient  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "xhs package not installed. Run: pip install xhs"
            ) from exc

        self._client = XhsClient(cookie=cookie)
        logger.info("XhsSearchClient ready (cookie length=%d)", len(cookie))

    async def search_restaurant(
        self,
        name: str,
        location: str = "洛杉矶 SGV",
        max_notes: int = 20,
    ) -> list[XhsNote]:
        """
        Search XHS for posts mentioning `name` near `location`.
        Returns up to max_notes notes sorted by XHS relevance.
        Returns [] on any error (caller should handle gracefully).
        """
        keyword = f"{name} {location}"
        logger.debug("XHS search: %r", keyword)

        try:
            raw = await asyncio.to_thread(
                self._client.get_search_data_by_keyword,
                keyword,
                page=1,
                page_size=min(max_notes, 20),
                sort="general",          # "general" | "popularity_descending"
            )
        except Exception as exc:
            logger.warning("XHS search failed for %r: %s", keyword, exc)
            return []

        return [_parse_note(item) for item in raw.get("items", [])]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _parse_note(item: dict) -> XhsNote:
    """Defensively parse one search result item into XhsNote."""
    card = item.get("note_card", {})
    info = card.get("interact_info", {})
    return XhsNote(
        note_id=item.get("id", ""),
        title=card.get("title", ""),
        desc=card.get("desc", ""),
        likes=parse_count(info.get("liked_count", "0")),
        saves=parse_count(info.get("collected_count", "0")),
        comments=parse_count(info.get("comment_count", "0")),
        tags=[t.get("name", "") for t in card.get("tag_list", [])],
    )
