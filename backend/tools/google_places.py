"""
GooglePlacesTool — real data, served from data/restaurants.json.

The JSON is produced offline by scripts/enrich_google.py (Google Places API New).
Serving reads the static file — no live Google calls per request (matches the
cache-by-design in project_decisions). Same interface as google_places_mock so
agent/react_agent.py swaps the import based on settings.google_source.

Activate with GOOGLE_SOURCE=real in .env.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from schemas.models import PriceLevel
# Reuse the dataclass + filter helpers from the mock (single source of truth).
from tools.google_places_mock import PlaceResult, _matches_budget, _matches_cuisine, _matches_area, _AREA_ALIASES

logger = logging.getLogger(__name__)

_DATA_FILE = Path(__file__).parent.parent / "data" / "restaurants.json"

_places_cache: Optional[list[PlaceResult]] = None
_cache_mtime: float = 0.0


def _build_keywords(d: dict) -> list[str]:
    """Lightweight keywords for query matching (restaurants.json has none of its own)."""
    kw = [d.get("cuisine_type", "")]
    addr = d.get("address", "")
    for token in ("Alhambra", "Arcadia", "San Gabriel", "Monterey Park", "Rosemead",
                  "Temple City", "Rowland Heights", "Irvine", "Los Angeles", "Costa Mesa"):
        if token in addr:
            kw.append(token.lower())
    return [k for k in kw if k]


def _load() -> list[PlaceResult]:
    global _places_cache, _cache_mtime
    if not _DATA_FILE.exists():
        logger.error("restaurants.json not found at %s — run scripts/enrich_google.py", _DATA_FILE)
        return []
    mtime = _DATA_FILE.stat().st_mtime
    if _places_cache is None or mtime != _cache_mtime:
        raw = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
        places = []
        for name, d in raw.items():
            try:
                places.append(PlaceResult(
                    place_id=d["place_id"], name=d["name"], name_zh=d.get("name_zh"),
                    address=d.get("address", ""), lat=d["lat"], lng=d["lng"],
                    google_rating=d["google_rating"], google_score=d["google_score"],
                    price_level=PriceLevel(d.get("price_level", "$$")),
                    cuisine_type=d.get("cuisine_type", "中餐"),
                    total_ratings=d.get("total_ratings", 0),
                    google_maps_url=d.get("google_maps_url", ""),
                    photo_url=d.get("photo_url"),
                    phone=d.get("phone"), website=d.get("website"),
                    keywords=_build_keywords(d),
                ))
            except (KeyError, ValueError) as e:
                logger.warning("Skipping malformed restaurant %r: %s", name, e)
        _places_cache, _cache_mtime = places, mtime
        logger.info("Loaded %d restaurants from restaurants.json", len(places))
    return _places_cache


async def search_restaurants(
    query: str = "",
    budget: Optional[PriceLevel] = None,
    cuisine: Optional[str] = None,
    area: Optional[str] = None,
    exclude_names: Optional[list[str]] = None,
    limit: int = 5,
) -> list[PlaceResult]:
    """Search real restaurants. Same scoring/behavior as the mock's search_restaurants."""
    places = _load()
    excl_lower = {n.lower() for n in (exclude_names or [])}
    results = [
        p for p in places
        if _matches_budget(p, budget)
        and _matches_cuisine(p, cuisine)
        and p.name.lower() not in excl_lower
        and (not p.name_zh or p.name_zh.lower() not in excl_lower)
    ]

    # Area: soft filter — relax if it would empty the results (incomplete area data).
    if area:
        narrowed = [p for p in results if _matches_area(p, area)]
        if narrowed:
            results = narrowed

    if query:
        q = query.lower()
        scored = []
        for p in results:
            score = 0
            if q in p.name.lower():
                score += 3
            if p.name_zh and q in p.name_zh:
                score += 3
            if any(q in kw.lower() or kw.lower() in q for kw in p.keywords):
                score += 2
            if q in p.cuisine_type.lower() or p.cuisine_type.lower() in q:
                score += 2
            if q in p.address.lower():
                score += 1
            scored.append((score, p))
        scored.sort(key=lambda x: -x[0])
        results = [p for _, p in scored]

    return results[:limit]


