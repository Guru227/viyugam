from __future__ import annotations
from datetime import date, datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator
import uuid


def new_id() -> str:
    return str(uuid.uuid4())[:8]


# ── Enums ──────────────────────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    TODO        = "todo"
    IN_PROGRESS = "in_progress"
    DONE        = "done"
    BACKLOG     = "backlog"

class ProjectStatus(str, Enum):
    ACTIVE    = "active"
    PAUSED    = "paused"
    COMPLETED = "completed"
    ICEBOX    = "icebox"

class Dimension(str, Enum):
    HEALTH        = "health"
    WEALTH        = "wealth"
    CAREER        = "career"
    RELATIONSHIPS = "relationships"
    JOY           = "joy"
    LEARNING      = "learning"

class Recurrence(str, Enum):
    DAILY   = "daily"
    WEEKLY  = "weekly"
    MONTHLY = "monthly"

class ResilienceState(str, Enum):
    FLOW       = "flow"
    DRIFT      = "drift"
    BANKRUPTCY = "bankruptcy"


# ── Core entities ──────────────────────────────────────────────────────────────

class Task(BaseModel):
    id:                 str          = Field(default_factory=new_id)
    title:              str
    status:             TaskStatus   = TaskStatus.TODO
    project_id:         Optional[str] = None
    context:            Optional[str] = None   # at-desk, errand, calls, anywhere
    scheduled_date:     Optional[str] = None   # YYYY-MM-DD
    time_block:         Optional[str] = None   # "09:00-11:00"
    time_period:        Optional[str] = None   # morning, afternoon, evening, night
    estimated_minutes:  int          = 30
    energy_cost:        int          = 5       # 1-10
    financial_cost:     float        = 0.0
    is_habit:           bool         = False
    recurrence:         Optional[Recurrence] = None
    streak:             int          = 0
    last_done:          Optional[str] = None   # YYYY-MM-DD
    dimension:          Optional[Dimension] = None
    is_overdue:         bool         = False
    overdue_count:      int          = 0
    created_at:         str          = Field(default_factory=lambda: datetime.now().isoformat())
    notes:              Optional[str] = None


class Project(BaseModel):
    id:           str           = Field(default_factory=new_id)
    title:        str
    description:  Optional[str] = None
    status:       ProjectStatus = ProjectStatus.ACTIVE
    dimension:    Optional[Dimension] = None
    goal_id:      Optional[str] = None
    deadline:     Optional[str] = None         # YYYY-MM-DD
    budget_cap:   float         = 0.0
    energy_cap:   int           = 0
    created_at:   str           = Field(default_factory=lambda: datetime.now().isoformat())


class Goal(BaseModel):
    id:          str        = Field(default_factory=new_id)
    title:       str
    description: Optional[str] = None
    dimension:   Dimension
    is_active:   bool       = True
    created_at:  str        = Field(default_factory=lambda: datetime.now().isoformat())


class InboxItem(BaseModel):
    id:           str  = Field(default_factory=new_id)
    content:      str
    source:       str  = "cli"
    is_processed: bool = False
    created_at:   str  = Field(default_factory=lambda: datetime.now().isoformat())


class SomedayItem(BaseModel):
    id:              str            = Field(default_factory=new_id)
    proposal:        str
    debate_transcript: list[dict]   = []
    consensus:       Optional[str]  = None
    deferred_reason: Optional[str]  = None
    revisit_after:   Optional[str]  = None  # YYYY-MM-DD
    created_at:      str            = Field(default_factory=lambda: datetime.now().isoformat())


class DimensionScore(BaseModel):
    dimension: Dimension
    score:     int            # 1-10, derived from journal
    note:      Optional[str]  = None


class JournalSummary(BaseModel):
    date:             str
    dimension_scores: list[DimensionScore] = []
    energy_level:     Optional[str]  = None   # low, medium, high
    mood:             Optional[str]  = None
    wins:             list[str]      = []
    challenges:       list[str]      = []
    patterns_noted:   list[str]      = []
    coach_note:       Optional[str]  = None


# ── New models ─────────────────────────────────────────────────────────────────

class SlowBurn(BaseModel):
    id:            str           = Field(default_factory=new_id)
    title:         str
    dimension:     Optional[Dimension] = None
    notes:         Optional[str] = None
    last_chipped:  Optional[str] = None   # YYYY-MM-DD
    created_at:    str           = Field(default_factory=lambda: datetime.now().isoformat())

class Milestone(BaseModel):
    id:         str           = Field(default_factory=new_id)
    title:      str
    goal_id:    Optional[str] = None
    project_id: Optional[str] = None
    due_date:   Optional[str] = None    # YYYY-MM-DD
    is_done:    bool          = False
    notes:      Optional[str] = None
    created_at: str           = Field(default_factory=lambda: datetime.now().isoformat())

