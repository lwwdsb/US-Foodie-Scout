"""
Unit tests for agent/intent_rewrite.extract_intent (Phase 1).

DeepSeek is mocked — no network. Covers: successful JSON extraction, graceful
fallback on malformed JSON / exception, invalid price_level dropping, and the
UI-precedence rule (dropdown budget/cuisine override text-extracted values).
"""

import json
import pytest
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace

from agent.intent_rewrite import extract_intent, _parse, _fallback
from schemas.models import IntentResult, PriceLevel


def _mock_llm_returning(content: str):
    """Patch _build_intent_llm to yield an LLM whose ainvoke returns `content`."""
    fake_llm = AsyncMock()
    fake_llm.ainvoke = AsyncMock(return_value=SimpleNamespace(content=content))
    return patch("agent.intent_rewrite._build_intent_llm", return_value=fake_llm)


# ── _parse (pure) ──────────────────────────────────────────────────────────────

class TestParse:
    def test_full_object(self):
        raw = json.dumps({
            "restaurant_name": None, "cuisine": "火锅", "price_level": "$$",
            "area": "SGV", "authenticity_pref": None, "keywords": ["辣", "聚餐"],
        })
        r = _parse(raw)
        assert r.cuisine == "火锅"
        assert r.price_level == PriceLevel.moderate
        assert r.area == "SGV"
        assert r.keywords == ["辣", "聚餐"]

    def test_invalid_price_dropped(self):
        r = _parse(json.dumps({"price_level": "cheap", "keywords": []}))
        assert r.price_level is None

    def test_empty_strings_become_none(self):
        r = _parse(json.dumps({"cuisine": "", "area": "", "keywords": []}))
        assert r.cuisine is None
        assert r.area is None

    def test_non_list_keywords_coerced(self):
        r = _parse(json.dumps({"keywords": "辣"}))
        assert r.keywords == []

    def test_non_object_raises(self):
        with pytest.raises(Exception):
            _parse(json.dumps(["not", "an", "object"]))


# ── extract_intent (mocked LLM) ─────────────────────────────────────────────────

class TestExtractIntent:
    async def test_successful_extraction(self):
        content = json.dumps({
            "restaurant_name": None, "cuisine": "川菜", "price_level": "$$$",
            "area": "Alhambra", "authenticity_pref": "隐藏宝藏", "keywords": ["麻辣"],
        })
        with _mock_llm_returning(content):
            r = await extract_intent("想吃高档的川菜，Alhambra的隐藏宝藏")
        assert r.cuisine == "川菜"
        assert r.price_level == PriceLevel.expensive
        assert r.area == "Alhambra"
        assert r.authenticity_pref == "隐藏宝藏"

    async def test_named_restaurant(self):
        content = json.dumps({
            "restaurant_name": "101 Noodle Express", "cuisine": None,
            "price_level": None, "area": None, "authenticity_pref": None, "keywords": [],
        })
        with _mock_llm_returning(content):
            r = await extract_intent("101 Noodle Express怎么样")
        assert r.restaurant_name == "101 Noodle Express"

    async def test_malformed_json_falls_back(self):
        with _mock_llm_returning("this is not json {{{"):
            r = await extract_intent("随便推荐")
        assert r.keywords == ["随便推荐"]
        assert r.cuisine is None

    async def test_exception_falls_back(self):
        failing = AsyncMock()
        failing.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("agent.intent_rewrite._build_intent_llm", return_value=failing):
            r = await extract_intent("推荐火锅")
        assert r.keywords == ["推荐火锅"]

    async def test_no_api_key_falls_back(self):
        # _build_intent_llm raises when key missing → fallback path
        with patch("agent.intent_rewrite._build_intent_llm", side_effect=RuntimeError("no key")):
            r = await extract_intent("推荐")
        assert r.keywords == ["推荐"]


# ── UI precedence ───────────────────────────────────────────────────────────────

class TestUIPrecedence:
    async def test_ui_budget_overrides_text(self):
        content = json.dumps({"price_level": "$", "cuisine": "火锅", "keywords": []})
        with _mock_llm_returning(content):
            r = await extract_intent("便宜的火锅", ui_budget=PriceLevel.luxury)
        assert r.price_level == PriceLevel.luxury  # UI wins

    async def test_ui_cuisine_overrides_text(self):
        content = json.dumps({"cuisine": "火锅", "keywords": []})
        with _mock_llm_returning(content):
            r = await extract_intent("火锅", ui_cuisine="日本料理")
        assert r.cuisine == "日本料理"  # UI wins

    async def test_ui_none_keeps_extracted(self):
        content = json.dumps({"cuisine": "火锅", "price_level": "$$", "keywords": []})
        with _mock_llm_returning(content):
            r = await extract_intent("便宜火锅")
        assert r.cuisine == "火锅"
        assert r.price_level == PriceLevel.moderate

    async def test_ui_overrides_even_on_fallback(self):
        with _mock_llm_returning("garbage"):
            r = await extract_intent("xyz", ui_budget=PriceLevel.budget, ui_cuisine="川菜")
        assert r.price_level == PriceLevel.budget
        assert r.cuisine == "川菜"
        assert r.keywords == ["xyz"]
