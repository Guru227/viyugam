"""
agents/finance.py — Finance Analyst agent.
Analyses budget data, cashflow, and recurring items.
Returns structured insights with wealth score.
"""
from __future__ import annotations
import json
import os

import anthropic


def _client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set.")
    return anthropic.Anthropic(api_key=api_key)


FINANCE_SYSTEM = """You are a direct, numbers-first financial analyst for a personal Life OS.

Rules:
- Reference actual numbers in every insight. No vague statements.
- Flag anomalies: sudden category spikes, negative net cashflow, budgets near limit.
- Savings rate = (income - expenses) / income * 100. If income is 0, note it.
- Wealth score 1-10: 1 = critical (debt spiral, no income), 10 = excellent (high savings rate, growing net worth).
- Be honest. If the data shows overspending, say it plainly.
- Keep recommendations actionable — specific amounts or categories.

Return ONLY a JSON object:
{
  "wealth_score": 1-10,
  "headline": "One sentence: the financial situation in plain terms",
  "savings_rate": null or float (percentage),
  "insights": ["specific observation with numbers", ...],
  "flags": ["anomaly or risk worth addressing", ...],
  "recommendations": ["concrete action", ...],
  "monthly_summary": "2-3 sentences synthesising the cashflow pattern"
}"""


def analyze_finance(
    budget_summaries: list[dict],
    monthly_cashflow: list[dict],
    recurring_items: list[dict],
    constitution: str = "",
) -> dict:
    """
    Run AI finance analysis.
    Returns: {wealth_score, headline, insights, flags, recommendations,
              savings_rate, monthly_summary}
    """
    cf_text = ""
    if monthly_cashflow:
        cf_text = "Monthly cashflow:\n" + "\n".join(
            f"  {cf['month']}: income={cf.get('income', 0):,.0f}  "
            f"expenses={cf.get('expenses', 0):,.0f}  net={cf.get('net', 0):+,.0f}"
            + (
                "\n    Top categories: " + ", ".join(
                    f"{k}={v:,.0f}" for k, v in
                    sorted(cf.get("by_category", {}).items(), key=lambda x: -x[1])[:4]
                ) if cf.get("by_category") else ""
            )
            for cf in monthly_cashflow
        )

    budget_text = "No active budgets."
    if budget_summaries:
        budget_text = "Active budgets:\n" + "\n".join(
            f"  {b['name']}: {b['spent']:,.0f}/{b['total_limit']:,.0f} ({b['pct']}% used)"
            for b in budget_summaries
        )

    recurring_text = "No recurring items."
    if recurring_items:
        recurring_text = "Recurring items:\n" + "\n".join(
            f"  [{r.get('tx_type', 'expense')}] {r['name']}: {r['amount']:,.0f} "
            f"({r.get('frequency', 'monthly')})"
            for r in recurring_items
        )

    constitution_section = f"\nUser's constitution (values/goals):\n{constitution}\n" if constitution else ""

    user_content = f"""{budget_text}

{cf_text}

{recurring_text}
{constitution_section}
Analyse the financial situation."""

    client = _client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        system=FINANCE_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    return json.loads(text)
