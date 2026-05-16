"""
Unit tests for pure helper functions in agent/react_agent.py.

Tests: _places_cache_key, _build_cards, _build_context_for_llm.
No Redis, no LLM, no network calls.
"""

import pytest
from schemas.models import AuthenticityTag, PriceLevel
from agent.react_agent import (
    _places_cache_key,
    _build_cards,
    _build_context_for_llm,
)


# ── _places_cache_key ─────────────────────────────────────────────────────────

class TestPlacesCacheKey:
    def test_returns_string_with_prefix(self):
        key = _places_cache_key("川菜", None, None)
        assert key.startswith("places:")

    def test_same_inputs_produce_same_key(self):
        k1 = _places_cache_key("川菜", PriceLevel.moderate, "粤菜")
        k2 = _places_cache_key("川菜", PriceLevel.moderate, "粤菜")
        assert k1 == k2

    def test_different_query_different_key(self):
        k1 = _places_cache_key("川菜", None, None)
        k2 = _places_cache_key("粤菜", None, None)
        assert k1 != k2

    def test_different_budget_different_key(self):
        k1 = _places_cache_key("推荐", PriceLevel.budget, None)
        k2 = _places_cache_key("推荐", PriceLevel.expensive, None)
        assert k1 != k2

    def test_different_cuisine_different_key(self):
        k1 = _places_cache_key("推荐", None, "川菜")
        k2 = _places_cache_key("推荐", None, "粤菜")
        assert k1 != k2


# ── _build_cards ──────────────────────────────────────────────────────────────

def _make_place(place_id: str, name: str, google_score: float) -> dict:
    return {
        "place_id": place_id,
        "name": name,
        "name_zh": None,
        "address": "1 Main St",
        "lat": 34.09,
        "lng": -118.13,
        "google_score": google_score,
        "price_level": "$$",
        "cuisine_type": "川菜",
        "google_maps_url": "https://maps.google.com",
    }


def _make_xhs(name: str, xhs_score: float) -> dict:
    return {
        "restaurant_name": name,
        "xhs_score": xhs_score,
        "post_count": 100,
        "top_keywords": ["好吃", "正宗"],
        "warning_keywords": [],
        "sample_comment": "很好",
    }


class TestBuildCards:
    def test_returns_one_card_per_place(self):
        places = {"p1": _make_place("p1", "A", 80)}
        xhs = {"A": _make_xhs("A", 80)}
        cards = _build_cards(places, xhs)
        assert len(cards) == 1

    def test_must_visit_tag(self):
        places = {"p1": _make_place("p1", "A", 80)}
        xhs = {"A": _make_xhs("A", 80)}
        cards = _build_cards(places, xhs)
        assert cards[0].authenticity_tag == AuthenticityTag.must_visit

    def test_hidden_gem_tag(self):
        places = {"p1": _make_place("p1", "A", 60)}
        xhs = {"A": _make_xhs("A", 80)}
        cards = _build_cards(places, xhs)
        assert cards[0].authenticity_tag == AuthenticityTag.hidden_gem

    def test_overhyped_tag(self):
        places = {"p1": _make_place("p1", "A", 80)}
        xhs = {"A": _make_xhs("A", 60)}
        cards = _build_cards(places, xhs)
        assert cards[0].authenticity_tag == AuthenticityTag.overhyped

    def test_general_tag(self):
        places = {"p1": _make_place("p1", "A", 60)}
        xhs = {"A": _make_xhs("A", 60)}
        cards = _build_cards(places, xhs)
        assert cards[0].authenticity_tag == AuthenticityTag.general

    def test_missing_xhs_defaults_to_50(self):
        places = {"p1": _make_place("p1", "UnknownPlace", 80)}
        cards = _build_cards(places, {})
        assert cards[0].xhs_score == 50.0

    def test_sort_order_must_visit_first(self):
        places = {
            "p1": _make_place("p1", "General",   60),
            "p2": _make_place("p2", "MustVisit",  80),
            "p3": _make_place("p3", "HiddenGem",  60),
        }
        xhs = {
            "General":   _make_xhs("General",   60),
            "MustVisit": _make_xhs("MustVisit", 80),
            "HiddenGem": _make_xhs("HiddenGem", 80),
        }
        cards = _build_cards(places, xhs)
        tags = [c.authenticity_tag for c in cards]
        assert tags[0] == AuthenticityTag.must_visit
        assert tags[1] == AuthenticityTag.hidden_gem
        assert tags[2] == AuthenticityTag.general

    def test_xhs_fuzzy_name_lookup(self):
        # XHS key is a partial match of the place name
        places = {"p1": _make_place("p1", "101 Noodle Express", 80)}
        xhs = {"101": _make_xhs("101", 90)}
        cards = _build_cards(places, xhs)
        assert cards[0].xhs_score == 90.0


# ── _build_context_for_llm ────────────────────────────────────────────────────

class TestBuildContextForLlm:
    def _places(self):
        return [_make_place("p1", "A", 80) | {"name_zh": "餐厅A"}]

    def _xhs_map(self):
        return {"A": _make_xhs("A", 85)}

    def test_contains_user_message(self):
        ctx = _build_context_for_llm("推荐川菜", self._places(), self._xhs_map(), True)
        assert "推荐川菜" in ctx

    def test_contains_restaurant_name(self):
        ctx = _build_context_for_llm("推荐", self._places(), self._xhs_map(), True)
        assert "餐厅A" in ctx

    def test_contains_google_score(self):
        ctx = _build_context_for_llm("推荐", self._places(), self._xhs_map(), True)
        assert "80" in ctx

    def test_contains_xhs_score(self):
        ctx = _build_context_for_llm("推荐", self._places(), self._xhs_map(), True)
        assert "85" in ctx

    def test_xhs_unavailable_warning(self):
        ctx = _build_context_for_llm("推荐", self._places(), {}, False)
        assert "不可用" in ctx

    def test_no_warning_when_xhs_available(self):
        ctx = _build_context_for_llm("推荐", self._places(), self._xhs_map(), True)
        assert "不可用" not in ctx
