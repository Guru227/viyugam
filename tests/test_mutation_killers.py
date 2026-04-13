"""test_mutation_killers.py — Tests that kill specific survived mutations.

Each test targets a mutation that survived the mutation testing run,
meaning the code could change at that point and no existing test would catch it.
"""
from __future__ import annotations

from datetime import date, timedelta

import viyugam.storage as storage
from viyugam.models import (
    Budget,
    Dimension,
    Goal,
    Recurrence,
    RecurringItem,
    SeasonConfig,
    Task,
    TaskStatus,
    TxType,
    ViyugamConfig,
)
from viyugam.storage import _paths


# ── _paths._load() returns exactly [] for missing files ─────────────────────
# Mutation: return [] -> return [None]
# Mutation: return [] if name != "state" else {} -> changed operator

class TestPathsLoadExactReturn:
    def test_load_missing_file_returns_empty_list(self):
        result = _paths._load("nonexistent_file_xyz")
        assert result == []
        assert isinstance(result, list)
        assert len(result) == 0

    def test_load_state_missing_returns_empty_dict(self):
        # "state" is special — returns {} not []
        # Delete state file to test the missing-file branch
        state_path = _paths.DATA / "state.json"
        if state_path.exists():
            state_path.unlink()
        result = _paths._load("state")
        assert result == {}
        assert isinstance(result, dict)

    def test_load_empty_file_returns_empty_list(self):
        path = _paths.DATA / "emptytest.json"
        path.write_text("")
        result = _paths._load("emptytest")
        assert result == []

    def test_load_state_empty_file_returns_empty_dict(self):
        state_path = _paths.DATA / "state.json"
        state_path.write_text("")
        result = _paths._load("state")
        assert result == {}

    def test_load_json_missing_returns_empty_list(self):
        from pathlib import Path
        result = _paths._load_json(Path("/tmp/definitely_does_not_exist.json"))
        assert result == []
        assert len(result) == 0

    def test_load_json_empty_returns_empty_list(self):
        path = _paths.DATA / "empty_json_test.json"
        path.write_text("")
        result = _paths._load_json(path)
        assert result == []


# ── calculate_actual_season: boundary at exactly 5 tasks ─────────────────────
# Mutation: if len(recent) < 5 -> if len(recent) <= 5

class TestCalculateActualSeasonBoundary:
    def test_four_tasks_returns_none(self):
        """4 done tasks = insufficient data, returns None."""
        today = date.today().isoformat()
        for i in range(4):
            t = Task(
                title=f"Task {i}", status=TaskStatus.DONE,
                dimension=Dimension.CAREER, scheduled_date=today,
            )
            storage.save_task(t)
        result = storage.calculate_actual_season(days=7)
        assert result is None

    def test_exactly_five_tasks_returns_dimension(self):
        """5 done tasks = sufficient data, should return the dominant dimension."""
        today = date.today().isoformat()
        for i in range(5):
            t = Task(
                title=f"Career task {i}", status=TaskStatus.DONE,
                dimension=Dimension.CAREER, scheduled_date=today,
            )
            storage.save_task(t)
        result = storage.calculate_actual_season(days=7)
        assert result is not None
        assert result == "career"

    def test_six_tasks_returns_dimension(self):
        """6 done tasks = clearly sufficient."""
        today = date.today().isoformat()
        for i in range(6):
            t = Task(
                title=f"Health task {i}", status=TaskStatus.DONE,
                dimension=Dimension.HEALTH, scheduled_date=today,
            )
            storage.save_task(t)
        result = storage.calculate_actual_season(days=7)
        assert result == "health"


# ── _coherence_season_score: no season returns exactly 0 ─────────────────────
# Mutation: return 0 -> return 1

class TestCoherenceSeasonScoreNoSeason:
    def test_no_season_returns_zero(self):
        from viyugam.storage.core import _coherence_season_score
        cfg = ViyugamConfig()  # no season set
        assert cfg.season is None
        score = _coherence_season_score(cfg, {"career": 80.0})
        assert score == 0
        assert score is not None

    def test_with_season_returns_nonzero(self):
        from viyugam.storage.core import _coherence_season_score
        cfg = ViyugamConfig(
            season=SeasonConfig(name="Career Focus", focus=Dimension.CAREER)
        )
        score = _coherence_season_score(cfg, {"career": 80.0})
        assert score > 0


# ── _coherence_narrative: boundary at exactly 75 ─────────────────────────────
# Mutation: if total_score >= 75 -> if total_score > 75

class TestCoherenceNarrativeBoundary:
    def test_score_75_is_strong(self):
        from viyugam.storage.core import _coherence_narrative
        cfg = ViyugamConfig(
            season=SeasonConfig(name="Career Focus", focus=Dimension.CAREER)
        )
        narrative = _coherence_narrative(cfg, {"career": 80.0}, total_score=75)
        assert "Strong" in narrative

    def test_score_74_is_moderate(self):
        from viyugam.storage.core import _coherence_narrative
        cfg = ViyugamConfig(
            season=SeasonConfig(name="Career Focus", focus=Dimension.CAREER)
        )
        narrative = _coherence_narrative(cfg, {"career": 80.0}, total_score=74)
        assert "Moderate" in narrative

    def test_score_49_is_low(self):
        from viyugam.storage.core import _coherence_narrative
        cfg = ViyugamConfig(
            season=SeasonConfig(name="Career Focus", focus=Dimension.CAREER)
        )
        narrative = _coherence_narrative(cfg, {"career": 80.0}, total_score=49)
        assert "Low" in narrative


