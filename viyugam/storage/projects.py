"""storage/projects.py — Project CRUD + project plans."""
from __future__ import annotations

from typing import Optional

from viyugam.models import Project, ProjectPlan, TaskStatus

from . import _paths


def get_projects(status: Optional[str] = None) -> list[Project]:
    raw = _paths._load("projects")
    projects = [Project(**p) for p in raw]
    if status:
        projects = [p for p in projects if p.status.value == status]
    return projects


def save_project(project: Project) -> None:
    if not project.seq_id:
        project.seq_id = _paths._next_id("P")
    raw = _paths._load("projects")
    existing = [p for p in raw if p["id"] != project.id]
    existing.append(project.model_dump())
    _paths._save("projects", existing)


def project_stats(project_id: str, _tasks: list | None = None) -> tuple[int, int, int, float]:
    """Returns (pct_done, mins_done, mins_total, budget_cap)."""
    if _tasks is None:
        from .tasks import get_tasks
        _tasks = get_tasks()

    tasks = [t for t in _tasks if t.project_id == project_id and not t.is_habit]
    if not tasks:
        return 0, 0, 0, 0.0
    total_e   = sum(t.energy_cost for t in tasks) or 1
    done_e    = sum(t.energy_cost for t in tasks if t.status == TaskStatus.DONE)
    mins_tot  = sum(t.estimated_minutes for t in tasks)
    mins_done = sum(t.estimated_minutes for t in tasks if t.status == TaskStatus.DONE)
    pct       = int(done_e / total_e * 100)

    proj = next((p for p in get_projects() if p.id == project_id), None)
    budget = proj.budget_cap if proj else 0.0
    return pct, mins_done, mins_tot, budget


# ── Project plans ─────────────────────────────────────────────────────────────

def get_all_project_plans() -> dict[str, ProjectPlan]:
    raw = _paths._load_json(_paths.PROJECT_PLANS_FILE)
    return {item["project_id"]: ProjectPlan(**item) for item in raw if "project_id" in item}


def get_project_plan(project_id: str) -> ProjectPlan | None:
    raw = _paths._load_json(_paths.PROJECT_PLANS_FILE)
    for item in raw:
        if item.get("project_id") == project_id:
            return ProjectPlan(**item)
    return None


def save_project_plan(plan: ProjectPlan) -> None:
    from datetime import datetime as _dt

    raw = _paths._load_json(_paths.PROJECT_PLANS_FILE)
    raw = [x for x in raw if x.get("project_id") != plan.project_id]
    plan.updated_at = _dt.now().isoformat()
    raw.append(plan.model_dump())
    _paths._save_json(_paths.PROJECT_PLANS_FILE, raw)
