from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum


class PriceLevel(str, Enum):
    budget = "$"
    moderate = "$$"
    expensive = "$$$"
    luxury = "$$$$"


class AuthenticityTag(str, Enum):
    must_visit = "华人必打卡"      # XHS≥75 AND Google≥75
    hidden_gem = "隐藏宝藏"        # XHS≥75 AND Google<75
    overhyped = "网红店慎入"       # XHS<75 AND Google≥75
    general = "普通推荐"           # both <75
    web_sentiment = "网络口碑"     # XHS from Tavily web search (no batch data)


def compute_authenticity_tag(
    xhs_score: float,
    google_score: float,
    xhs_threshold: float = 75.0,
    google_threshold: float = 75.0,
) -> AuthenticityTag:
    # Thresholds default to 75 (mock/original design). Real bazhuayu XHS scores are
    # likes-only and run lower/more compressed, so the agent injects a lower
    # xhs_threshold from settings.xhs_high_threshold at the call site.
    high_xhs = xhs_score >= xhs_threshold
    high_google = google_score >= google_threshold
    if high_xhs and high_google:
        return AuthenticityTag.must_visit
    if high_xhs and not high_google:
        return AuthenticityTag.hidden_gem
    if not high_xhs and high_google:
        return AuthenticityTag.overhyped
    return AuthenticityTag.general


# ── Input ──────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    session_id: str = Field(..., min_length=1)
    budget: Optional[PriceLevel] = None
    cuisine: Optional[str] = Field(None, max_length=50)

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("消息不能为空")
        return v.strip()


# ── Query intent (rewrite layer) ─────────────────────────────────────────────────

class IntentResult(BaseModel):
    """Structured intent extracted from a fuzzy natural-language query.

    Produced by agent/intent_rewrite.extract_intent (DeepSeek JSON mode), consumed
    by the deterministic restaurant filter. All fields optional — a query may
    specify any subset. Empty/failed extraction degrades to keywords=[raw message].
    """
    restaurant_name: Optional[str] = None   # user named a specific restaurant → skip filtering
    cuisine: Optional[str] = None            # e.g. 川菜 / 火锅 / 日本料理
    price_level: Optional[PriceLevel] = None
    area: Optional[str] = None               # e.g. SGV / Alhambra / Irvine
    authenticity_pref: Optional[str] = None  # "隐藏宝藏" or "必打卡" (ranking hint, not a filter)
    keywords: list[str] = Field(default_factory=list)  # dish/vibe terms for scoring


# ── Restaurant Card ────────────────────────────────────────────────────────────

class RestaurantCard(BaseModel):
    name: str
    name_zh: Optional[str] = None
    address: str
    lat: float
    lng: float
    google_score: float = Field(..., ge=0, le=100)
    xhs_score: float = Field(..., ge=0, le=100)
    price_level: PriceLevel
    authenticity_tag: AuthenticityTag
    cuisine_type: str
    google_maps_url: str
    xhs_post_count: int = 0
    photo_url: Optional[str] = None
    highlight: Optional[str] = None    # one-line reason from Agent
    # "batch" = from xhs_notes.json | "web_search" = Tavily fallback | "none" = no data
    xhs_source: str = "batch"


