"""
Unit tests for tools/xhs_scorer.py.

All pure functions — no I/O, no mocks needed.
"""

import pytest
from tools.xhs_scorer import (
    parse_count,
    compute_xhs_score,
    extract_keywords,
    pick_sample_comment,
)


# ── parse_count ───────────────────────────────────────────────────────────────

class TestParseCount:
    def test_plain_integer(self):
        assert parse_count("1234") == 1234

    def test_wan_unit(self):
        assert parse_count("3万") == 30000

    def test_decimal_wan(self):
        assert parse_count("1.2万") == 12000

    def test_qian_unit(self):
        assert parse_count("5千") == 5000

    def test_empty_string(self):
        assert parse_count("") == 0

    def test_non_numeric(self):
        assert parse_count("N/A") == 0

    def test_whitespace_stripped(self):
        assert parse_count("  500  ") == 500


# ── compute_xhs_score ────────────────────────────────────────────────────────

class TestComputeXhsScore:
    def test_zero_posts_returns_low_score(self):
        score = compute_xhs_score(0, [], [])
        assert score < 15  # only sentiment component (neutral = 10)

    def test_score_in_range(self):
        interactions = [{"likes": 100, "saves": 50, "comments": 20}] * 10
        texts = ["正宗好吃推荐" * 3]
        score = compute_xhs_score(10, interactions, texts)
        assert 0 <= score <= 100

    def test_high_volume_high_engagement_high_score(self):
        interactions = [{"likes": 1000, "saves": 500, "comments": 200}] * 50
        texts = ["正宗必打卡地道强烈推荐不踩雷"] * 50
        score = compute_xhs_score(50, interactions, texts)
        assert score >= 70

    def test_negative_keywords_lower_score(self):
        positive_ints = [{"likes": 100, "saves": 50, "comments": 20}] * 5
        negative_ints = [{"likes": 100, "saves": 50, "comments": 20}] * 5
        pos_texts = ["正宗好吃必打卡推荐值得"] * 5
        neg_texts = ["踩雷难吃不推荐失望坑"] * 5

        pos_score = compute_xhs_score(5, positive_ints, pos_texts)
        neg_score = compute_xhs_score(5, negative_ints, neg_texts)
        assert pos_score > neg_score

    def test_saves_weighted_more_than_likes(self):
        save_heavy = [{"likes": 10, "saves": 100, "comments": 5}]
        like_heavy = [{"likes": 100, "saves": 10, "comments": 5}]
        texts = ["好吃"]

        save_score = compute_xhs_score(1, save_heavy, texts)
        like_score = compute_xhs_score(1, like_heavy, texts)
        assert save_score > like_score

    def test_more_posts_higher_volume_component(self):
        empty_interactions = []
        texts: list[str] = []
        score_1 = compute_xhs_score(1, empty_interactions, texts)
        score_100 = compute_xhs_score(100, empty_interactions, texts)
        assert score_100 > score_1

    def test_neutral_sentiment_near_10(self):
        # No keywords matched → sentiment = 10
        score = compute_xhs_score(0, [], ["随便写点什么没有关键词"])
        # Only sentiment contributes: should be ~10
        assert 8 <= score <= 12

    def test_score_is_rounded(self):
        score = compute_xhs_score(5, [{"likes": 10, "saves": 5, "comments": 2}], ["好吃"])
        assert score == round(score, 1)


# ── extract_keywords ──────────────────────────────────────────────────────────

class TestExtractKeywords:
    def test_returns_two_lists(self):
        pos, neg = extract_keywords(["好吃正宗推荐"])
        assert isinstance(pos, list)
        assert isinstance(neg, list)

    def test_detects_positive_keywords(self):
        pos, _ = extract_keywords(["这家店真的超级正宗，必打卡，强烈推荐！"])
        assert "正宗" in pos or "必打卡" in pos

    def test_detects_negative_keywords(self):
        _, neg = extract_keywords(["踩雷了，难吃，不推荐"])
        assert "踩雷" in neg or "难吃" in neg

    def test_empty_text_returns_empty_lists(self):
        pos, neg = extract_keywords([])
        assert pos == []
        assert neg == []

    def test_extracts_hashtags(self):
        pos, _ = extract_keywords(["#洛杉矶美食 #SGV 好吃正宗"])
        # Should contain at least one hashtag or keyword
        assert len(pos) > 0

    def test_respects_top_n(self):
        text = ["正宗好吃必打卡地道推荐值得量大新鲜很棒不错实惠"]
        pos, neg = extract_keywords(text, top_positive=3, top_negative=2)
        assert len(pos) <= 3
        assert len(neg) <= 2

    def test_higher_weight_keywords_first(self):
        # 正宗 (weight 3) should come before 好吃 (weight 2)
        pos, _ = extract_keywords(["好吃正宗"])
        if "正宗" in pos and "好吃" in pos:
            assert pos.index("正宗") < pos.index("好吃")


# ── pick_sample_comment ───────────────────────────────────────────────────────

class TestPickSampleComment:
    def test_empty_input(self):
        assert pick_sample_comment([]) == ""

    def test_returns_string(self):
        result = pick_sample_comment(["好吃", "一般"])
        assert isinstance(result, str)

    def test_prefers_positive_text(self):
        texts = ["踩雷了很难吃", "超级正宗必打卡强烈推荐好吃地道"]
        result = pick_sample_comment(texts)
        assert result == "超级正宗必打卡强烈推荐好吃地道"

    def test_respects_max_len(self):
        long_text = "好吃" * 100
        result = pick_sample_comment([long_text], max_len=20)
        assert len(result) <= 20

    def test_single_text(self):
        result = pick_sample_comment(["这家店很好吃"])
        assert result == "这家店很好吃"

    def test_ignores_very_short_texts(self):
        texts = ["好", "这家餐厅正宗好吃强烈推荐值得专程来"]
        result = pick_sample_comment(texts)
        # Should pick the longer, more informative text
        assert len(result) > 1
