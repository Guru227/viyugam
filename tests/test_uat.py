"""
test_uat.py — User Acceptance Tests (integration tests).

These verify end-to-end command flows across storage, connector, engine,
and tool layers.  The conftest.py autouse fixture patches all storage
paths to tmp_path, so nothing touches ~/.viyugam/.

No mocks except where an external API call would be triggered.
"""
from __future__ import annotations

from datetime import date

import pytest

from viyugam.connectors.local_storage import LocalStorageConnector
from viyugam.models import (
    Budget,
    Dimension,
    Goal,
    Task,
    TaskStatus,
    Transaction,
    TxType,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _connector() -> LocalStorageConnector:
    return LocalStorageConnector()


# ── 1. Capture -> Plan cycle ──────────────────────────────────────────────────

class TestUATCapturePlanCycle:
    """Capture items to triage, verify they appear, mark processed."""

    def test_uat_capture_to_triage(self):
        conn = _connector()

        # Capture three items
        r1 = conn.append_triage("Buy groceries", source="cli")
        r2 = conn.append_triage("Schedule dentist appointment", source="cli")
        r3 = conn.append_triage("Research investment options", source="cli")

        assert r1["status"] == "captured"
        assert r2["status"] == "captured"
        assert r3["status"] == "captured"

        # All three should appear in unprocessed triage
        triage = conn.get_triage(unprocessed_only=True)
        assert triage["count"] == 3
        contents = [item["content"] for item in triage["items"]]
        assert "Buy groceries" in contents
        assert "Schedule dentist appointment" in contents
        assert "Research investment options" in contents

    def test_uat_mark_triage_processed(self):
        conn = _connector()

        r1 = conn.append_triage("Item to process")
        r2 = conn.append_triage("Item to keep")

        # Mark only the first one processed
        conn.mark_triage_processed([r1["id"]])

        triage = conn.get_triage(unprocessed_only=True)
        assert triage["count"] == 1
        assert triage["items"][0]["content"] == "Item to keep"

        # All items still exist when including processed
        all_triage = conn.get_triage(unprocessed_only=False)
        assert all_triage["count"] == 2

    def test_uat_triage_storage_roundtrip(self):
        """Verify triage persists through direct storage module."""
        from viyugam.storage import append_triage, get_triage, mark_triage_processed

        item = append_triage("Direct storage capture")
        items = get_triage(unprocessed_only=True)
        ids = [i.id for i in items]
        assert item.id in ids

        mark_triage_processed([item.id])
        remaining = get_triage(unprocessed_only=True)
        remaining_ids = [i.id for i in remaining]
        assert item.id not in remaining_ids


# ── 2. Task lifecycle ─────────────────────────────────────────────────────────

class TestUATTaskLifecycle:
    """Create, read, complete tasks through the connector."""

    def test_uat_task_lifecycle(self):
        conn = _connector()

        # Create a task
        result = conn.save_task({
            "title": "Write integration tests",
            "dimension": "career",
            "estimated_minutes": 60,
        })
        assert result["status"] == "saved"
        task_id = result["task_id"]
        seq_id = result["seq_id"]
        assert seq_id is not None
        assert seq_id.startswith("T-")

        # Verify it appears in storage
        from viyugam.storage import get_tasks
        tasks = get_tasks()
        task_ids = [t.id for t in tasks]
        assert task_id in task_ids

        found = next(t for t in tasks if t.id == task_id)
        assert found.title == "Write integration tests"
        assert found.dimension == Dimension.CAREER
        assert found.status == TaskStatus.TODO

        # Mark done via seq_id
        done_result = conn.mark_task_done(seq_id)
        assert done_result["status"] == "done"

        # Verify status is DONE
        from viyugam.storage import get_task_by_id
        updated = get_task_by_id(task_id)
        assert updated is not None
        assert updated.status == TaskStatus.DONE

    def test_uat_task_get_via_connector(self):
        conn = _connector()

        conn.save_task({"title": "Task A", "dimension": "health"})
        conn.save_task({"title": "Task B", "dimension": "wealth"})

        result = conn.get_tasks()
        assert result["count"] == 2
        titles = [t["title"] for t in result["tasks"]]
        assert "Task A" in titles
        assert "Task B" in titles

    def test_uat_task_sequential_ids_increment(self):
        conn = _connector()

        r1 = conn.save_task({"title": "First task"})
        r2 = conn.save_task({"title": "Second task"})

        assert r1["seq_id"] == "T-001"
        assert r2["seq_id"] == "T-002"


# ── 3. Goal -> Task alignment ────────────────────────────────────────────────

class TestUATGoalTaskAlignment:
    """Create a goal, align tasks to it, verify progress recomputation."""

    def test_uat_goal_task_alignment(self):
        from viyugam.storage import (
            _recompute_goal_progress,
            get_goals,
            save_goal,
            save_task,
        )

        # Create a goal
        goal = Goal(title="Ship v1.0", dimension=Dimension.CAREER)
        save_goal(goal)

        # Create tasks aligned to that goal
        t1 = Task(title="Write code", dimension=Dimension.CAREER, aligns_to=[goal.id])
        t2 = Task(title="Write tests", dimension=Dimension.CAREER, aligns_to=[goal.id])
        t3 = Task(title="Deploy", dimension=Dimension.CAREER, aligns_to=[goal.id])
        save_task(t1)
        save_task(t2)
        save_task(t3)

        # Initially goal progress should be 0
        pct = _recompute_goal_progress(goal.id)
        assert pct == 0.0

        # Mark one task done
        t1.status = TaskStatus.DONE
        t1.last_done = date.today().isoformat()
        save_task(t1)

        pct = _recompute_goal_progress(goal.id)
        assert pct is not None
        assert abs(pct - 33.3) < 1.0  # 1 out of 3

        # Mark second task done
        t2.status = TaskStatus.DONE
        t2.last_done = date.today().isoformat()
        save_task(t2)

        pct = _recompute_goal_progress(goal.id)
        assert pct is not None
        assert abs(pct - 66.7) < 1.0  # 2 out of 3

        # Verify goal object is persisted with updated progress
        goals = get_goals(active_only=False)
        updated_goal = next(g for g in goals if g.id == goal.id)
        assert abs(updated_goal.progress_pct - 66.7) < 1.0

    def test_uat_mark_done_cascades_goal_progress(self):
        """mark_entity_done should cascade goal progress updates."""
        from viyugam.storage import get_goals, mark_entity_done, save_goal, save_task

        goal = Goal(title="Learn Rust", dimension=Dimension.LEARNING)
        save_goal(goal)

        t1 = Task(title="Read ch1", dimension=Dimension.LEARNING, aligns_to=[goal.id])
        t2 = Task(title="Read ch2", dimension=Dimension.LEARNING, aligns_to=[goal.id])
        save_task(t1)
        save_task(t2)

        # mark_entity_done uses seq_id
        result = mark_entity_done(t1.seq_id)
        assert result is not None
        assert "marked done" in result
        assert "Goal progress updated" in result

        goals = get_goals(active_only=False)
        updated = next(g for g in goals if g.id == goal.id)
        assert abs(updated.progress_pct - 50.0) < 1.0


# ── 4. Finance round-trip ────────────────────────────────────────────────────

class TestUATFinanceRoundtrip:
    """Budget creation, transactions, spent updates, cashflow."""

    def test_uat_finance_roundtrip(self):
        from viyugam.storage import (
            get_budget_by_id,
            get_monthly_cashflow,
            get_transactions,
            save_budget,
            save_transaction,
        )

        today = date.today()
        month_str = today.strftime("%Y-%m")

        # Create a budget
        budget = Budget(
            name="Groceries",
            total_limit=10000.0,
            period_start=f"{month_str}-01",
            period_end=f"{month_str}-28",
            dimension=Dimension.HEALTH,
        )
        save_budget(budget)

        # Record transactions against it
        tx1 = Transaction(
            amount=2500.0,
            category="food",
            description="Weekly groceries",
            tx_type=TxType.EXPENSE,
            budget_id=budget.id,
            occurred_at=f"{month_str}-05T10:00:00",
        )
        tx2 = Transaction(
            amount=1500.0,
            category="food",
            description="Fruits and vegetables",
            tx_type=TxType.EXPENSE,
            budget_id=budget.id,
            occurred_at=f"{month_str}-10T14:00:00",
        )
        save_transaction(tx1)
        save_transaction(tx2)

        # Verify budget spent is updated
        updated_budget = get_budget_by_id(budget.id)
        assert updated_budget is not None
        assert updated_budget.spent == 4000.0

        # Verify transactions are retrievable
        txns = get_transactions(budget_id=budget.id)
        assert len(txns) == 2

        # Verify monthly cashflow
        cashflow = get_monthly_cashflow(month_str)
        assert cashflow["month"] == month_str
        assert cashflow["expenses"] == 4000.0
        assert cashflow["income"] == 0.0
        assert cashflow["net"] == -4000.0
        assert cashflow["by_category"]["food"] == 4000.0

    def test_uat_finance_via_connector(self):
        conn = _connector()
        today = date.today()
        month_str = today.strftime("%Y-%m")

        # Save budget directly
        from viyugam.storage import save_budget
        budget = Budget(
            name="Entertainment",
            total_limit=5000.0,
            period_start=f"{month_str}-01",
            period_end=f"{month_str}-28",
        )
        save_budget(budget)

        # Use connector to save transaction
        conn.save_transaction({
            "amount": 800.0,
            "category": "movies",
            "description": "Cinema tickets",
            "tx_type": "expense",
            "budget_id": budget.id,
        })

        # Use connector to get cashflow
        cashflow = conn.get_monthly_cashflow(month_str)
        assert cashflow["expenses"] == 800.0

    def test_uat_finance_income_and_expense(self):
        from viyugam.storage import get_monthly_cashflow, save_transaction

        today = date.today()
        month_str = today.strftime("%Y-%m")

        # Income
        save_transaction(Transaction(
            amount=50000.0,
            category="salary",
            description="Monthly salary",
            tx_type=TxType.INCOME,
            occurred_at=f"{month_str}-01T09:00:00",
        ))
        # Expense
        save_transaction(Transaction(
            amount=15000.0,
            category="rent",
            description="Monthly rent",
            tx_type=TxType.EXPENSE,
            occurred_at=f"{month_str}-01T09:00:00",
        ))

        cashflow = get_monthly_cashflow(month_str)
        assert cashflow["income"] == 50000.0
        assert cashflow["expenses"] == 15000.0
        assert cashflow["net"] == 35000.0


# ── 5. Tool registry -> Executor -> Connector pipeline ──────────────────────

class TestUATToolPipeline:
    """build_tools_for_agent -> executor -> connector -> storage round-trip."""

    def test_uat_tool_pipeline_task(self):
        from viyugam.engine.tools.registry import build_tools_for_agent

        declarations, dispatch = build_tools_for_agent(["task"])

        # Should have task-domain tools
        tool_names = [d["name"] for d in declarations]
        assert "get_tasks" in tool_names
        assert "save_task" in tool_names
        assert "mark_task_done" in tool_names

        # All dispatch entries should be callable
        for name, fn in dispatch.items():
            assert callable(fn), f"{name} is not callable"

        # Round-trip: save via executor, retrieve via executor
        save_fn = dispatch["save_task"]
        get_fn = dispatch["get_tasks"]

        save_result = save_fn({"title": "Pipeline test task", "dimension": "career"})
        assert save_result["status"] == "saved"
        assert save_result["seq_id"].startswith("T-")

        get_result = get_fn({})
        assert get_result["count"] >= 1
        titles = [t["title"] for t in get_result["tasks"]]
        assert "Pipeline test task" in titles

    def test_uat_tool_pipeline_triage(self):
        from viyugam.engine.tools.registry import build_tools_for_agent

        declarations, dispatch = build_tools_for_agent(["triage"])

        append_fn = dispatch["append_triage"]
        get_fn = dispatch["get_triage"]
        mark_fn = dispatch["mark_triage_processed"]

        r = append_fn({"content": "Executor pipeline item", "source": "test"})
        assert r["status"] == "captured"
        item_id = r["id"]

        items = get_fn({"unprocessed_only": True})
        assert items["count"] >= 1

        mark_fn({"item_ids": [item_id]})
        items_after = get_fn({"unprocessed_only": True})
        remaining_ids = [i["id"] for i in items_after["items"]]
        assert item_id not in remaining_ids

    def test_uat_tool_pipeline_goal(self):
        from viyugam.engine.tools.registry import build_tools_for_agent

        declarations, dispatch = build_tools_for_agent(["goal"])

        save_fn = dispatch["save_goal"]
        get_fn = dispatch["get_goals"]

        save_fn({"title": "Master cooking", "dimension": "joy"})
        result = get_fn({"active_only": True})

        # Should find the goal (plus pseudo-goals from ensure_dirs)
        titles = [g["title"] for g in result["goals"]]
        assert "Master cooking" in titles

    def test_uat_build_all_read_tools(self):
        from viyugam.engine.tools.registry import build_all_read_tools

        declarations, dispatch = build_all_read_tools()
        assert len(declarations) > 0
        assert len(dispatch) > 0

        # All returned tools should be READ-only
        for name in dispatch:
            assert "save" not in name
            assert "mark" not in name
            assert "delete" not in name
            assert "append" not in name


# ── 6. Engine state ──────────────────────────────────────────────────────────

class TestUATEngineState:
    """build_context() returns a populated ContextPacket."""

    def test_uat_build_context(self):
        from viyugam.engine.state import build_context

        ctx = build_context()

        # Basic fields
        assert ctx.today == date.today().isoformat()
        assert ctx.day_name != ""
        assert ctx.current_time != ""

        # Config should be loaded (default if no config.yaml)
        assert ctx.config is not None
        assert ctx.config.user_name == "friend"  # default

        # Values dict should be populated (empty default structure)
        assert isinstance(ctx.values, dict)

        # Resilience defaults to flow
        assert ctx.resilience == "flow"

    def test_uat_build_context_with_config(self):
        """Context reflects saved config."""
        from viyugam.engine.state import build_context
        from viyugam.storage import load_config, save_config

        config = load_config()
        config.user_name = "Guru"
        save_config(config)

        ctx = build_context()
        assert ctx.user_name == "Guru"
        assert ctx.config.user_name == "Guru"


# ── 7. Session persistence ──────────────────────────────────────────────────

class TestUATSessionPersistence:
    """Save and load chat sessions."""

    def test_uat_session_roundtrip(self):
        from viyugam.storage import load_last_chat_session, save_chat_session

        chat = [
            {"role": "user", "content": "Plan my day"},
            {"role": "assistant", "content": "Here is your plan for today..."},
            {"role": "user", "content": "Add a task to buy milk"},
        ]

        save_chat_session(chat)
        loaded = load_last_chat_session()

        assert len(loaded) == 3
        assert loaded[0]["role"] == "user"
        assert loaded[0]["content"] == "Plan my day"
        assert loaded[1]["role"] == "assistant"
        assert loaded[2]["content"] == "Add a task to buy milk"

    def test_uat_session_filters_ansi(self):
        """Sessions should filter out entries with 'Ctrl' in ansi field."""
        from viyugam.storage import load_last_chat_session, save_chat_session

        chat = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "bye", "ansi": "Ctrl+C"},
            {"role": "assistant", "content": "real response"},
        ]

        save_chat_session(chat)
        loaded = load_last_chat_session()

        # The entry with 'Ctrl' in ansi should be filtered out
        assert len(loaded) == 2
        assert loaded[1]["content"] == "real response"


