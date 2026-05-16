"""
XHS sentiment scoring — pure functions, no I/O, no external dependencies.

Used by both the real XHS client and any future data source.
All inputs are plain Python types so this layer is trivially testable.
"""

import math
import re
from typing import Optional

# ── Keyword dictionaries (weighted, SGV Chinese restaurant context) ────────────

# Positive: strong evidence that locals genuinely recommend this place
POSITIVE_KEYWORDS: dict[str, float] = {
    # Authenticity signals (weight 3)
    "正宗": 3.0, "地道": 3.0, "国内水平": 3.0, "不输国内": 3.0,
    # Strong recommendation signals (weight 3)
    "必打卡": 3.0, "必吃": 3.0, "强烈推荐": 3.0, "不踩雷": 3.0,
    "没让我失望": 3.0, "下次还来": 3.0,
    # General positive (weight 2)
    "好吃": 2.0, "超赞": 2.0, "推荐": 2.0, "值得": 2.0,
    "性价比高": 2.0, "惊喜": 2.0, "好评": 2.0, "满意": 2.0,
    # Minor positive (weight 1)
    "量大": 1.0, "新鲜": 1.0, "很棒": 1.0, "不错": 1.0,
    "实惠": 1.0, "干净": 1.0, "用心": 1.0,
}

# Negative: signals that the place disappoints or is a tourist trap
NEGATIVE_KEYWORDS: dict[str, float] = {
    # Hard negative (weight 4)
    "踩雷": 4.0, "难吃": 4.0, "不新鲜": 4.0,
    # Strong negative (weight 3)
    "不推荐": 3.0, "不值得": 3.0, "失望": 3.0, "坑": 3.0,
    "差评": 3.0, "后悔": 3.0,
    # Tourist-trap signals (weight 2)
    "商业化": 2.0, "给外国人吃的": 2.0, "网红店": 2.0,
    "一般": 2.0, "太贵": 2.0, "服务差": 2.0, "态度差": 2.0,
    # Minor negative (weight 1)
    "贵": 1.0, "等位久": 1.0, "油腻": 1.0, "咸": 1.0, "无功无过": 1.0,
}


# ── Count parser ──────────────────────────────────────────────────────────────

def parse_count(s: str) -> int:
    """
    Parse XHS interaction counts, which may use Chinese units.
      '3万'  → 30000
      '1.2万' → 12000
      '500'  → 500
      ''     → 0
    """
    if not s:
        return 0
    s = s.strip()
    try:
        if "万" in s:
            return int(float(s.replace("万", "")) * 10_000)
        if "千" in s:
            return int(float(s.replace("千", "")) * 1_000)
        return int(s)
    except (ValueError, TypeError):
        return 0


# ── Core scoring ──────────────────────────────────────────────────────────────

def compute_xhs_score(
    post_count: int,
    interactions: list[dict],
    texts: list[str],
) -> float:
    """
    Compute a 0-100 XHS authenticity score.

    Args:
        post_count:   Number of XHS notes found for this restaurant.
        interactions: List of dicts with keys 'likes', 'saves', 'comments'
                      (one entry per note). Saves are weighted 3× likes because
                      saving a post signals "I want to go here" — stronger intent.
        texts:        Combined title + description text for each note.

    Returns:
        Float in [0, 100].

    Score breakdown:
        Volume score    (0–40): log-scale on post count.
        Engagement score(0–40): weighted avg of saves/likes/comments, log-scaled.
        Sentiment score (0–20): keyword sentiment, centred at 10 (neutral).
    """
    # ── Volume (0-40) ─────────────────────────────────────────────────────────
    # log1p curve: 1 post→6, 5→13, 20→22, 100→32, 500→39, 1000+→40
    volume_score = min(40.0, math.log1p(post_count) * 6.5)

    # ── Engagement (0-40) ─────────────────────────────────────────────────────
    if interactions:
        total_weighted = sum(
            i.get("saves", 0) * 3 + i.get("likes", 0) + i.get("comments", 0) * 0.5
            for i in interactions
        )
        avg_weighted = total_weighted / len(interactions)
        engagement_score = min(40.0, math.log1p(avg_weighted) * 5.5)
    else:
        engagement_score = 0.0

    # ── Sentiment (0-20) ─────────────────────────────────────────────────────
    combined = " ".join(texts)
    pos = sum(w for kw, w in POSITIVE_KEYWORDS.items() if kw in combined)
    neg = sum(w for kw, w in NEGATIVE_KEYWORDS.items() if kw in combined)
    raw = pos - neg                                    # roughly [-20, +30]
    sentiment_score = max(0.0, min(20.0, 10.0 + raw * 0.8))

    return round(volume_score + engagement_score + sentiment_score, 1)


# ── Keyword extraction ────────────────────────────────────────────────────────

def extract_keywords(
    texts: list[str],
    top_positive: int = 5,
    top_negative: int = 3,
) -> tuple[list[str], list[str]]:
    """
    Extract the most-weighted matched keywords and top hashtags from notes.

    Returns:
        (positive_keywords, warning_keywords) — both sorted by relevance.
    """
    combined = " ".join(texts)

    pos_hits = sorted(
        [(kw, w) for kw, w in POSITIVE_KEYWORDS.items() if kw in combined],
        key=lambda x: -x[1],
    )
    neg_hits = sorted(
        [(kw, w) for kw, w in NEGATIVE_KEYWORDS.items() if kw in combined],
        key=lambda x: -x[1],
    )

    # Hashtags as supplementary positive signals
    hashtags = re.findall(r"#([^\s#]+)", combined)
    tag_freq: dict[str, int] = {}
    for tag in hashtags:
        tag_freq[tag] = tag_freq.get(tag, 0) + 1
    top_tags = sorted(tag_freq, key=lambda t: -tag_freq[t])

    positives = [kw for kw, _ in pos_hits[:top_positive]]
    # Backfill with hashtags if fewer matched keywords than requested
    for tag in top_tags:
        if len(positives) >= top_positive:
            break
        if tag not in positives:
            positives.append(tag)

    warnings = [kw for kw, _ in neg_hits[:top_negative]]
    return positives, warnings


# ── Sample comment picker ─────────────────────────────────────────────────────

def pick_sample_comment(texts: list[str], max_len: int = 100) -> str:
    """
    Return the most information-dense note text (highest keyword density).
    Prefers texts that are positive-heavy, substantive (>20 chars), and concise.
    """
    if not texts:
        return ""

    def _score(text: str) -> float:
        pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in text)
        neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text)
        # Reward length up to ~80 chars, penalise very short texts
        length_factor = min(1.0, len(text) / 80)
        return (pos - neg * 0.5) * length_factor

    best = max((t for t in texts if len(t) > 10), key=_score, default=texts[0])
    return best[:max_len]
