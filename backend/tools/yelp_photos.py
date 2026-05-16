"""
Yelp Fusion API — restaurant photo fetcher.

Returns the first photo URL for a given restaurant name + address.
Falls back to None if YELP_API_KEY is not set or the business isn't found.
"""

import logging

import httpx

from core.config import get_settings

log = logging.getLogger(__name__)

_BASE = "https://api.yelp.com/v3"
_TIMEOUT = 5.0


async def get_restaurant_photo(name: str, address: str) -> str | None:
    """Search Yelp for `name` near `address` and return its first photo URL."""
    _YELP_API_KEY = get_settings().yelp_api_key
    if not _YELP_API_KEY:
        return None

    # Use city/state from address as location (last two comma-separated parts)
    parts = [p.strip() for p in address.split(",")]
    location = ", ".join(parts[-2:]) if len(parts) >= 2 else address

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{_BASE}/businesses/search",
                headers={"Authorization": f"Bearer {_YELP_API_KEY}"},
                params={"term": name, "location": location, "limit": 1},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            businesses = resp.json().get("businesses", [])
            if businesses:
                url = businesses[0].get("image_url")
                if url:
                    # Replace /ms.jpg suffix with /o.jpg for full-size image
                    return url.replace("/ms.jpg", "/o.jpg").replace("/348s.jpg", "/o.jpg")
    except Exception as exc:
        log.warning("Yelp photo fetch failed for %r: %s", name, exc)

    return None
