"""
test_storage_extended.py — Coverage tests for storage submodules below 90%.

Covers: sessions, calendar (ICS), triage, journal, projects, values, plans, tasks.
The autouse conftest fixture patches all paths to tmp_path.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

import pytest
import yaml

import viyugam.storage as storage
from viyugam.storage import _paths
from viyugam.models import (
    CalendarEntry,
    Dimension,
    Project,
    ProjectPlan,
    ProjectStatus,
    SomedayItem,
    Task,
    TaskStatus,
    TriageItem,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. sessions.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestSessions:
    """save_chat_session / load_last_chat_session."""

    def test_save_and_load_today(self):
        chat = [{"role": "user", "content": "hello"}]
        storage.save_chat_session(chat)
        loaded = storage.load_last_chat_session()
        assert loaded == chat

    def test_entries_with_ctrl_ansi_are_stripped(self):
        chat = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "ansi": "Ctrl+C to quit"},
        ]
        storage.save_chat_session(chat)
        loaded = storage.load_last_chat_session()
        assert len(loaded) == 1
        assert loaded[0]["role"] == "user"

    def test_empty_session_list_not_saved(self):
        # Only entries with Ctrl ansi — after filtering, entries is empty
        chat = [{"role": "assistant", "ansi": "Press Ctrl+D"}]
        storage.save_chat_session(chat)
        # The file should not exist (nothing was written)
        today_file = _paths.SESSIONS_DIR / f"{date.today().isoformat()}.json"
        assert not today_file.exists()

    def test_load_returns_empty_when_no_session(self):
        assert storage.load_last_chat_session() == []

    def test_load_yesterday_when_before_noon(self, monkeypatch):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        yesterday_chat = [{"role": "user", "content": "yesterday"}]
        path = _paths.SESSIONS_DIR / f"{yesterday}.json"
        path.write_text(json.dumps(yesterday_chat))

        # Patch datetime.now().hour to be before noon
        _real_datetime = datetime

        class FakeDatetime(_real_datetime):
            @classmethod
            def now(cls, tz=None):
                return _real_datetime(
                    date.today().year, date.today().month, date.today().day,
                    8, 0, 0,
                )

        monkeypatch.setattr("viyugam.storage.sessions.datetime", FakeDatetime)
        loaded = storage.load_last_chat_session()
        assert loaded == yesterday_chat

    def test_no_yesterday_when_after_noon(self, monkeypatch):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        yesterday_chat = [{"role": "user", "content": "yesterday"}]
        path = _paths.SESSIONS_DIR / f"{yesterday}.json"
        path.write_text(json.dumps(yesterday_chat))

        _real_datetime = datetime

        class FakeDatetime(_real_datetime):
            @classmethod
            def now(cls, tz=None):
                return _real_datetime(
                    date.today().year, date.today().month, date.today().day,
                    14, 0, 0,
                )

        monkeypatch.setattr("viyugam.storage.sessions.datetime", FakeDatetime)
        loaded = storage.load_last_chat_session()
        assert loaded == []

    def test_prune_old_sessions(self):
        old_date = (date.today() - timedelta(days=35)).isoformat()
        old_path = _paths.SESSIONS_DIR / f"{old_date}.json"
        old_path.write_text(json.dumps([{"role": "user", "content": "old"}]))

        recent_date = (date.today() - timedelta(days=5)).isoformat()
        recent_path = _paths.SESSIONS_DIR / f"{recent_date}.json"
        recent_path.write_text(json.dumps([{"role": "user", "content": "recent"}]))

        # save_chat_session triggers the pruning
        storage.save_chat_session([{"role": "user", "content": "now"}])

        assert not old_path.exists(), "Old session file should be pruned"
        assert recent_path.exists(), "Recent session file should be kept"

    def test_corrupt_today_file_returns_empty(self):
        today_file = _paths.SESSIONS_DIR / f"{date.today().isoformat()}.json"
        today_file.write_text("NOT JSON")
        loaded = storage.load_last_chat_session()
        assert loaded == []


# ═══════════════════════════════════════════════════════════════════════════════
# 2. calendar.py — ICS parsing
# ═══════════════════════════════════════════════════════════════════════════════


SAMPLE_ICS = """\
BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART:20260316T090000Z
DTEND:20260316T100000Z
SUMMARY:Morning standup
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20260317
SUMMARY:All-day offsite
END:VEVENT
BEGIN:VEVENT
DTSTART:20260318T140000
DTEND:20260318T150000
SUMMARY:Afternoon review
END:VEVENT
END:VCALENDAR
"""


class TestCalendarICS:
    """parse_ics, get_ics_events_for_period, delete_calendar_entry."""

    def test_parse_ics_basic(self):
        _paths.CALENDAR_ICS.write_text(SAMPLE_ICS)
        events = storage.parse_ics()
        assert len(events) == 3

        standup = next(e for e in events if e["title"] == "Morning standup")
        assert standup["date"] == "2026-03-16"
        assert standup["start_time"] == "09:00"
        assert standup["end_time"] == "10:00"
        assert standup["all_day"] is False

    def test_parse_ics_all_day(self):
        _paths.CALENDAR_ICS.write_text(SAMPLE_ICS)
        events = storage.parse_ics()
        offsite = next(e for e in events if e["title"] == "All-day offsite")
        assert offsite["all_day"] is True
        assert offsite["start_time"] is None

    def test_parse_ics_no_file_returns_empty(self):
        # CALENDAR_ICS should not exist yet (conftest does not create it)
        assert storage.parse_ics() == []

    def test_parse_ics_empty_file(self):
        _paths.CALENDAR_ICS.write_text("")
        assert storage.parse_ics() == []

    def test_parse_ics_no_dtstart_skipped(self):
        bad_ics = """\
