"""storage/finance.py — Budget, transactions, recurring, cashflow."""
from __future__ import annotations

import json
from datetime import date
from typing import Optional

import yaml

from viyugam.models import Budget, RecurringItem, Transaction, TxType

from . import _paths

# ── Budgets ───────────────────────────────────────────────────────────────────

def get_budgets() -> list[Budget]:
    raw = _paths._load_json(_paths.BUDGETS_FILE)
    return [Budget(**b) for b in raw]


def get_budget_by_id(budget_id: str) -> Optional[Budget]:
    for b in get_budgets():
        if b.id == budget_id or b.id.startswith(budget_id):
            return b
    return None


def save_budget(b: Budget) -> None:
    raw = _paths._load_json(_paths.BUDGETS_FILE)
    raw = [x for x in raw if x["id"] != b.id]
    raw.append(b.model_dump())
    _paths._save_json(_paths.BUDGETS_FILE, raw)


# ── Transactions ──────────────────────────────────────────────────────────────

def get_transactions(budget_id: str | None = None) -> list[Transaction]:
    raw = _paths._load_json(_paths.TRANSACTIONS_FILE)
    txns = [Transaction(**t) for t in raw]
    if budget_id:
        txns = [t for t in txns if t.budget_id == budget_id]
    return txns


def save_transaction(t: Transaction) -> None:
    raw = _paths._load_json(_paths.TRANSACTIONS_FILE)
    raw = [x for x in raw if x["id"] != t.id]
    raw.append(t.model_dump())
    _paths._save_json(_paths.TRANSACTIONS_FILE, raw)
    if t.budget_id:
        b = get_budget_by_id(t.budget_id)
        if b:
            # Compute spent from the already-written raw list to avoid re-reading
            budget_txns = [Transaction(**x) for x in raw if x.get("budget_id") == t.budget_id]
            b.spent = round(sum(x.amount for x in budget_txns), 2)
            save_budget(b)


def get_budget_summary() -> list[dict]:
    today = date.today().isoformat()
    budgets = [b for b in get_budgets() if b.period_end >= today]
    result = []
    for b in budgets:
        remaining = round(b.total_limit - b.spent, 2)
        pct = round((b.spent / b.total_limit) * 100, 1) if b.total_limit > 0 else 0
        result.append({
            "id": b.id, "name": b.name, "total_limit": b.total_limit,
            "spent": b.spent, "remaining": remaining, "pct": pct,
            "dimension": b.dimension.value if b.dimension else None,
        })
    return result


# ── Recurring items ───────────────────────────────────────────────────────────

def get_recurring_items(active_only: bool = True) -> list[RecurringItem]:
    raw = _paths._load_json(_paths.RECURRING_FILE)
    items = [RecurringItem(**r) for r in raw]
    if active_only:
        items = [i for i in items if i.is_active]
    return items


def save_recurring_item(item: RecurringItem) -> None:
    raw = _paths._load_json(_paths.RECURRING_FILE)
    raw = [r for r in raw if r["id"] != item.id]
    raw.append(item.model_dump())
    _paths._save_json(_paths.RECURRING_FILE, raw)


def delete_recurring_item(item_id: str) -> None:
    raw = _paths._load_json(_paths.RECURRING_FILE)
    _paths._save_json(_paths.RECURRING_FILE, [r for r in raw if r["id"] != item_id])


# ── Period queries ────────────────────────────────────────────────────────────

def get_transactions_by_period(start: str, end: str) -> list[Transaction]:
    all_txns = get_transactions()
    return [t for t in all_txns if start <= t.occurred_at[:10] <= end]


def get_spending_by_category(start: str, end: str) -> dict[str, float]:
    txns = [t for t in get_transactions_by_period(start, end) if t.tx_type == TxType.EXPENSE]
    result: dict[str, float] = {}
    for t in txns:
        result[t.category] = round(result.get(t.category, 0.0) + t.amount, 2)
    return result


def get_monthly_cashflow(month: str) -> dict:
    start = f"{month}-01"
    year, mon = int(month[:4]), int(month[5:7])
    import calendar as _cal
    last_day = _cal.monthrange(year, mon)[1]
    end = f"{month}-{last_day:02d}"

    txns = get_transactions_by_period(start, end)
    income = round(sum(t.amount for t in txns if t.tx_type == TxType.INCOME), 2)
    expenses = round(sum(t.amount for t in txns if t.tx_type == TxType.EXPENSE), 2)
    net = round(income - expenses, 2)
    by_category: dict[str, float] = {}
    for t in txns:
        if t.tx_type == TxType.EXPENSE:
            by_category[t.category] = round(by_category.get(t.category, 0.0) + t.amount, 2)
    return {
        "month": month, "income": income, "expenses": expenses,
        "net": net, "by_category": by_category,
        "transactions": [t.model_dump() for t in txns],
    }


