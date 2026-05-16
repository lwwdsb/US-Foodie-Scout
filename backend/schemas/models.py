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


def compute_authenticity_tag(xhs_score: float, google_score: float) -> AuthenticityTag:
    high_xhs = xhs_score >= 75
    high_google = google_score >= 75
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