# ── 8. Journal -> Summary extraction ─────────────────────────────────────────

class TestUATJournalSummary:
    """Save a journal with embedded JSON, load and parse the summary."""

    def test_uat_journal_summary_extraction(self):
        from viyugam.storage import load_journal_summary, save_journal

        today_str = date.today().isoformat()
        content = f"""# Journal for {today_str}

Had a productive day. Worked on integration tests.

```json
{{
    "date": "{today_str}",
    "dimension_scores": [
        {{"dimension": "career", "score": 8, "note": "Good coding session"}},
        {{"dimension": "health", "score": 6, "note": "Skipped gym"}}
    ],
    "energy_level": "high",
    "mood": "focused",
    "wins": ["Finished UAT tests", "Fixed two bugs"],
    "challenges": ["Procrastinated on emails"],
    "patterns_noted": ["Best coding happens before lunch"]
}}
```

Overall a good day.
"""
        save_journal(content, for_date=today_str)

        summary = load_journal_summary(for_date=today_str)
        assert summary is not None
        assert summary.date == today_str
        assert summary.energy_level == "high"
        assert summary.mood == "focused"
        assert len(summary.dimension_scores) == 2
        assert summary.dimension_scores[0].dimension == Dimension.CAREER
        assert summary.dimension_scores[0].score == 8
        assert "Finished UAT tests" in summary.wins
        assert "Procrastinated on emails" in summary.challenges
        assert len(summary.patterns_noted) == 1

    def test_uat_journal_no_summary_block(self):
        """Journal without JSON block should return None for summary."""
        from viyugam.storage import load_journal_summary, save_journal

        save_journal("Just a plain journal entry.", for_date="2026-01-01")
        summary = load_journal_summary(for_date="2026-01-01")
        assert summary is None

    def test_uat_journal_via_connector(self):
        conn = _connector()
        today_str = date.today().isoformat()

        content = f"""# Entry
```json
{{
    "date": "{today_str}",
    "energy_level": "medium",
    "mood": "calm",
    "wins": ["Shipped feature"],
    "challenges": [],
    "patterns_noted": []
}}
```
"""
        result = conn.save_journal(content, for_date=today_str)
        assert result["status"] == "saved"

        summary_result = conn.load_journal_summary(for_date=today_str)
        assert summary_result["summary"] is not None
        assert summary_result["summary"]["mood"] == "calm"