class Budget(BaseModel):
    id:           str      = Field(default_factory=new_id)
    name:         str
    total_limit:  float
    spent:        float    = 0.0
    period_start: str                    # YYYY-MM-DD
    period_end:   str                    # YYYY-MM-DD
    dimension:    Optional[Dimension] = None
    created_at:   str      = Field(default_factory=lambda: datetime.now().isoformat())

class Transaction(BaseModel):
    id:          str      = Field(default_factory=new_id)
    amount:      float
    category:    str
    description: str
    budget_id:   Optional[str] = None
    task_id:     Optional[str] = None
    project_id:  Optional[str] = None
    occurred_at: str      = Field(default_factory=lambda: datetime.now().isoformat())

class Decision(BaseModel):
    id:             str            = Field(default_factory=new_id)
    proposal:       str
    outcome:        str            # approved / rejected / conditional
    reasoning:      str
    voices:         list[dict]     = []
    condition:      Optional[str]  = None
    created_at:     str            = Field(default_factory=lambda: datetime.now().isoformat())
    revisited_at:   Optional[str]  = None
    actual_outcome: Optional[str]  = None   # filled in during review

class ActualRecord(BaseModel):
    id:              str           = Field(default_factory=new_id)
    task_id:         str
    task_title:      str
    planned_minutes: int
    actual_minutes:  Optional[int] = None
    date:            str                     # YYYY-MM-DD
    completed:       bool          = True
    created_at:      str           = Field(default_factory=lambda: datetime.now().isoformat())


class KeyResult(BaseModel):
    id:      str  = Field(default_factory=new_id)
    text:    str
    target:  Optional[str] = None    # e.g. "complete 3 projects"
    is_done: bool = False

class OKR(BaseModel):
    id:          str  = Field(default_factory=new_id)
    quarter:     str                     # e.g. "2026-Q1"
    objective:   str
    dimension:   Optional[Dimension] = None
    key_results: list[KeyResult]     = []
    is_active:   bool = True
    created_at:  str  = Field(default_factory=lambda: datetime.now().isoformat())


# ── Config (loaded from config.yaml) ──────────────────────────────────────────

class SeasonConfig(BaseModel):
    name:      str
    focus:     Dimension
    secondary: Optional[Dimension] = None
    until:     Optional[str]       = None  # YYYY-MM-DD


class WorkSchedule(BaseModel):
    start:       str       = "09:00"
    end:         str       = "17:30"
    office_days: list[str] = ["mon", "tue", "wed", "thu", "fri"]
    wfh_days:    list[str] = []   # days that are WFH (not in office_days)


class CalendarEntryType(str, Enum):
    EVENT   = "event"
    BLOCK   = "block"
    WORKOUT = "workout"
    MEETING = "meeting"


class CalendarEntry(BaseModel):
    id:         str                   = Field(default_factory=new_id)
    title:      str
    entry_type: CalendarEntryType     = CalendarEntryType.EVENT
    recurs_on:  list[str]             = []      # e.g. ["mon","wed"] — weekly recurring
    date:       Optional[str]         = None    # YYYY-MM-DD — one-off
    start_time: Optional[str]         = None    # HH:MM
    end_time:   Optional[str]         = None
    notes:      Optional[str]         = None
    created_at: str                   = Field(default_factory=lambda: datetime.now().isoformat())

    @model_validator(mode="after")
    def check_recurs_or_date(self) -> "CalendarEntry":
        if not self.recurs_on and not self.date:
            raise ValueError("Must set recurs_on (recurring) or date (one-off)")
        return self


class ViyugamConfig(BaseModel):
    user_name:       str            = "friend"
    season:          Optional[SeasonConfig] = None
    work_schedule:   Optional[WorkSchedule] = None
    dimensions:      list[str]      = [d.value for d in Dimension]
    work_hours_cap:  int            = 8
    day_start:       int            = 10     # hour (24h) after which plan = mid-day mode
    currency:        str            = "₹"
    timezone:        str            = "Asia/Kolkata"
    api_key:         Optional[str]  = None   # fallback if not in env
    constitution_exists: bool = False   # flag so agents know to load it


# ── System state (persisted in data/state.json) ───────────────────────────────

class SystemState(BaseModel):
    resilience:       ResilienceState = ResilienceState.FLOW
    last_active:      Optional[str]   = None   # ISO datetime
    last_log:         Optional[str]   = None   # YYYY-MM-DD
    last_plan:        Optional[str]   = None   # YYYY-MM-DD
    last_review:      Optional[str]   = None   # YYYY-MM-DD
    last_think:       Optional[str]   = None   # YYYY-MM-DD
    current_streak:   int             = 0
    actual_season:    Optional[str]   = None   # derived, updated by plan/review
