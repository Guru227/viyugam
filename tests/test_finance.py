"""
test_finance.py — Tests for budget and transaction logic.
"""
from __future__ import annotations
import pytest
from datetime import date, timedelta

import viyugam.storage as storage
from viyugam.models import Budget, Transaction, Dimension


def _active_budget(name="Test Budget", limit=10000.0) -> Budget:
    today = date.today()
    return Budget(
        name=name,
        total_limit=limit,
        period_start=today.isoformat(),
        period_end=(today + timedelta(days=30)).isoformat(),
    )


# ── Budget creation ───────────────────────────────────────────────────────────

def test_budget_creation_and_retrieval():
    b = _active_budget("OpEx", 50000.0)
    storage.save_budget(b)
    found = storage.get_budget_by_id(b.id)
    assert found is not None
    assert found.name == "OpEx"
    assert found.total_limit == 50000.0
    assert found.spent == 0.0


def test_budget_partial_id_lookup():
    b = _active_budget("Partial lookup")
    storage.save_budget(b)
    found = storage.get_budget_by_id(b.id[:5])
    assert found is not None


# ── Transaction logged, budget.spent updated ──────────────────────────────────

def test_transaction_updates_budget_spent():
    b = _active_budget(limit=20000.0)
    storage.save_budget(b)

    t = Transaction(amount=2500.0, category="food", description="Monthly groceries",
                    budget_id=b.id)
    storage.save_transaction(t)

    updated = storage.get_budget_by_id(b.id)
    assert updated.spent == 2500.0


def test_multiple_transactions_on_one_budget():
    b = _active_budget("Multi", 15000.0)
    storage.save_budget(b)

    for amount in [1000.0, 2000.0, 500.0]:
        t = Transaction(amount=amount, category="misc", description=f"Expense {amount}",
                        budget_id=b.id)
        storage.save_transaction(t)

    updated = storage.get_budget_by_id(b.id)
    assert updated.spent == 3500.0


# ── get_budget_summary returns correct remaining/pct ──────────────────────────

def test_budget_summary_remaining_and_pct():
    b = _active_budget("Summary test", 10000.0)
    storage.save_budget(b)

    t = Transaction(amount=3000.0, category="food", description="Food",
                    budget_id=b.id)
    storage.save_transaction(t)

    summaries = storage.get_budget_summary()
    s = next(x for x in summaries if x["id"] == b.id)
    assert s["remaining"] == 7000.0
    assert s["pct"] == 30.0


# ── Transaction without budget_id ────────────────────────────────────────────

def test_transaction_without_budget_id():
    t = Transaction(amount=150.0, category="transport", description="Cab ride")
    storage.save_transaction(t)  # Must not raise

    txns = storage.get_transactions()
    assert any(x.id == t.id for x in txns)


# ── Budget period filtering ───────────────────────────────────────────────────

def test_expired_budgets_excluded_from_summary():
    expired = Budget(
        name="Old budget", total_limit=5000.0,
        period_start="2025-01-01", period_end="2025-01-31"
    )
    active = _active_budget("Active one", 8000.0)
    storage.save_budget(expired)
    storage.save_budget(active)

    summaries = storage.get_budget_summary()
    ids = [s["id"] for s in summaries]
    assert expired.id not in ids
    assert active.id in ids


# ── Transaction amount precision ─────────────────────────────────────────────

def test_transaction_amount_precision():
    b = _active_budget("Precision", 1000.0)
    storage.save_budget(b)

    t1 = Transaction(amount=333.33, category="food", description="A",
                     budget_id=b.id)
    t2 = Transaction(amount=333.33, category="food", description="B",
                     budget_id=b.id)
    t3 = Transaction(amount=333.34, category="food", description="C",
                     budget_id=b.id)

    storage.save_transaction(t1)
    storage.save_transaction(t2)
    storage.save_transaction(t3)

    updated = storage.get_budget_by_id(b.id)
    assert updated.spent == round(333.33 + 333.33 + 333.34, 2)


# ── get_transactions filter by budget ─────────────────────────────────────────

def test_get_transactions_by_budget():
    b1 = _active_budget("Budget A")
    b2 = _active_budget("Budget B")
    storage.save_budget(b1)
    storage.save_budget(b2)

    t1 = Transaction(amount=100, category="food", description="T1", budget_id=b1.id)
    t2 = Transaction(amount=200, category="food", description="T2", budget_id=b2.id)
    storage.save_transaction(t1)
    storage.save_transaction(t2)

    result = storage.get_transactions(budget_id=b1.id)
    assert any(x.id == t1.id for x in result)
    assert not any(x.id == t2.id for x in result)


# ── Zero-limit budget pct ─────────────────────────────────────────────────────

def test_budget_zero_limit():
    b = Budget(name="Zero limit", total_limit=0.0,
               period_start=date.today().isoformat(),
               period_end=(date.today() + timedelta(days=30)).isoformat())
    storage.save_budget(b)

    summaries = storage.get_budget_summary()
    s = next((x for x in summaries if x["id"] == b.id), None)
    assert s is not None
    assert s["pct"] == 0  # no ZeroDivisionError