async def get_place_detail(place_id: str) -> Optional[PlaceResult]:
    for p in _load():
        if p.place_id == place_id:
            return p
    return None


# ── Live fallback (called when static DB returns no results) ──────────────────

_LA_BOX = {"rectangle": {"low": {"latitude": 33.70, "longitude": -118.67},
                         "high": {"latitude": 34.35, "longitude": -117.65}}}
_LIVE_FIELDS = ("places.id,places.displayName,places.formattedAddress,places.location,"
                "places.rating,places.userRatingCount,places.priceLevel,places.googleMapsUri")
_PRICE_MAP = {
    "PRICE_LEVEL_FREE": "$", "PRICE_LEVEL_INEXPENSIVE": "$",
    "PRICE_LEVEL_MODERATE": "$$", "PRICE_LEVEL_EXPENSIVE": "$$$",
    "PRICE_LEVEL_VERY_EXPENSIVE": "$$$$",
}

_CUISINE_HINTS = [
    (("火锅", "hot pot", "shabu"), "火锅"),
    (("dim sum", "seafood", "海鲜"), "粤式海鲜"),
    (("sichuan", "szechuan", "川", "麻辣"), "川菜"),
    (("noodle", "ramen", "面"), "面食"),
    (("taco", "mexican", "mariscos"), "墨西哥菜"),
    (("burger", "in-n-out", "smash"), "美式汉堡"),
    (("pizza", "pizzeria", "italian", "trattoria"), "意大利菜"),
    (("sushi", "japanese", "izakaya", "tsujita"), "日本料理"),
    (("thai",), "泰国菜"),
    (("korean", "bbq", "baekjeong"), "韩式烤肉"),
    (("deli", "pastrami"), "犹太熟食"),
    (("ice cream", "salt & straw", "gelato"), "冰淇淋"),
    (("donut", "doughnut"), "甜甜圈"),
]


def _guess_cuisine(name: str) -> str:
    low = name.lower()
    for keys, label in _CUISINE_HINTS:
        if any(k in low for k in keys):
            return label
    return "餐厅"


async def search_restaurants_live(
    query: str,
    budget: Optional[PriceLevel] = None,
    area: Optional[str] = None,
    limit: int = 5,
) -> list[PlaceResult]:
    """
    Real-time Google Places text search — used when the static DB returns 0 results.
    Results are NOT written to restaurants.json (offline batch only).
    """
    import json as _json
    import urllib.request
    import urllib.error

    from core.config import get_settings
    key = get_settings().google_api_key
    if not key:
        logger.warning("GOOGLE_API_KEY not set — cannot do live place search")
        return []

    text_query = f"{query} {area} Los Angeles" if area else f"{query} Los Angeles"
    body = _json.dumps({
        "textQuery": text_query,
        "languageCode": "en",
        "maxResultCount": min(limit * 2, 10),
        "locationRestriction": _LA_BOX,
    }).encode()
    req = urllib.request.Request(
        "https://places.googleapis.com/v1/places:searchText",
        data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": _LIVE_FIELDS,
        },
    )
    try:
        import asyncio as _asyncio
        raw = await _asyncio.to_thread(
            lambda: _json.load(urllib.request.urlopen(req, timeout=10))
        )
    except Exception as e:
        logger.warning("Live Google search failed for %r: %s", query, e)
        return []

    results: list[PlaceResult] = []
    for p in raw.get("places", [])[:limit]:
        if p.get("rating") is None:
            continue
        loc = p.get("location", {})
        gname = p.get("displayName", {}).get("text", query)
        price_raw = p.get("priceLevel", "")
        price = PriceLevel(_PRICE_MAP.get(price_raw, "$$"))
        if budget and price != budget:
            continue
        results.append(PlaceResult(
            place_id=p.get("id", ""),
            name=gname,
            name_zh=None,
            address=p.get("formattedAddress", ""),
            lat=loc.get("latitude", 0.0),
            lng=loc.get("longitude", 0.0),
            google_rating=float(p["rating"]),
            google_score=round(float(p["rating"]) * 20, 1),
            price_level=price,
            cuisine_type=_guess_cuisine(gname),
            total_ratings=p.get("userRatingCount", 0),
            google_maps_url=p.get("googleMapsUri", ""),
            photo_url=None,
            keywords=[],
        ))
    return results
