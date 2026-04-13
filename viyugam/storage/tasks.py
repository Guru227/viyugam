"""storage/tasks.py — Task CRUD."""
from __future__ import annotations

from typing import Optional

from viyugam.models import Task, TaskStatus

from . import _paths


def get_tasks(
    status: Optional[str] = None,
    scheduled_date: Optional[str] = None,
    include_habits: bool = True,
) -> list[Task]:
    raw = _paths._load("tasks")
    tasks = [Task(**t) for t in raw]
    if status:
        tasks = [t for t in tasks if t.status.value == status]
    if scheduled_date:
        tasks = [t for t in tasks if t.scheduled_date == scheduled_date]
    if not include_habits:
        tasks = [t for t in tasks if not t.is_habit]
    return tasks


def get_task_by_id(task_id: str) -> Optional[Task]:
    for t in get_tasks():
        if t.id == task_id or t.id.startswith(task_id):
            return t
        if t.seq_id and (t.seq_id == task_id or t.seq_id.upper() == task_id.upper()):
            return t
    return None


def save_task(task: Task) -> None:
    if not task.seq_id:
        task.seq_id = _paths._next_id("T")
    raw = _paths._load("tasks")
    existing = [t for t in raw if t["id"] != task.id]
    existing.append(task.model_dump())
    _paths._save("tasks", existing)


def save_tasks(tasks: list[Task]) -> None:
    raw = _paths._load("tasks")
    updated_ids = {t.id for t in tasks}
    kept = [t for t in raw if t["id"] not in updated_ids]
    kept.extend([t.model_dump() for t in tasks])
    _paths._save("tasks", kept)


def get_habits() -> list[Task]:
    return [t for t in get_tasks() if t.is_habit]


def _check_unblocked(completed_task_id: str) -> list[str]:
    """Find tasks that were only blocked by the completed task and are now unblocked."""
    all_tasks = get_tasks(include_habits=False)
    unblocked = []
    for t in all_tasks:
        if t.status == TaskStatus.DONE:
            continue
        completed_was_blocking = any(
            other.id == completed_task_id and t.id in other.blocks
            for other in all_tasks
        )
        if not completed_was_blocking:
            continue
        still_blocked = any(
            other.id != completed_task_id
            and other.status != TaskStatus.DONE
            and t.id in other.blocks
            for other in all_tasks
        )
        if not still_blocked:
            unblocked.append(t.title)
    return unblocked