# ── get_budget_by_id: exact ID match vs prefix match ─────────────────────────
# Mutation: if b.id == budget_id -> b.id != budget_id

class TestBudgetByIdExactMatch:
    def test_exact_id_match(self):
        today = date.today()
        b = Budget(
            name="Test", total_limit=10000.0,
            period_start=today.isoformat(),
            period_end=(today + timedelta(days=30)).isoformat(),
        )
        storage.save_budget(b)
        # Exact full ID match
        found = storage.get_budget_by_id(b.id)
        assert found is not None
        assert found.id == b.id
        assert found.name == "Test"

    def test_nonexistent_id_returns_none(self):
        result = storage.get_budget_by_id("zzz_nonexistent_zzz")
        assert result is None


# ── get_task_by_id: exact ID match vs prefix match ──────────────────────────
# Mutation: if t.id == task_id -> t.id != task_id

class TestTaskByIdExactMatch:
    def test_exact_full_id_match(self):
        task = Task(title="Exact match test", dimension=Dimension.CAREER)
        storage.save_task(task)
        found = storage.get_task_by_id(task.id)
        assert found is not None
        assert found.id == task.id
        assert found.title == "Exact match test"

    def test_nonexistent_full_id_returns_none(self):
        result = storage.get_task_by_id("zzz_totally_fake_id_zzz")
        assert result is None

    def test_two_tasks_exact_match_returns_correct_one(self):
        t1 = Task(title="First task")
        t2 = Task(title="Second task")
        storage.save_task(t1)
        storage.save_task(t2)
        found = storage.get_task_by_id(t1.id)
        assert found is not None
        assert found.title == "First task"


# ── _finance_recurring_lines: EXPENSE vs INCOME separation ──────────────────
# Mutation: if r.tx_type == TxType.EXPENSE -> r.tx_type != TxType.EXPENSE

class TestFinanceRecurringLines:
    def test_expense_and_income_separated(self):
        from viyugam.storage.finance import _finance_recurring_lines
        expense = RecurringItem(
            name="Rent", amount=15000.0, tx_type=TxType.EXPENSE,
            frequency=Recurrence.MONTHLY, day_of_month=1,
        )
        income = RecurringItem(
            name="Salary", amount=80000.0, tx_type=TxType.INCOME,
            frequency=Recurrence.MONTHLY, day_of_month=1,
        )
        storage.save_recurring_item(expense)
        storage.save_recurring_item(income)

        lines = _finance_recurring_lines()
        text = "\n".join(lines)
        # Expense total should be 15000, income should be 80000
        assert "15,000" in text
        assert "80,000" in text
        # They should NOT be swapped
        expense_idx = text.index("expenses=")
        income_idx = text.index("income=")
        expense_val = text[expense_idx:expense_idx + 30]
        income_val = text[income_idx:income_idx + 30]
        assert "15,000" in expense_val
        assert "80,000" in income_val


# ── _recompute_goal_progress: habits should NOT count ────────────────────────
# Mutation: include_habits=False -> include_habits=True

class TestGoalProgressExcludesHabits:
    def test_habits_excluded_from_goal_progress(self):
        g = Goal(title="Test goal", dimension=Dimension.CAREER)
        storage.save_goal(g)

        # Regular task aligned to goal — done
        t1 = Task(
            title="Regular task", aligns_to=[g.id],
            status=TaskStatus.DONE, is_habit=False,
        )
        storage.save_task(t1)

        # Habit task aligned to goal — done (should NOT count)
        t2 = Task(
            title="Daily habit", aligns_to=[g.id],
            status=TaskStatus.DONE, is_habit=True,
        )
        storage.save_task(t2)

        # Another regular task — not done
        t3 = Task(
            title="Pending task", aligns_to=[g.id],
            status=TaskStatus.TODO, is_habit=False,
        )
        storage.save_task(t3)

        # Without habits: 1 done out of 2 regular = 50%
        # With habits: 2 done out of 3 total = 66.7%
        pct = storage._recompute_goal_progress(g.id)
        assert pct is not None
        assert pct == 50.0  # Must be 50%, not 66.7%

    def test_goal_progress_only_regular_tasks(self):
        g = Goal(title="No habits goal", dimension=Dimension.HEALTH)
        storage.save_goal(g)

        t1 = Task(title="T1", aligns_to=[g.id], status=TaskStatus.DONE)
        t2 = Task(title="T2", aligns_to=[g.id], status=TaskStatus.TODO)
        storage.save_task(t1)
        storage.save_task(t2)

        pct = storage._recompute_goal_progress(g.id)
        assert pct == 50.0