# ── 9. Multi-domain coherence ────────────────────────────────────────────────

class TestUATCoherence:
    """Create tasks across dimensions, compute coherence score."""

    def test_uat_coherence_score(self):
        from viyugam.models import SeasonConfig
        from viyugam.storage import compute_coherence_score, load_config, save_config, save_task

        # Set up a season focus
        config = load_config()
        config.season = SeasonConfig(name="builder", focus=Dimension.CAREER)
        save_config(config)
        config = load_config()  # reload to ensure persistence

        today_str = date.today().isoformat()

        # Create done tasks across dimensions with scheduled_date = today
        tasks_data = [
            ("Code review", Dimension.CAREER),
            ("Architecture design", Dimension.CAREER),
            ("Sprint planning", Dimension.CAREER),
            ("Morning run", Dimension.HEALTH),
            ("Read a book", Dimension.LEARNING),
            ("Budget review", Dimension.WEALTH),
            ("Call friend", Dimension.RELATIONSHIPS),
        ]

        for title, dim in tasks_data:
            t = Task(
                title=title,
                dimension=dim,
                status=TaskStatus.DONE,
                scheduled_date=today_str,
                last_done=today_str,
            )
            save_task(t)

        result = compute_coherence_score(config, days=7)
        assert result["score"] is not None
        assert isinstance(result["score"], int)
        assert 0 <= result["score"] <= 100

        # Breakdown should have entries
        assert len(result["breakdown"]) > 0
        assert "career" in result["breakdown"]

        # Career should be the top dimension (3 out of 7 tasks)
        assert result["breakdown"]["career"] > result["breakdown"].get("health", 0)

        # Narrative should be a non-empty string
        assert isinstance(result["narrative"], str)
        assert len(result["narrative"]) > 0

    def test_uat_coherence_no_data(self):
        from viyugam.storage import compute_coherence_score, load_config

        config = load_config()
        result = compute_coherence_score(config, days=7)
        assert result["score"] is None
        assert result["narrative"] == "Not enough data yet."
