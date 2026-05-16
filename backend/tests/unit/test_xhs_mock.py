"""
Unit tests for tools/xhs_sentiment_mock.py.

Covers: exact match, Chinese alias, English fuzzy match, not-found → None.
"""

import pytest
from tools.xhs_sentiment_mock import get_xhs_sentiment


class TestGetXhsSentiment:
    async def test_exact_english_name(self):
        result = await get_xhs_sentiment("101 Noodle Express")
        assert result is not None
        assert result.restaurant_name == "101 Noodle Express"
        assert result.xhs_score > 0

    async def test_exact_english_name_din_tai_fung(self):
        result = await get_xhs_sentiment("Din Tai Fung Arcadia")
        assert result is not None
        assert result.xhs_score < 75  # 网红店慎入: algorithm-computed, not hardcoded

    async def test_chinese_alias_match(self):
        result = await get_xhs_sentiment("101面馆")
        assert result is not None
        assert result.restaurant_name == "101 Noodle Express"

    async def test_chinese_alias_match_lunar(self):
        result = await get_xhs_sentiment("皇朝")
        assert result is not None
        assert result.restaurant_name == "Lunasia Dim Sum House"

    async def test_english_alias_match(self):
        result = await get_xhs_sentiment("din tai fung")
        assert result is not None
        assert result.restaurant_name == "Din Tai Fung Arcadia"

    async def test_fuzzy_partial_name(self):
        # "Chengdu" is a substring of "Chengdu Taste"
        result = await get_xhs_sentiment("Chengdu")
        assert result is not None
        assert result.restaurant_name == "Chengdu Taste"

    async def test_not_found_returns_none(self):
        result = await get_xhs_sentiment("NonExistentRestaurant XYZ 99999")
        assert result is None

    async def test_result_has_expected_fields(self):
        result = await get_xhs_sentiment("Lunasia Dim Sum House")
        assert result is not None
        assert isinstance(result.xhs_score, float)
        assert isinstance(result.post_count, int)
        assert isinstance(result.top_keywords, list)
        assert isinstance(result.warning_keywords, list)
        assert isinstance(result.sample_comment, str)

    async def test_all_four_quadrants_covered(self):
        """Verify mock data spans all authenticity quadrants."""
        names = [
            "101 Noodle Express",       # 华人必打卡
            "Chengdu Taste",            # 隐藏宝藏
            "Din Tai Fung Arcadia",     # 网红店慎入
            "Golden Deli Vietnamese",   # 普通推荐
        ]
        scores = []
        for name in names:
            r = await get_xhs_sentiment(name)
            assert r is not None, f"Missing mock data for {name}"
            scores.append(r.xhs_score)

        assert any(s >= 75 for s in scores[:2])   # must_visit / hidden_gem
        assert any(s < 75 for s in scores[2:])    # overhyped / general
