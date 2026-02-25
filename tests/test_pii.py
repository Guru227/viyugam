"""
test_pii.py — Tests for PII redaction.
"""
from __future__ import annotations
import pytest

from viyugam.pii import redact


# ── Email redacted ────────────────────────────────────────────────────────────

def test_email_redacted():
    text = "Send invoice to john.doe@example.com by Friday"
    result = redact(text)
    assert "john.doe@example.com" not in result
    assert "<EMAIL>" in result


def test_email_not_in_text_unchanged():
    text = "Call the office to confirm"
    result = redact(text)
    assert result == text


# ── Phone redacted ────────────────────────────────────────────────────────────

def test_phone_redacted():
    text = "Call me at 9876543210 anytime"
    result = redact(text)
    assert "9876543210" not in result
    assert "<PHONE>" in result


def test_phone_not_in_text_unchanged():
    text = "My zip code is 110001"
    result = redact(text)
    # 6-digit codes are not matched by 10-digit phone pattern
    assert result == text


# ── Currency amount redacted ──────────────────────────────────────────────────

def test_rupee_amount_redacted():
    text = "I spent ₹1,500 on groceries today"
    result = redact(text)
    assert "₹1,500" not in result
    assert "<AMOUNT>" in result


def test_dollar_amount_redacted():
    text = "Paid $250.99 for the subscription"
    result = redact(text)
    assert "$250.99" not in result
    assert "<AMOUNT>" in result


# ── Clean text unchanged ──────────────────────────────────────────────────────

def test_clean_text_unchanged():
    text = "Finished the sprint planning session today"
    result = redact(text)
    assert result == text


# ── Multiple PII in one string ────────────────────────────────────────────────

def test_multiple_pii_redacted():
    text = "Email admin@company.org, call 9988776655, paid ₹5,000"
    result = redact(text)
    assert "admin@company.org" not in result
    assert "9988776655" not in result
    assert "₹5,000" not in result
    assert "<EMAIL>" in result
    assert "<PHONE>" in result
    assert "<AMOUNT>" in result
