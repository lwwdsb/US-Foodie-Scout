"""
XHS sentiment from Octoparse / 八爪鱼 collected data.

Why this exists:
  - The `xhs` PyPI path (tools/xhs_sentiment.py) hits XHS's API with reverse-engineered
    signing → the account gets logged out / banned. Do NOT use it.
  - XHS is collected OFFLINE in the 八爪鱼 desktop client (real browser, residential IP,
    QR login with a 小号), exported, normalized into backend/data/xhs_notes.json, and read
    here. The serving path never touches XHS → zero account risk at request time.

Activated by setting XHS_SOURCE=bazhuayu in .env.
Drops in as an exact replacement for xhs_sentiment_mock.get_xhs_sentiment()
— same signature, same return type — so agent/react_agent.py just swaps the import.

Cache file shape (produced by scripts/ingest_xhs_export.py):
  {
    "101 Noodle Express": [
      {"title": "...", "desc": "...", "likes": 150, "saves": 65, "comments": 30},
      ...
    ],
    "Lunasia Dim Sum House": [ ... ]
  }
Keys are restaurant names; values are the notes collected for that restaurant.
This module is COLUMN-AGNOSTIC — all raw-export column mapping lives in the
ingestion script, not here.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from tools.xhs_scorer import (
    compute_xhs_score_likes,
    extract_keywords,
    pick_sample_comment,
)
from tools.xhs_sentiment_mock import XHSSentimentResult  # reuse the dataclass

logger = logging.getLogger(__name__)

# backend/data/xhs_notes.json
_CACHE_FILE = Path(__file__).parent.parent / "data" / "xhs_notes.json"

# In-process cache, reloaded when the file changes (handy in dev).
_notes_cache: Optional[dict[str, list[dict]]] = None
_cache_mtime: float = 0.0


def _load_notes() -> dict[str, list[dict]]:
    """Load (and hot-reload) the normalized notes cache from disk."""
    global _notes_cache, _cache_mtime

    if not _CACHE_FILE.exists():
        if _notes_cache is None:
            logger.warning(
                "XHS notes cache not found at %s — run scripts/ingest_xhs_export.py "
                "after collecting in the 八爪鱼 desktop client.",
                _CACHE_FILE,
            )
        _notes_cache = {}
        return _notes_cache

    mtime = _CACHE_FILE.stat().st_mtime
    if _notes_cache is None or mtime != _cache_mtime:
        try:
            with _CACHE_FILE.open(encoding="utf-8") as f:
                _notes_cache = json.load(f)
            _cache_mtime = mtime
            logger.info("Loaded XHS notes for %d restaurants", len(_notes_cache))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to read %s: %s", _CACHE_FILE, exc)
            _notes_cache = _notes_cache or {}

    return _notes_cache


def _find_notes(restaurant_name: str) -> list[dict]:
    """Resolve a restaurant name to its notes: exact, then case-insensitive substring."""
    notes = _load_notes()
    if not notes:
        return []

    if restaurant_name in notes:
        return notes[restaurant_name]

    name_lower = restaurant_name.lower()
    for key, value in notes.items():
        kl = key.lower()
        if name_lower in kl or kl in name_lower:
            return value

    return []


async def get_xhs_sentiment(restaurant_name: str) -> Optional[XHSSentimentResult]:
    """
    XHS sentiment for a restaurant, computed from 八爪鱼-collected notes.
    Same interface as xhs_sentiment_mock.get_xhs_sentiment().
    Returns None when no notes were collected for this restaurant.
    """
    notes = _find_notes(restaurant_name)
    if not notes:
        logger.info("XHS: no collected notes for %r", restaurant_name)
        return None

    # Defensive field access — notes are normalized but tolerate missing keys.
    # 2996 gives title (no desc) and likes (no saves/comments) → likes-primary score.
    texts = [f"{n.get('title', '')} {n.get('desc', '')}".strip() for n in notes]
    likes = [int(n.get("likes", 0) or 0) for n in notes]

    xhs_score = compute_xhs_score_likes(
        post_count=len(notes),
        likes=likes,
        texts=texts,
    )
    positive_keywords, warning_keywords = extract_keywords(texts)
    sample = pick_sample_comment(texts)

    # Approximate star rating from score (same mapping as the real xhs_sentiment path).
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
