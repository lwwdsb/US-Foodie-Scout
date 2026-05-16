"""
Unit tests for schemas/models.py.

Covers: compute_authenticity_tag (all 4 quadrants + boundaries),
ChatRequest validation, and field constraints.
"""

import pytest
from pydantic import ValidationError
from schemas.models import (
    AuthenticityTag,
    ChatRequest,
    PriceLevel,
    compute_authenticity_tag,
)


# ── compute_authenticity_tag ──────────────────────────────────────────────────

class TestComputeAuthenticityTag:
    def test_must_visit_both_high(self):
        assert compute_authenticity_tag(80, 80) == AuthenticityTag.must_visit

    def test_must_visit_at_exact_boundary(self):
        assert compute_authenticity_tag(75, 75) == AuthenticityTag.must_visit

    def test_hidden_gem_xhs_high_google_low(self):
        assert compute_authenticity_tag(76, 74) == AuthenticityTag.hidden_gem

    def test_overhyped_google_high_xhs_low(self):
        assert compute_authenticity_tag(74, 76) == AuthenticityTag.overhyped

    def test_general_both_low(self):
        assert compute_authenticity_tag(50, 50) == AuthenticityTag.general

    def test_general_at_boundary_below_threshold(self):
        assert compute_authenticity_tag(74.9, 74.9) == AuthenticityTag.general

    def test_extremes_zero(self):
        assert compute_authenticity_tag(0, 0) == AuthenticityTag.general

    def test_extremes_hundred(self):
        assert compute_authenticity_tag(100, 100) == AuthenticityTag.must_visit


# ── ChatRequest validation ────────────────────────────────────────────────────

class TestChatRequest:
    def test_valid_minimal(self):
        req = ChatRequest(message="推荐川菜", session_id="abc-123")
        assert req.message == "推荐川菜"
        assert req.budget is None
        assert req.cuisine is None

    def test_message_is_stripped(self):
        req = ChatRequest(message="  推荐川菜  ", session_id="abc")
        assert req.message == "推荐川菜"

    def test_message_empty_raises(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="", session_id="abc")

    def test_message_whitespace_only_raises(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="   ", session_id="abc")

    def test_message_too_long_raises(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="x" * 501, session_id="abc")

    def test_session_id_empty_raises(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="推荐川菜", session_id="")

    def test_budget_valid_enum(self):
        req = ChatRequest(message="推荐川菜", session_id="abc", budget=PriceLevel.moderate)
        assert req.budget == PriceLevel.moderate

    def test_cuisine_too_long_raises(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="推荐餐厅", session_id="abc", cuisine="x" * 51)