def get_due_recurring_items(as_of: str | None = None) -> list[RecurringItem]:
    today_date = date.fromisoformat(as_of) if as_of else date.today()
    this_month = today_date.strftime("%Y-%m")
    items = get_recurring_items(active_only=True)
    due = []
    for item in items:
        if item.day_of_month != today_date.day:
            continue
        if item.last_logged and item.last_logged[:7] == this_month:
            continue
        due.append(item)
    return due


# ── Finance context (for agents) ─────────────────────────────────────────────

def _finance_budget_lines() -> list[str]:
    lines: list[str] = []
    summaries = get_budget_summary()
    if summaries:
        lines.append(f"\nActive budgets ({len(summaries)}):")
        for b in summaries:
            lines.append(
                f"  {b['name']}: {b['spent']:,.0f}/{b['total_limit']:,.0f} spent ({b['pct']}% used)"
            )
    return lines


def _finance_cashflow_lines(months: int) -> list[str]:
    lines: list[str] = []
    today = date.today()
    cashflows = []
    for i in range(months):
        year = today.year
        mon = today.month - i
        while mon <= 0:
            mon += 12
            year -= 1
        month_str = f"{year}-{mon:02d}"
        cf = get_monthly_cashflow(month_str)
        cashflows.append(cf)

    if cashflows:
        lines.append(f"\nMonthly cashflow (last {months} months):")
        for cf in cashflows:
            lines.append(
                f"  {cf['month']}: income={cf['income']:,.0f}  "
                f"expenses={cf['expenses']:,.0f}  net={cf['net']:+,.0f}"
            )
        top_cats = sorted(
            cashflows[0]["by_category"].items(), key=lambda x: -x[1]
        )[:5]
        if top_cats:
            lines.append(f"\nTop expense categories ({cashflows[0]['month']}):")
            for cat, amt in top_cats:
                lines.append(f"  {cat}: {amt:,.0f}")
    return lines


def _finance_recurring_lines() -> list[str]:
    lines: list[str] = []
    all_recurring = get_recurring_items(active_only=True)
    if all_recurring:
        total_monthly_expense = sum(
            r.amount for r in all_recurring
            if r.tx_type == TxType.EXPENSE and r.frequency.value == "monthly"
        )
        total_monthly_income = sum(
            r.amount for r in all_recurring
            if r.tx_type == TxType.INCOME and r.frequency.value == "monthly"
        )
        lines.append(
            f"\nRecurring items ({len(all_recurring)} active): "
            f"monthly expenses={total_monthly_expense:,.0f}  "
            f"monthly income={total_monthly_income:,.0f}"
        )
    return lines


def get_finance_context(months: int = 3) -> str:
    lines = ["FINANCE CONTEXT:"]
    lines.extend(_finance_budget_lines())
    lines.extend(_finance_cashflow_lines(months))
    lines.extend(_finance_recurring_lines())
    return "\n".join(lines)


# ── Budget YAML ───────────────────────────────────────────────────────────────

def load_budget_yaml() -> dict:
    if _paths.BUDGET_YAML.exists():
        try:
            data = yaml.safe_load(_paths.BUDGET_YAML.read_text()) or {}
            return data
        except Exception:
            pass

    # Migrate from budgets.json
    envelopes: list[dict] = []
    if _paths.BUDGETS_FILE.exists():
        try:
            raw = json.loads(_paths.BUDGETS_FILE.read_text().strip() or "[]")
            for b in raw:
                envelopes.append({
                    "name": b.get("name", ""),
                    "monthly_limit": b.get("total_limit", 0),
                    "category": b.get("dimension") or "general",
                })
        except Exception:
            pass
    budget_data: dict = {"currency": "\u20b9", "envelopes": envelopes}
    _paths.BUDGET_YAML.write_text(
        yaml.dump(budget_data, allow_unicode=True, default_flow_style=False)
    )
    return budget_data


def save_budget_yaml(data: dict) -> None:
    _paths.BUDGET_YAML.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False)
    )


def get_budget_envelope_summary() -> list[dict]:
    data = load_budget_yaml()
    return data.get("envelopes", [])
