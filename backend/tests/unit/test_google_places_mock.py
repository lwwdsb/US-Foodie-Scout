"""
Unit tests for tools/google_places_mock.py.

Covers: budget filter, cuisine filter (CJK + English), query scoring,
and the full search_restaurants pipeline.
"""

import pytest
from schemas.models import PriceLevel
from tools.google_places_mock import (
    PlaceResult,
    _matches_budget,
    _matches_cuisine,
    search_restaurants,
    _MOCK_PLACES,
)


def _place(**kwargs) -> PlaceResult:
    defaults = dict(
        place_id="p1", name="Test", name_zh=None, address="addr",
        lat=34.0, lng=-118.0, google_rating=4.0, google_score=80.0,
        price_level=PriceLevel.moderate, cuisine_type="川菜", total_ratings=100,
        google_maps_url="https://maps.google.com", keywords=["sichuan", "spicy"],
    )
    defaults.update(kwargs)
    return PlaceResult(**defaults)


# ── _matches_budget ───────────────────────────────────────────────────────────

class TestMatchesBudget:
    def test_none_budget_matches_all(self):
        p = _place(price_level=PriceLevel.luxury)
        assert _matches_budget(p, None) is True

    def test_exact_level_matches(self):
        p = _place(price_level=PriceLevel.moderate)
        assert _matches_budget(p, PriceLevel.moderate) is True

    def test_cheaper_than_budget_matches(self):
        p = _place(price_level=PriceLevel.budget)
        assert _matches_budget(p, PriceLevel.expensive) is True

    def test_pricier_than_budget_no_match(self):
        p = _place(price_level=PriceLevel.expensive)
        assert _matches_budget(p, PriceLevel.budget) is False


# ── _matches_cuisine ──────────────────────────────────────────────────────────

class TestMatchesCuisine:
    def test_none_cuisine_matches_all(self):
        p = _place(cuisine_type="川菜")
        assert _matches_cuisine(p, None) is True

    def test_exact_english_match(self):
        p = _place(cuisine_type="sichuan", keywords=[])
        assert _matches_cuisine(p, "sichuan") is True

    def test_substring_english(self):
        p = _place(cuisine_type="northern chinese noodles", keywords=[])
        assert _matches_cuisine(p, "noodles") is True

    def test_cjk_character_overlap(self):
        # 粤 in both query "粤菜" and cuisine_type "粤式早茶"
        p = _place(cuisine_type="粤式早茶", keywords=[])
        assert _matches_cuisine(p, "粤菜") is True

    def test_cjk_no_overlap_no_match(self):
        p = _place(cuisine_type="川菜", keywords=[])
        assert _matches_cuisine(p, "粤菜") is False

    def test_keyword_fallback(self):
        p = _place(cuisine_type="台式点心", keywords=["xiao long bao", "soup dumplings"])
        assert _matches_cuisine(p, "soup dumplings") is True

    def test_no_match_returns_false(self):
        p = _place(cuisine_type="japanese", keywords=["ramen"])
        assert _matches_cuisine(p, "italian") is False


# ── search_restaurants ────────────────────────────────────────────────────────

class TestSearchRestaurants:
    async def test_no_filter_returns_all(self):
        results = await search_restaurants(limit=100)
        assert len(results) == len(_MOCK_PLACES)

    async def test_budget_filters_luxury_out(self):
        results = await search_restaurants(budget=PriceLevel.budget)
        for r in results:
            assert r.price_level == PriceLevel.budget

    async def test_cuisine_cjk_filter(self):
        results = await search_restaurants(cuisine="川菜")
        assert len(results) >= 1
        assert all("川" in r.cuisine_type for r in results)

    async def test_query_ranks_name_match_first(self):
        results = await search_restaurants(query="101")
        assert results[0].name == "101 Noodle Express"

    async def test_limit_respected(self):
        results = await search_restaurants(limit=2)
        assert len(results) <= 2

    async def test_empty_query_returns_results(self):
        results = await search_restaurants(query="")
        assert len(results) > 0
