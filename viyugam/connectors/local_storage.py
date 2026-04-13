"""connectors/local_storage.py — Wraps storage/ modules behind a connector interface.

Returns plain dicts (JSON-serializable) for tool results.
This creates the seam for Google Workspace sync (Phase 2 will subclass/compose).
"""
from __future__ import annotations

from typing import Optional


class LocalStorageConnector:
    """Connector backed by local file storage (~/.viyugam/)."""

    # ── Tasks ─────────────────────────────────────────────────────────────

    def get_tasks(
        self,
        status: Optional[str] = None,
        scheduled_date: Optional[str] = None,
    ) -> dict:
        from viyugam.storage import get_tasks
        tasks = get_tasks(status=status, scheduled_date=scheduled_date, include_habits=False)
        return {
            "tasks": [t.model_dump() for t in tasks],
            "count": len(tasks),
        }

    def get_task_by_id(self, task_id: str) -> dict:
        from viyugam.storage import get_task_by_id
        task = get_task_by_id(task_id)
        if task is None:
            return {"error": f"Task not found: {task_id}"}
        return task.model_dump()

    def save_task(self, task_data: dict) -> dict:
        from viyugam.models import Dimension, Task
        from viyugam.storage import save_task

        task = Task(
            title=task_data["title"],
            dimension=Dimension(task_data["dimension"]) if task_data.get("dimension") else None,
            scheduled_date=task_data.get("scheduled_date"),
            estimated_minutes=task_data.get("estimated_minutes", 30),
            project_id=task_data.get("project_id"),
            aligns_to=task_data.get("aligns_to", []),
        )
        save_task(task)
        return {"status": "saved", "task_id": task.id, "seq_id": task.seq_id}

    def mark_task_done(self, task_id: str) -> dict:
        from viyugam.storage import mark_entity_done
        result = mark_entity_done(task_id)
        if result:
            return {"status": "done", "message": result}
        return {"error": f"Not found: {task_id}"}

    # ── Projects ──────────────────────────────────────────────────────────

    def get_projects(self, status: Optional[str] = None) -> dict:
        from viyugam.storage import get_projects
        projects = get_projects(status=status)
        return {
            "projects": [p.model_dump() for p in projects],
            "count": len(projects),
        }

    def save_project(self, project_data: dict) -> dict:
        from viyugam.models import Dimension, Project
        from viyugam.storage import save_project

        project = Project(
            title=project_data["title"],
            dimension=Dimension(project_data["dimension"]) if project_data.get("dimension") else None,
            budget_cap=project_data.get("budget_cap", 0.0),
        )
        save_project(project)
        return {"status": "saved", "project_id": project.id, "seq_id": project.seq_id}

    # ── Goals ─────────────────────────────────────────────────────────────

    def get_goals(self, active_only: bool = True) -> dict:
        from viyugam.storage import get_goals
        goals = get_goals(active_only=active_only)
        return {
            "goals": [g.model_dump() for g in goals],
            "count": len(goals),
        }

    def save_goal(self, goal_data: dict) -> dict:
        from viyugam.models import Dimension, Goal
        from viyugam.storage import save_goal

        goal = Goal(
            title=goal_data["title"],
            dimension=Dimension(goal_data["dimension"]),
        )
        save_goal(goal)
        return {"status": "saved", "goal_id": goal.id, "seq_id": goal.seq_id}

    def delete_goal(self, goal_id: str) -> dict:
        from viyugam.storage import delete_goal
        ok = delete_goal(goal_id)
        return {"status": "deleted" if ok else "not_found"}

    # ── Triage ────────────────────────────────────────────────────────────

    def get_triage(self, unprocessed_only: bool = True) -> dict:
        from viyugam.storage import get_triage
        items = get_triage(unprocessed_only=unprocessed_only)
        return {
            "items": [i.model_dump() for i in items],
            "count": len(items),
        }

    def append_triage(self, content: str, source: str = "cli") -> dict:
        from viyugam.storage import append_triage
        item = append_triage(content, source)
        return {"status": "captured", "id": item.id}

    def mark_triage_processed(self, item_ids: list[str]) -> dict:
        from viyugam.storage import mark_triage_processed
        mark_triage_processed(item_ids)
        return {"status": "processed", "count": len(item_ids)}

    # ── Journal ───────────────────────────────────────────────────────────

    def get_recent_journals(self, days: int = 14) -> dict:
        from viyugam.storage import get_recent_journals
        entries = get_recent_journals(days=days)
        return {
            "entries": [{"date": d, "content": c[:500]} for d, c in entries],
            "count": len(entries),
        }

    def load_journal_summary(self, for_date: Optional[str] = None) -> dict:
        from viyugam.storage import load_journal_summary
        summary = load_journal_summary(for_date)
        if summary is None:
            return {"summary": None}
        return {"summary": summary.model_dump()}

    def save_journal(self, content: str, for_date: Optional[str] = None) -> dict:
        from viyugam.storage import save_journal
        path = save_journal(content, for_date)
        return {"status": "saved", "path": str(path)}

    # ── Finance ───────────────────────────────────────────────────────────

    def get_budget_summary(self) -> dict:
        from viyugam.storage import get_budget_summary
        return {"budgets": get_budget_summary()}

    def get_monthly_cashflow(self, month: str) -> dict:
        from viyugam.storage import get_monthly_cashflow
        return get_monthly_cashflow(month)

    def get_recurring_items(self, active_only: bool = True) -> dict:
        from viyugam.storage import get_recurring_items
        items = get_recurring_items(active_only=active_only)
        return {"items": [i.model_dump() for i in items], "count": len(items)}

    def get_transactions(self, budget_id: Optional[str] = None) -> dict:
        from viyugam.storage import get_transactions
        txns = get_transactions(budget_id=budget_id)
        return {"transactions": [t.model_dump() for t in txns], "count": len(txns)}

    def save_transaction(self, tx_data: dict) -> dict:
        from viyugam.models import Transaction, TxType
        from viyugam.storage import save_transaction

        tx = Transaction(
            amount=tx_data["amount"],
            category=tx_data["category"],
            description=tx_data["description"],
            tx_type=TxType(tx_data.get("tx_type", "expense")),
            budget_id=tx_data.get("budget_id"),
        )
        save_transaction(tx)
        return {"status": "saved", "transaction_id": tx.id}

    # ── Calendar ──────────────────────────────────────────────────────────

    def get_calendar_events(self, date_str: str) -> dict:
        from viyugam.storage import get_calendar_entries
        entries = get_calendar_entries(date_str)
        return {"events": [e.model_dump() for e in entries], "count": len(entries)}

    # ── Values ────────────────────────────────────────────────────────────

    def load_values(self) -> dict:
        from viyugam.storage import load_values
        return load_values()

    # ── GPS ────────────────────────────────────────────────────────────────

    def get_priority_context(self) -> dict:
        try:
            from viyugam.priority import get_context
            ctx = get_context()
            return ctx.model_dump() if hasattr(ctx, "model_dump") else {"error": "no context"}
        except Exception as e:
            return {"error": str(e)}

    # ── Notes ─────────────────────────────────────────────────────────────

    def get_notes(self) -> dict:
        from viyugam.storage import get_notes
        notes = get_notes()
        return {"notes": [n.model_dump() for n in notes], "count": len(notes)}

    def save_note(self, note_data: dict) -> dict:
        from viyugam.models import Note
        from viyugam.storage import save_note

        note = Note(title=note_data["title"], content=note_data.get("content", ""))
        save_note(note)
        return {"status": "saved", "note_id": note.id, "seq_id": note.seq_id}

    # ── Decisions ─────────────────────────────────────────────────────────

    def get_decisions(self) -> dict:
        from viyugam.storage import get_decisions
        decisions = get_decisions()
        return {"decisions": [d.model_dump() for d in decisions], "count": len(decisions)}

    def save_decision(self, decision_data: dict) -> dict:
        from viyugam.models import Decision
        from viyugam.storage import save_decision

        decision = Decision(
            proposal=decision_data["proposal"],
            outcome=decision_data["outcome"],
            reasoning=decision_data["reasoning"],
        )
        save_decision(decision)
        return {"status": "saved", "decision_id": decision.id}

    # ── System State ──────────────────────────────────────────────────────

    def get_system_state(self) -> dict:
        from viyugam.storage import load_state
        state = load_state()
        return state.model_dump()

    def save_system_state(self, state_data: dict) -> dict:
        from viyugam.storage import load_state, save_state
        state = load_state()
        for key, val in state_data.items():
            if hasattr(state, key) and val is not None:
                setattr(state, key, val)
        save_state(state)
        return {"status": "saved"}

    # ── Memory ────────────────────────────────────────────────────────────

    def get_memory_context(self, max_entries: int = 7) -> dict:
        from viyugam.storage import get_memory_context
        ctx = get_memory_context(max_entries=max_entries)
        return {"context": ctx}