BEGIN:VCALENDAR
BEGIN:VEVENT
SUMMARY:No date event
END:VEVENT
END:VCALENDAR
"""
        _paths.CALENDAR_ICS.write_text(bad_ics)
        events = storage.parse_ics()
        assert len(events) == 0

    def test_get_ics_events_for_period(self):
        _paths.CALENDAR_ICS.write_text(SAMPLE_ICS)
        events = storage.get_ics_events_for_period(
            date(2026, 3, 16), date(2026, 3, 16),
        )
        assert len(events) == 1
        assert events[0]["title"] == "Morning standup"

    def test_get_ics_events_for_period_range(self):
        _paths.CALENDAR_ICS.write_text(SAMPLE_ICS)
        events = storage.get_ics_events_for_period(
            date(2026, 3, 16), date(2026, 3, 18),
        )
        assert len(events) == 3

    def test_delete_calendar_entry(self):
        entry = CalendarEntry(title="Delete me", date="2026-06-01")
        storage.save_calendar_entry(entry)
        assert any(e["id"] == entry.id for e in json.loads(_paths.CALENDAR_FILE.read_text()))

        storage.delete_calendar_entry(entry.id)
        assert not any(e["id"] == entry.id for e in json.loads(_paths.CALENDAR_FILE.read_text()))

    def test_parse_ics_with_local_datetime(self):
        """Events with local datetime (no Z suffix) should parse correctly."""
        _paths.CALENDAR_ICS.write_text(SAMPLE_ICS)
        events = storage.parse_ics()
        review = next(e for e in events if e["title"] == "Afternoon review")
        assert review["date"] == "2026-03-18"
        assert review["start_time"] == "14:00"
        assert review["end_time"] == "15:00"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. triage.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestTriage:
    """append_triage, get_triage, save_triage_item, recent logs, someday."""

    def test_append_and_get_triage(self):
        item = storage.append_triage("Buy milk", source="cli")
        assert item.content == "Buy milk"
        assert item.source == "cli"
        items = storage.get_triage(unprocessed_only=True)
        assert any(i.id == item.id for i in items)

    def test_get_triage_unprocessed_filter(self):
        item1 = storage.append_triage("Unprocessed item")
        item2 = storage.append_triage("Processed item")
        # Mark item2 as processed
        item2.processed = True
        storage.save_triage_item(item2)

        unprocessed = storage.get_triage(unprocessed_only=True)
        assert any(i.id == item1.id for i in unprocessed)
        assert not any(i.id == item2.id for i in unprocessed)

        all_items = storage.get_triage(unprocessed_only=False)
        assert any(i.id == item2.id for i in all_items)

    def test_snoozed_items_filtered_when_future(self):
        item = storage.append_triage("Snoozed task")
        item.snooze_until = (date.today() + timedelta(days=5)).isoformat()
        storage.save_triage_item(item)

        unprocessed = storage.get_triage(unprocessed_only=True)
        assert not any(i.id == item.id for i in unprocessed)

    def test_snoozed_items_shown_when_past(self):
        item = storage.append_triage("Past snooze")
        item.snooze_until = (date.today() - timedelta(days=1)).isoformat()
        storage.save_triage_item(item)

        unprocessed = storage.get_triage(unprocessed_only=True)
        assert any(i.id == item.id for i in unprocessed)

    def test_save_triage_item_updates_existing(self):
        item = storage.append_triage("Original content")
        item.boardroom_notes = "Decided to act on this"
        storage.save_triage_item(item)

        all_items = storage.get_triage(unprocessed_only=False)
        found = next(i for i in all_items if i.id == item.id)
        assert found.boardroom_notes == "Decided to act on this"

    def test_get_recent_triage_logs(self):
        for i in range(7):
            storage.append_triage(f"Item {i}")
        recent = storage.get_recent_triage_logs(n=5)
        assert len(recent) == 5

    def test_get_recent_triage_logs_empty(self):
        assert storage.get_recent_triage_logs() == []

    def test_get_triage_file_missing(self):
        if _paths.TRIAGE_FILE.exists():
            _paths.TRIAGE_FILE.unlink()
        assert storage.get_triage() == []

    def test_get_someday_empty(self):
        assert storage.get_someday() == []

    def test_save_and_get_someday(self):
        item = SomedayItem(proposal="Write a novel")
        storage.save_someday(item)
        items = storage.get_someday()
        assert any(s.id == item.id for s in items)
        assert items[0].proposal == "Write a novel"

    def test_save_someday_updates_existing(self):
        item = SomedayItem(proposal="Original")
        storage.save_someday(item)
        item.consensus = "Revisit in Q2"
        storage.save_someday(item)
        items = storage.get_someday()
        matching = [s for s in items if s.id == item.id]
        assert len(matching) == 1
        assert matching[0].consensus == "Revisit in Q2"

    def test_delete_someday(self):
        item = SomedayItem(proposal="Delete this")
        storage.save_someday(item)
        storage.delete_someday(item.id)
        items = storage.get_someday()
        assert not any(s.id == item.id for s in items)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. journal.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestJournal:
    """save_journal, get_recent_journals, load_journal_summary, save_research."""

    def test_save_journal_writes_file(self, mock_journal_thread):
        content = "# Journal\nGreat day today."
        path = storage.save_journal(content)
        assert path.exists()
        assert path.read_text() == content

    def test_save_journal_for_specific_date(self, mock_journal_thread):
        content = "# Journal for 2026-01-15"
        path = storage.save_journal(content, for_date="2026-01-15")
        assert path.name == "2026-01-15.md"
        assert path.read_text() == content

    def test_load_journal_exists(self, mock_journal_thread):
        storage.save_journal("Hello journal", for_date="2026-03-01")
        loaded = storage.load_journal(for_date="2026-03-01")
        assert loaded == "Hello journal"

    def test_load_journal_missing(self):
        assert storage.load_journal(for_date="1999-01-01") is None

    def test_get_recent_journals(self, mock_journal_thread):
        # Write journals for past few days
        for i in range(3):
            d = (date.today() - timedelta(days=i)).isoformat()
            storage.save_journal(f"Journal for {d}", for_date=d)

        entries = storage.get_recent_journals(days=7)
        assert len(entries) == 3
        # Each entry is (date_str, content)
        assert entries[0][0] == date.today().isoformat()

    def test_get_recent_journals_empty(self):
        entries = storage.get_recent_journals(days=7)
        assert entries == []

    def test_load_journal_summary_with_json(self, mock_journal_thread):
        summary_json = json.dumps({
            "date": "2026-03-10",
            "dimension_scores": [
                {"dimension": "career", "score": 8},
                {"dimension": "health", "score": 6},
            ],
            "energy_level": "high",
            "mood": "focused",
            "wins": ["Shipped feature"],
            "challenges": ["Missed workout"],
            "patterns_noted": [],
        })
        content = f"# Journal\nGood day.\n\n```json\n{summary_json}\n```\n"
        storage.save_journal(content, for_date="2026-03-10")

        summary = storage.load_journal_summary(for_date="2026-03-10")
        assert summary is not None
        assert summary.date == "2026-03-10"
        assert summary.energy_level == "high"
        assert len(summary.dimension_scores) == 2
        assert summary.wins == ["Shipped feature"]

    def test_load_journal_summary_no_json_block(self, mock_journal_thread):
        storage.save_journal("Plain text journal, no JSON.", for_date="2026-03-11")
        assert storage.load_journal_summary(for_date="2026-03-11") is None

    def test_load_journal_summary_missing_journal(self):
        assert storage.load_journal_summary(for_date="1999-01-01") is None

    def test_save_research(self):
        path = storage.save_research("Machine Learning Basics", "# ML\nContent here.")
        assert path.exists()
        assert "machine-learning-basics" in path.name
        assert date.today().isoformat() in path.name
        assert path.read_text() == "# ML\nContent here."

    def test_save_research_slug_sanitization(self):
        path = storage.save_research("What's the Best!!! Way?", "content")
        # Special chars should be replaced with hyphens
        assert "what-s-the-best-way" in path.name


# ═══════════════════════════════════════════════════════════════════════════════
# 5. projects.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestProjects:
    """project_stats, project plans CRUD."""

    def test_project_stats_no_tasks(self):
        proj = Project(title="Empty project")
        storage.save_project(proj)
        pct, mins_done, mins_tot, budget = storage.project_stats(proj.id)
        assert pct == 0
        assert mins_done == 0
        assert mins_tot == 0
        assert budget == 0.0

    def test_project_stats_with_mixed_tasks(self):
        proj = Project(title="Mixed tasks", budget_cap=5000.0)
        storage.save_project(proj)

        t1 = Task(title="Done task", status=TaskStatus.DONE,
                   project_id=proj.id, energy_cost=5, estimated_minutes=60)
        t2 = Task(title="Todo task", status=TaskStatus.TODO,
                   project_id=proj.id, energy_cost=5, estimated_minutes=30)
        t3 = Task(title="In progress", status=TaskStatus.IN_PROGRESS,
                   project_id=proj.id, energy_cost=10, estimated_minutes=120)
        storage.save_task(t1)
        storage.save_task(t2)
        storage.save_task(t3)

        pct, mins_done, mins_tot, budget = storage.project_stats(proj.id)
        # done_e = 5, total_e = 20, pct = 25
        assert pct == 25
        assert mins_done == 60
        assert mins_tot == 210
        assert budget == 5000.0

    def test_project_stats_all_done(self):
        proj = Project(title="All done")
        storage.save_project(proj)

        t1 = Task(title="Task A", status=TaskStatus.DONE,
                   project_id=proj.id, energy_cost=4, estimated_minutes=30)
        t2 = Task(title="Task B", status=TaskStatus.DONE,
                   project_id=proj.id, energy_cost=6, estimated_minutes=45)
        storage.save_task(t1)
        storage.save_task(t2)

        pct, mins_done, mins_tot, _ = storage.project_stats(proj.id)
        assert pct == 100
        assert mins_done == 75
        assert mins_tot == 75

    def test_project_stats_excludes_habits(self):
        proj = Project(title="With habits")
        storage.save_project(proj)

        habit = Task(title="Daily standup", project_id=proj.id,
                     is_habit=True, status=TaskStatus.DONE, energy_cost=2)
        task = Task(title="Real task", project_id=proj.id,
                    status=TaskStatus.TODO, energy_cost=5, estimated_minutes=60)
        storage.save_task(habit)
        storage.save_task(task)

        pct, mins_done, mins_tot, _ = storage.project_stats(proj.id)
        # Habit excluded; only 1 todo task
        assert pct == 0
        assert mins_tot == 60

    def test_project_stats_with_passed_tasks(self):
        """project_stats accepts an optional _tasks list."""
        proj = Project(title="Passed tasks")
        storage.save_project(proj)

        tasks = [
            Task(title="Done", status=TaskStatus.DONE,
                 project_id=proj.id, energy_cost=3, estimated_minutes=20),
            Task(title="Todo", status=TaskStatus.TODO,
                 project_id=proj.id, energy_cost=7, estimated_minutes=40),
        ]
        pct, mins_done, mins_tot, _ = storage.project_stats(proj.id, _tasks=tasks)
        assert pct == 30
        assert mins_done == 20

    def test_save_and_get_project_plan(self):
        plan = ProjectPlan(
            project_id="proj-001",
            scope_md="Build the MVP",
            success_criteria=["Feature A done", "Tests pass"],
            out_of_scope=["Mobile app"],
            total_budget=10000.0,
            notes="Start with backend",
        )
        storage.save_project_plan(plan)

        loaded = storage.get_project_plan("proj-001")
        assert loaded is not None
        assert loaded.project_id == "proj-001"
        assert loaded.scope_md == "Build the MVP"
        assert len(loaded.success_criteria) == 2
        assert loaded.total_budget == 10000.0

    def test_get_project_plan_missing(self):
        assert storage.get_project_plan("nonexistent") is None

    def test_get_all_project_plans(self):
        plan1 = ProjectPlan(project_id="p1", scope_md="Plan 1")
        plan2 = ProjectPlan(project_id="p2", scope_md="Plan 2")
        storage.save_project_plan(plan1)
        storage.save_project_plan(plan2)

        all_plans = storage.get_all_project_plans()
        assert "p1" in all_plans
        assert "p2" in all_plans
        assert all_plans["p1"].scope_md == "Plan 1"

    def test_save_project_plan_updates_existing(self):
        plan = ProjectPlan(project_id="p-upd", scope_md="v1")
        storage.save_project_plan(plan)

        plan.scope_md = "v2"
        storage.save_project_plan(plan)

        all_plans = storage.get_all_project_plans()
        assert all_plans["p-upd"].scope_md == "v2"
        # Should not duplicate
        raw = json.loads(_paths.PROJECT_PLANS_FILE.read_text())
        matching = [x for x in raw if x["project_id"] == "p-upd"]
        assert len(matching) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 6. values.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestValues:
    """load_values, save_values, migration from constitution.md."""

    def test_load_values_default(self):
        values = storage.load_values()
        assert "prayer" in values
        assert "chapters" in values
        assert "career" in values["chapters"]

    def test_save_and_load_values(self):
        values = {
            "prayer": "Be grateful",
            "chapters": {
                "career": "Build meaningful products",
                "wealth": "Save 50%",
                "health": "Exercise daily",
                "relationships": "Be present",
                "joy": "Read more",
                "learning": "One course per quarter",
            },
        }
        storage.save_values(values)
        loaded = storage.load_values()
        assert loaded["prayer"] == "Be grateful"
        assert loaded["chapters"]["wealth"] == "Save 50%"

    def test_load_values_from_yaml_file(self):
        vals = {"prayer": "Test prayer", "chapters": {"career": "Test career"}}
        _paths.VALUES_FILE.write_text(
            yaml.dump(vals, allow_unicode=True, default_flow_style=False)
        )
        loaded = storage.load_values()
        assert loaded["prayer"] == "Test prayer"
        assert loaded["chapters"]["career"] == "Test career"

    def test_load_values_migration_from_constitution(self):
        """When values.yaml does not exist but constitution.md does, migrate."""
        # Ensure values.yaml does NOT exist
        if _paths.VALUES_FILE.exists():
            _paths.VALUES_FILE.unlink()

        constitution_content = "Work hard. Be kind. Stay curious."
        _paths.CONSTITUTION_FILE.write_text(constitution_content)

        values = storage.load_values()
        assert values["chapters"]["career"] == constitution_content
        # values.yaml should now exist (migration wrote it)
        assert _paths.VALUES_FILE.exists()

    def test_load_values_corrupt_yaml_returns_default(self):
        _paths.VALUES_FILE.write_text(": : : bad yaml [[[")
        values = storage.load_values()
        # Falls through to constitution check, then defaults
        assert "chapters" in values

    def test_save_values_roundtrip(self):
        original = {
            "prayer": "Focus",
            "chapters": {"career": "Ship it", "health": "Run daily"},
        }
        storage.save_values(original)
        loaded = storage.load_values()
        assert loaded == original


# ═══════════════════════════════════════════════════════════════════════════════
# 7. plans.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestPlans:
    """save_plan / load_plan."""

    def test_save_and_load_plan(self):
        plan_data = {
            "date": "2026-03-16",
            "tasks": ["Write tests", "Code review"],
            "focus": "career",
        }
        path = storage.save_plan("daily", plan_data)
        assert path.exists()

        loaded = storage.load_plan("daily")
        assert loaded["date"] == "2026-03-16"
        assert loaded["tasks"] == ["Write tests", "Code review"]

    def test_load_plan_missing_scope(self):
        assert storage.load_plan("nonexistent") == {}

    def test_save_plan_overwrites(self):
        storage.save_plan("weekly", {"version": 1})
        storage.save_plan("weekly", {"version": 2})
        loaded = storage.load_plan("weekly")
        assert loaded["version"] == 2

    def test_different_scopes_independent(self):
        storage.save_plan("daily", {"scope": "daily"})
        storage.save_plan("weekly", {"scope": "weekly"})
        assert storage.load_plan("daily")["scope"] == "daily"
        assert storage.load_plan("weekly")["scope"] == "weekly"


# ═══════════════════════════════════════════════════════════════════════════════
# 8. tasks.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestTasksExtended:
    """get_task_by_id by seq_id, save_tasks batch, get_habits."""

    def test_get_task_by_seq_id(self):
        task = Task(title="Seq ID task")
        storage.save_task(task)  # assigns seq_id T-001
        found = storage.get_task_by_id(task.seq_id)
        assert found is not None
        assert found.id == task.id

    def test_get_task_by_seq_id_case_insensitive(self):
        task = Task(title="Case test")
        storage.save_task(task)
        seq = task.seq_id  # e.g. "T-001"
        found = storage.get_task_by_id(seq.lower())
        assert found is not None
        assert found.id == task.id

    def test_get_task_by_id_not_found(self):
        assert storage.get_task_by_id("nonexistent-id") is None

    def test_save_tasks_batch(self):
        t1 = Task(title="Batch 1", seq_id="T-101")
        t2 = Task(title="Batch 2", seq_id="T-102")
        t3 = Task(title="Batch 3", seq_id="T-103")
        storage.save_tasks([t1, t2, t3])

        all_tasks = storage.get_tasks()
        ids = {t.id for t in all_tasks}
        assert t1.id in ids
        assert t2.id in ids
        assert t3.id in ids

    def test_save_tasks_batch_updates_existing(self):
        task = Task(title="Original")
        storage.save_task(task)

        task.title = "Updated via batch"
        storage.save_tasks([task])

        found = storage.get_task_by_id(task.id)
        assert found.title == "Updated via batch"
        # Should not duplicate
        all_tasks = storage.get_tasks()
        matching = [t for t in all_tasks if t.id == task.id]
        assert len(matching) == 1

    def test_get_habits(self):
        habit = Task(title="Meditate", is_habit=True)
        regular = Task(title="Deploy feature", is_habit=False)
        storage.save_task(habit)
        storage.save_task(regular)

        habits = storage.get_habits()
        assert any(h.id == habit.id for h in habits)
        assert not any(h.id == regular.id for h in habits)

    def test_get_habits_empty(self):
        assert storage.get_habits() == []

    def test_get_tasks_exclude_habits(self):
        habit = Task(title="Habit task", is_habit=True)
        regular = Task(title="Regular task", is_habit=False)
        storage.save_task(habit)
        storage.save_task(regular)

        tasks = storage.get_tasks(include_habits=False)
        assert not any(t.id == habit.id for t in tasks)
        assert any(t.id == regular.id for t in tasks)
