"""
dashboard.py — Full-screen split dashboard for Viyugam.

Layout:
  Left (60%)  — navigable data panels: Strategic → Tactical → Daily → Research
  Right (40%) — persistent chat window with inline AI output

Keys:
  ← →         switch left panel
  ↑ ↓         scroll left panel
  Ctrl+↑/↓    scroll chat (right panel)
  f           toggle focus mode  (All ↔ Work)
  Esc / C-d   close
  Enter       dispatch query (runs in background, output appears in chat)
"""
from __future__ import annotations

import argparse
import contextlib
import io
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import ANSI, FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    ConditionalContainer, HSplit, Layout, VSplit, Window,
)
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import D
from prompt_toolkit.styles import Style
from rich.console import Console as RichConsole

import viyugam.storage as storage

# ── Constants ──────────────────────────────────────────────────────────────────

PANEL_SETS: dict = {
    "execute":  ["GPS", "Strategic", "Tactical", "Daily", "Research", "Review"],
    "project":  ["Scope",     "Tasks",    "Context"],
    "goal":     ["OKRs",      "Projects", "Alignment"],
    "plan":     ["Strategy"],
    "review":   ["Session",   "Activity", "Captures"],
    "triage":   ["Inbox",     "Done"],
}
PANELS = PANEL_SETS["execute"]  # backwards compat alias
WORK_DIMS    = {"career", "learning", "wealth"}
APPROVE_KW   = {"approve", "looks good", "lgtm", "confirmed", "yes", "ok", "okay", "ship it"}
FOCUS_CYCLE  = ["all", "career", "wealth", "health", "relationships", "joy", "learning"]

# ── Slash command hint table ────────────────────────────────────────────────────
# Each entry: (command, args_hint, description)
SLASH_HINTS: list[tuple[str, str, str]] = [
    ("plan",     "[day|week|quarter]",    "start a planning session"),
    ("plan",     "P-NNN",                 "open project planning boardroom"),
    ("plan",     "G-NNN",                 "open goal planning boardroom"),
    ("review",   "[day|week|quarter]",    "start a review session"),
    ("triage",   "",                      "process inbox items"),
    ("log",      "<note>",               "capture a thought, task, or expense"),
    ("research", "<topic>",               "run background research"),
    ("clear",    "",                      "clear chat history"),
    ("exit",     "",                      "exit current mode or quit"),
]

# ── Style ──────────────────────────────────────────────────────────────────────

STYLE = Style.from_dict({
    # ── Header bar ──
    "header":           "bg:#1e2030 #b0b8d0",
    "header.title":     "bg:#1e2030 #ffffff bold",
    "header.mode.all":  "bg:#1e2030 #44dd88 bold",
    "header.mode.work": "bg:#1e2030 #ffbb55 bold",

    # ── Tab bar ──
    "tab":              "bg:#161825 #8888bb",
    "tab.active":       "bg:#161825 #44ddff bold",
    "tab.sep":          "bg:#161825 #3a3a55",

    # ── Structural ──
    "sep":              "#3a3a55",
    "div":              "#3a3a55",

    # ── Content ──
    "label":            "#aaaaee bold",
    "accent":           "#44ddff",
    "done":             "#66dd99",
    "todo":             "#e8eaff",
    "overdue":          "#ff7766",
    "dim":              "#7a7a99",
    "warn":             "#ffbb55",
    "bar.on":           "#4499ff",
    "bar.off":          "#2a2a44",

    # ── Chat ──
    "chat.header":      "bg:#1e2030 #9090b8",
    "chat.user":        "#44ddff bold",
    "chat.system":      "#7a7a99 italic",
    "chat.section":     "#a0c4ff bold",
    "chat.spinner":     "#ffbb55",

    # ── Plan proposal priorities ──
    "plan.p1":          "#ff6b6b bold",
    "plan.p2":          "#ffb347",
    "plan.p3":          "#ffd700",
    "plan.defer":       "#7a7a99",

    # ── Canvas diff ──
    "canvas.add":       "#22c55e",
    "canvas.del":       "#f87171",
    "canvas.ctx":       "#7a7a99",

    # ── Slash hints ──
    "hint.border":      "bg:#161825 #2a2a44",
    "hint.cmd":         "bg:#161825 #44ddff bold",
    "hint.args":        "bg:#161825 #6060a0",
    "hint.desc":        "bg:#161825 #4a4a70",
    "hint.match":       "bg:#1a1e38 #44ddff bold",
    "hint.match.args":  "bg:#1a1e38 #7a7acc",
    "hint.match.desc":  "bg:#1a1e38 #8080b0",

    # ── Input ──
    "toolbar":          "bg:#161825 #606080",
    "toolbar.insert":   "bg:#161825 #44ddff bold",
    "prompt":           "#44ddff bold",
    "prompt.normal":    "#3a3a55",
    "mode.normal":      "bg:#161825 #3a3a55",
    "mode.insert":      "bg:#161825 #44ddff bold",
    "input.line":       "bg:#161825 #e8eaff",
})

# ── State ──────────────────────────────────────────────────────────────────────

_WELCOME_HINTS = """\
  Just type naturally — no commands needed.

  \x1b[96mPlan & tasks\x1b[0m
    "plan my day"
    "finished the report"
    "add task: call dentist tomorrow"

  \x1b[96mLog & reflect\x1b[0m
    "spent 2000 on groceries"
    "got salary 80k"
    "log: had a great workout"

  \x1b[96mDecide & review\x1b[0m
    "should I take the contract?"
    "weekly review"
    "research cloud storage options"

  \x1b[96mNavigate\x1b[0m
    ← →  switch panels
    ↑ ↓  scroll panel
    f    toggle Work / All mode
    Esc  exit
"""


@dataclass
class _State:
    panel:        int        = 0          # 0=GPS 1=strategic 2=tactical 3=daily 4=research 5=review
    scroll_l:     list       = field(default_factory=lambda: [0, 0, 0, 0, 0, 0])
    scroll_r:     int        = 0
    focus_mode:   str        = "all"      # "all" | "work"
    staging:      bool       = False      # plan staged, awaiting approval
    mode:         str        = "normal"   # "normal" | "insert"
    scroll_focus: str        = "left"     # "left" | "right" — which pane ↑↓ scrolls
    dirty:        bool       = False      # cleared panel cache when True
    chat:        list       = field(default_factory=lambda: [
        {"role": "assistant", "ansi": _WELCOME_HINTS},
    ])
    research:       list       = field(default_factory=list)
    running:        bool       = False
    tick:           int        = 0          # incremented by ticker thread
    active_session: Optional[dict] = None  # review / plan session in progress
    ui_mode:        str        = "execute"   # "execute"|"project"|"goal"|"plan"|"review"|"triage"
    ui_mode_arg:    str | None = None        # project_id / goal_id / cadence depending on mode
    pending_exit:   bool       = False       # True when /exit typed mid-session


# ── Focus filter ───────────────────────────────────────────────────────────────

def _visible(dimension, focus_mode: str) -> bool:
    if focus_mode == "all" or dimension is None:
        return True
    d = dimension.value if hasattr(dimension, "value") else str(dimension)
    if focus_mode == "work":
        return d in WORK_DIMS
    return d == focus_mode


# ── Project completion ─────────────────────────────────────────────────────────

def _project_stats(project_id: str) -> tuple[int, int, int, float]:
    """Returns (pct_done, mins_done, mins_total, budget_cap).
    Delegates to centralized storage.project_stats()."""
    try:
        return storage.project_stats(project_id)
    except Exception:
        return 0, 0, 0, 0.0


def _pct_bar(pct: int, width: int = 12) -> list[tuple[str, str]]:
    filled = int(pct / 100 * width)
    return [
        ("class:bar.on",  "█" * filled),
        ("class:bar.off", "░" * (width - filled)),
    ]


# ── Token helpers ──────────────────────────────────────────────────────────────

def _t(style: str, text: str) -> tuple[str, str]:
    return (f"class:{style}", text)


def _blank() -> list:
    return []


def _div(width: int = 44) -> list:
    return [_t("sep", "  " + "─" * width)]


# ── Shared panel section renderers ─────────────────────────────────────────────

def _section_finance(L, B, show_categories: bool = False, compact: bool = False) -> None:
    """Render monthly finance summary into a panel using caller's L/B helpers."""
    try:
        month_str = date.today().strftime("%Y-%m")
        cf = storage.get_monthly_cashflow(month_str)
        if cf.get("income") or cf.get("expenses"):
            L(_t("label", f"  FINANCE  ({month_str})"))
            if cf["income"]:
                if compact:
                    L(_t("done", f"  \u2191 Income   \u20b9{cf['income']:>10,.0f}"))
                else:
                    L(_t("done", f"  Income:   \u20b9{cf['income']:>10,.0f}"))
            if compact:
                L(_t("dim",   f"  \u2193 Expenses \u20b9{cf['expenses']:>10,.0f}"))
                net_sty = "done" if cf["net"] >= 0 else "overdue"
                L(_t(net_sty, f"  = Net      \u20b9{cf['net']:>10,.0f}"))
            else:
                L(_t("dim",   f"  Expenses: \u20b9{cf['expenses']:>10,.0f}"))
                net_sty = "done" if cf["net"] >= 0 else "overdue"
                L(_t(net_sty, f"  Net:      \u20b9{cf['net']:>10,.0f}"))
            if show_categories:
                top_cats = sorted(cf.get("by_category", {}).items(), key=lambda x: -x[1])[:3]
                for cat, amt in top_cats:
                    L(_t("dim", f"    {cat:<16}  \u20b9{amt:>8,.0f}"))
            B()
    except Exception:
        pass


def _section_calendar(L, B, start_date, end_date, label: str,
                      max_events: int = 8, title_width: int = 32) -> None:
    """Render calendar events (date-first format) into a panel using caller's L/B helpers."""
    try:
        cal_events = storage.get_ics_events_for_period(start_date, end_date)
        if cal_events:
            L(_t("label", f"  CALENDAR  ({label})"))
            for ev in cal_events[:max_events]:
                time_str = f"  {ev['start_time']}" if ev.get("start_time") else ""
                L(_t("dim", f"  {ev['date']}  {ev['title'][:title_width]}{time_str}"))
            B()
    except Exception:
        pass


# ── Panel: GPS ─────────────────────────────────────────────────────────────────

def _build_gps(focus: str) -> list[list]:
    """GPS panel -- one directive, nudges, goal trajectories, patterns.
    All data from priority.get_context() -- no Claude calls, instant render."""
    lines: list[list] = []

    def L(*toks): lines.append(list(toks))
    def B():      lines.append(_blank())

    try:
        from viyugam.priority import get_context

        ctx = get_context()

        # -- NOW: directive task --
        L(_t("label", "  NOW"))
        lines.append(_div())
        if ctx.directive_task:
            dt = ctx.directive_task
            seq = dt.get("seq_id") or ""
            title = dt.get("title", "")
            L(_t("accent", f"  {title}"))
            if seq:
                L(_t("dim", f"  [{seq}]"))

            # Project & Goal context
            proj_str = ""
            if dt.get("project_id"):
                projs = storage.get_projects()
                proj = next((p for p in projs if p.id == dt["project_id"]), None)
                if proj:
                    proj_str = f"Project: {proj.seq_id or proj.title[:20]}"
            goal_str = ""
            if dt.get("aligns_to"):
                goals = storage.get_goals(active_only=False)
                for gid in dt["aligns_to"][:2]:
                    g = next((gg for gg in goals if gg.id == gid), None)
                    if g:
                        goal_str += f"  Goal: {g.seq_id or g.title[:20]}"
            if proj_str or goal_str:
                L(_t("dim", f"  {proj_str}{goal_str}"))

            # Why this task
            if ctx.why_bottleneck:
                L(_t("dim", f"  Why: {ctx.why_bottleneck}"))

            # Unblocks
            if ctx.unblocks:
                L(_t("dim", f"  Unblocks: {', '.join(ctx.unblocks[:3])}"))

            # Energy + time + due
            energy = dt.get("energy_cost", 5)
            mins = dt.get("estimated_minutes", 30)
            due = dt.get("due") or dt.get("scheduled_date") or ""
            info = f"  Energy: {energy}/10  ~{mins}m"
            if due:
                info += f"  Due: {due}"
            L(_t("dim", info))
        else:
            L(_t("dim", "  No active tasks. Capture something to get started."))
        B()

        # -- NUDGES --
        if ctx.nudges:
            L(_t("label", "  NUDGES"))
            lines.append(_div())
            for n in ctx.nudges[:6]:
                if n.severity == "critical":
                    marker, sty = "!", "overdue"
                elif n.severity == "warn":
                    marker, sty = "!", "warn"
                else:
                    marker, sty = ".", "dim"
                L(_t(sty, f"  {marker} {n.message}"))
            B()

        # -- GOALS --
        if ctx.goal_trajectories:
            L(_t("label", "  GOALS"))
            lines.append(_div())
            for gt in ctx.goal_trajectories:
                dim_str = gt.get("dimension")
                if focus != "all" and dim_str is not None:
                    if focus == "work" and dim_str not in WORK_DIMS:
                        continue
                    elif focus != "work" and dim_str != focus:
                        continue
                pct = gt.get("progress_pct", 0)
                bar = _pct_bar(int(pct), width=10)
                seq = gt.get("seq_id") or ""
                title = gt.get("title", "")[:24]
                traj = gt.get("trajectory", "")
                traj_val = traj.value if hasattr(traj, "value") else str(traj)
                arrow = {"on_track": "+", "at_risk": "~", "off_track": "-"}.get(traj_val, " ")
                row = [_t("dim", f"  {seq:<6} {title:<24} ")]
                row.extend(bar)
                row.append(_t("dim", f" {pct:>5.0f}%  {arrow}"))
                lines.append(row)
            B()

        # -- PATTERNS --
        try:
            patterns = storage.get_patterns(precipitated_only=True)
            if patterns:
                L(_t("label", "  PATTERNS"))
                lines.append(_div())
                for p in patterns[:4]:
                    L(_t("dim", f"  . {p.pattern}"))
                B()
        except Exception:
            pass

    except Exception as e:
        lines.append([_t("overdue", f"  GPS error: {e}")])

    return lines


# ── Panel: Strategic ───────────────────────────────────────────────────────────

def _build_strategic(focus: str) -> list[list]:
    lines: list[list] = []

    def L(*toks): lines.append(list(toks))
    def B():      lines.append(_blank())

    try:
        config     = storage.load_config()
        slow_burns = storage.get_slow_burns()
        goals      = storage.get_goals(active_only=False)
        state      = storage.load_state()

        # ── Prayer (from values.yaml — shown at top) ──
        values = storage.load_values()
        prayer = values.get("prayer", "")
        if prayer:
            for line in prayer.strip().splitlines()[:4]:
                if line.strip():
                    L(_t("accent", f"  {line}"))
            lines.append(_div())
            B()

        # ── Season ──
        if config.season:
            s   = config.season
            sec = f"  ·  {s.secondary.value}" if s.secondary else ""
            until = f"  until {s.until}" if s.until else ""
            L(_t("accent", f"  Season: {s.name}{until}"))
            L(_t("dim",    f"  Focus: {s.focus.value}{sec}"))
        else:
            L(_t("warn", "  No season — run 'setup'"))

        # Days remaining in current quarter
        today_d = date.today()
        q_end = storage.period_end("quarterly", today_d)
        days_left = (q_end - today_d).days
        L(_t("dim", f"  Quarter ends in {days_left} days ({q_end.isoformat()})"))
        lines.append(_div())
        B()

        # ── Season weights from plans/season_weights.json ──
        season_weights_path = storage.PLANS / "season_weights.json"
        if season_weights_path.exists():
            try:
                import json as _json
                weights = _json.loads(season_weights_path.read_text())
                if weights:
                    L(_t("label", "  SEASON WEIGHTS"))
                    for dim, pct in list(weights.items())[:6]:
                        bar = _pct_bar(int(pct), width=10)
                        row = [_t("dim", f"  {dim:<12} ")]
                        row.extend(bar)
                        row.append(_t("dim", f"  {pct}%"))
                        lines.append(row)
                    B()
            except Exception:
                pass

        # ── Dimension bars ──
        L(_t("label", "  DIMENSIONS  (14-day avg, 0–10)"))
        scores = storage.get_avg_dimension_scores(days=14)
        if scores:
            for s in sorted(scores, key=lambda x: -x["score"]):
                bar = _pct_bar(int(s["score"] * 10), width=14)
                row = [_t("dim", f"  {s['dimension']:<12} ")]
                row.extend(bar)
                row.append(_t("dim", f"  {s['score']:.1f}"))
                lines.append(row)
        else:
            # Fallback: task count per dimension
            tasks  = storage.get_tasks()
            counts: dict[str, int] = {}
            for t in tasks:
                if t.dimension:
                    k = t.dimension.value
                    counts[k] = counts.get(k, 0) + 1
            if counts:
                mx = max(counts.values())
                for dim, cnt in sorted(counts.items(), key=lambda x: -x[1]):
                    bar = _pct_bar(int(cnt / mx * 100), width=14)
                    row = [_t("dim", f"  {dim:<12} ")]
                    row.extend(bar)
                    row.append(_t("dim", f"  {cnt}t"))
                    lines.append(row)
            else:
                L(_t("dim", "    Log tasks to see dimension balance"))
        B()

        # ── Active goals (G-NNN) ──
        active_goals   = [g for g in goals if getattr(g, "is_active", True)
                          and not getattr(g, "is_pseudo", False)
                          and _visible(g.dimension, focus)]
        inactive_goals = [g for g in goals if not getattr(g, "is_active", True)
                          and not getattr(g, "is_pseudo", False)
                          and _visible(g.dimension, focus)]
        L(_t("label", f"  GOALS  ({len(active_goals)} active)"))
        if active_goals:
            for g in active_goals[:10]:
                dim = g.dimension.value if g.dimension else "—"
                seq = g.seq_id or "—"
                L(_t("todo", f"  ◆  {g.title[:32]:<32}  "),
                  _t("dim",  f"{seq}  {dim}"))
        else:
            L(_t("dim", "    No active goals"))
        B()

        if inactive_goals:
            L(_t("label", f"  PAUSED GOALS ({len(inactive_goals)})"))
            for g in inactive_goals[:4]:
                L(_t("dim", f"  ·  {g.title[:38]}"))
            B()

        # ── Slow burns ──
        L(_t("label", f"  SLOW BURNS ({len(slow_burns)})"))
        if slow_burns:
            for sb in slow_burns[:6]:
                dim = sb.dimension if isinstance(sb.dimension, str) else (
                    sb.dimension.value if sb.dimension else "—")
                L(_t("dim", f"  ●  {sb.title[:36]:<36}  "),
                  _t("dim", dim))
        else:
            L(_t("dim", "    None — add long-horizon aspirations"))
        B()

        # ── Monthly finance summary ──
        _section_finance(L, B, show_categories=True, compact=False)

        # ── Upcoming quarter calendar events ──
        try:
            q_end = storage.period_end("quarterly", date.today())
            _section_calendar(L, B, date.today(), q_end,
                              f"to {q_end.isoformat()}", max_events=6, title_width=32)
        except Exception:
            pass

        # ── Review cadence ──
        L(_t("dim", f"  Last review:   {state.last_review or 'never'}"))

    except Exception as e:
        lines.append([_t("overdue", f"  Error: {e}")])

    return lines


# ── Panel: Tactical ────────────────────────────────────────────────────────────

def _build_tactical(focus: str) -> list[list]:
    lines: list[list] = []

    def L(*toks): lines.append(list(toks))
    def B():      lines.append(_blank())

    try:
        from viyugam.models import ProjectStatus, TaskStatus

        config        = storage.load_config()
        quarter       = storage.get_current_quarter()
        projects      = storage.get_projects()
        goals         = storage.get_goals()
        okrs          = storage.get_okrs()
        milestones    = storage.get_milestones()
        project_plans = storage.get_all_project_plans()
        state         = storage.load_state()
        today         = date.today().isoformat()

        season_name = config.season.name if config.season else "No season"
        L(_t("accent", f"  {quarter}  ·  {season_name}"))
        lines.append(_div())
        B()

        # ── Active projects with stats ──
        active = [p for p in projects
                  if p.status == ProjectStatus.ACTIVE
                  and _visible(p.dimension, focus)]
        L(_t("label", f"  PROJECTS  ({len(active)} active)"))
        if active:
            proj_milestones = {}
            for m in milestones:
                if m.project_id and not m.is_done and (m.due_date or "") >= today:
                    prev = proj_milestones.get(m.project_id)
                    if prev is None or (m.due_date or "9999") < (prev.due_date or "9999"):
                        proj_milestones[m.project_id] = m
            for p in active[:8]:
                pct, mins_done, mins_tot, budget = _project_stats(p.id)
                bar    = _pct_bar(pct, width=8)
                h_done = mins_done // 60
                m_done = mins_done % 60
                row = [_t("todo", f"  ●  {p.title[:28]:<28}  ")]
                row.extend(bar)
                row.append(_t("dim", f"  {pct:>3}%  {h_done}h{m_done:02d}m"))
                if budget:
                    row.append(_t("dim", f"  \u20b9{budget:,.0f}"))
                lines.append(row)
                # Second line: plan status + next milestone
                plan_tag  = "Scoped" if p.id in project_plans else "No plan"
                plan_sty  = "done" if p.id in project_plans else "dim"
                next_ms   = proj_milestones.get(p.id)
                ms_str    = f"  \u2192 {next_ms.title[:22]}  {next_ms.due_date}" if next_ms else ""
                L(_t(plan_sty, f"       {plan_tag:<9}"), _t("dim", ms_str))
        else:
            L(_t("dim", "    No active projects"))
        B()

        # ── Paused / icebox ──
        paused = [p for p in projects
                  if p.status in (ProjectStatus.PAUSED, ProjectStatus.ICEBOX)
                  and _visible(p.dimension, focus)]
        if paused:
            L(_t("label", f"  ON HOLD ({len(paused)})"))
            for p in paused[:5]:
                status_str = "paused" if p.status == ProjectStatus.PAUSED else "icebox"
                L(_t("dim", f"  ·  {p.title[:34]:<34}  "),
                  _t("dim", status_str))
            B()

        # ── OKRs ──
        cur_okrs = [o for o in okrs if o.quarter == quarter and o.is_active]
        if cur_okrs:
            L(_t("label", f"  OKRs  ({quarter})"))
            for okr in cur_okrs[:3]:
                L(_t("accent", f"  {okr.objective[:42]}"))
                krs = okr.key_results or []
                done_krs = sum(1 for kr in krs if kr.is_done)
                for kr in krs[:3]:
                    mark = "✓" if kr.is_done else "○"
                    sty  = "done" if kr.is_done else "dim"
                    L(_t(sty, f"    {mark}  {kr.text[:38]}"))
                if krs:
                    bar = _pct_bar(int(done_krs / len(krs) * 100), width=10)
                    row = [_t("dim", "    ")]
                    row.extend(bar)
                    row.append(_t("dim", f"  {done_krs}/{len(krs)}"))
                    lines.append(row)
            B()

        # ── Goals ──
        vis_goals = [g for g in goals if _visible(g.dimension, focus)]
        if vis_goals:
            L(_t("label", "  GOALS"))
            for g in vis_goals[:5]:
                dim = g.dimension.value if g.dimension else "—"
                L(_t("dim", f"  ○  {g.title[:34]:<34}  "),
                  _t("dim", dim))
            B()

        # ── Milestones ──
        upcoming = sorted(
            [m for m in milestones
             if getattr(m, "due_date", None) and m.due_date >= today
             and not getattr(m, "done", False)],
            key=lambda m: m.due_date,
        )
        if upcoming:
            L(_t("label", "  MILESTONES"))
            for m in upcoming[:5]:
                L(_t("dim",  f"  {m.due_date}  "),
                  _t("todo", f"{m.title[:30]}"))
            B()

        # ── Weekly plan (from plans/weekly.json) ──
        weekly_plan = storage.load_plan("weekly")
        if weekly_plan.get("proposal"):
            L(_t("label", "  WEEKLY PLAN"))
            proposal = weekly_plan["proposal"]
            if isinstance(proposal, list):
                items = proposal[:5]
            else:
                items = [line.strip() for line in str(proposal).split("\n") if line.strip()][:5]
            for item in items:
                L(_t("dim", f"  ·  {item[:42]}"))
            B()

        # ── Budget summary ──
        try:
            envelopes = storage.get_budget_envelope_summary()
            if envelopes:
                L(_t("label", "  BUDGET"))
                for env in envelopes[:4]:
                    L(_t("dim", f"  {env.get('name',''):<16}  {env.get('monthly_limit',0):>8,.0f}"))
                B()
        except Exception:
            pass

        # ── Finance: month cashflow ──
        _section_finance(L, B, show_categories=False, compact=True)

        # ── Calendar: next 14 days ──
        _section_calendar(L, B, date.today(), date.today() + timedelta(days=14),
                          "next 14 days", max_events=8, title_width=28)

        L(_t("dim", f"  Last weekly review:  {state.last_review or 'never'}"))

    except Exception as e:
        lines.append([_t("overdue", f"  Error: {e}")])

    return lines


# ── Panel: Daily ───────────────────────────────────────────────────────────────

def _build_daily(focus: str, staging: bool) -> list[list]:
    lines: list[list] = []

    def L(*toks): lines.append(list(toks))
    def B():      lines.append(_blank())

    try:
        from viyugam.models import TaskStatus, ProjectStatus

        today = date.today().isoformat()
        now   = datetime.now()

        tasks_today = storage.get_tasks(scheduled_date=today, include_habits=False)
        habits      = storage.get_habits()
        all_tasks   = storage.get_tasks(include_habits=False)
        state       = storage.load_state()
        inbox       = storage.get_inbox(unprocessed_only=True)
        triage_unprocessed = storage.get_triage(unprocessed_only=True)

        overdue = [
            t for t in all_tasks
            if t.scheduled_date and t.scheduled_date < today
            and t.status in (TaskStatus.TODO, TaskStatus.IN_PROGRESS)
        ]
        done_today = [t for t in tasks_today if t.status == TaskStatus.DONE]
        vis_today  = [t for t in tasks_today if _visible(t.dimension, focus)]

        # Energy indicator from last journal
        energy_str = ""
        try:
            ep = storage.get_energy_pattern()
            if ep and ep.get("pattern_summary"):
                energy_str = f"  ·  {ep['pattern_summary'][:30]}"
        except Exception:
            pass

        # Re-entry detection
        reentry_str = ""
        if state.last_log:
            days_away = (date.today() - date.fromisoformat(state.last_log)).days
            if days_away >= 3:
                reentry_str = f"  [dim]last log: {days_away}d ago[/dim]"

        L(_t("accent", f"  {now.strftime('%A, %-d %b %Y')}  ·  {now.strftime('%H:%M')}{energy_str}"))
        if reentry_str:
            L(_t("warn", f"  Away {days_away} days — consider a quick replan"))
        lines.append(_div())
        B()

        # ── Today's daily plan ──
        daily_plan = storage.load_plan("daily")
        if daily_plan.get("proposal") and not tasks_today:
            L(_t("label", "  TODAY'S PLAN"))
            proposal = daily_plan["proposal"]
            items = [line.strip() for line in str(proposal).split("\n") if line.strip()][:5]
            for item in items:
                L(_t("dim", f"  ·  {item[:42]}"))
            B()

        # ── Staging banner ──
        if staging:
            L(_t("warn",  "  ✦ PLAN STAGED — review above, type 'approve' to confirm"))
            B()

        # ── Schedule ──
        label = "STAGED PLAN" if staging else f"SCHEDULE  ({len(done_today)}/{len(tasks_today)} done)"
        L(_t("label", f"  {label}"))
        if vis_today:
            for t in sorted(vis_today, key=lambda x: (x.status == TaskStatus.DONE, x.time_period or "z")):
                if t.status == TaskStatus.DONE:
                    mark, sty = "✓", "done"
                elif t.status == TaskStatus.IN_PROGRESS:
                    mark, sty = "●", "todo"
                else:
                    mark, sty = "○", "dim"
                period = t.time_period[:3] if t.time_period else "   "
                block  = t.time_block[:5]  if t.time_block  else "     "
                L(_t(sty, f"  {mark}  {block}  {t.title[:28]:<28}"),
                  _t("dim", f"  {t.estimated_minutes}m  {period}"))
        else:
            L(_t("dim", "    No tasks today — type 'plan my day'"))
        B()

        # ── Habits ──
        if habits:
            L(_t("label", "  HABITS"))
            for h in habits[:6]:
                done_h = h.last_done == today
                mark   = "✓" if done_h else "○"
                sty    = "done" if done_h else "dim"
                L(_t(sty, f"  {mark}  {h.title[:32]:<32}"),
                  _t("dim", f"  streak {h.streak}"))
            B()

        # ── Today's calendar events ──
        try:
            today_date = date.today()
            day_events = storage.get_ics_events_for_period(today_date, today_date + timedelta(days=1))
            if day_events:
                L(_t("label", "  CALENDAR"))
                for ev in day_events[:5]:
                    time_str = ev.get("start_time") or "all day"
                    L(_t("dim", f"  {time_str}  {ev['title'][:36]}"))
                B()
        except Exception:
            pass

        # ── Today's transactions ──
        try:
            today_str = date.today().isoformat()
            week_start = storage.period_start("weekly", date.today()).isoformat()
            week_txns = storage.get_transactions_by_period(week_start, today_str)
            if week_txns:
                L(_t("label", "  SPEND  (this week)"))
                for txn in sorted(week_txns, key=lambda x: x.occurred_at, reverse=True)[:4]:
                    amt = f"₹{txn.amount:,.0f}"
                    L(_t("dim", f"  {txn.occurred_at[:10]}  {txn.description[:24]:<24}  {amt:>9}"))
                B()
        except Exception:
            pass

        # ── Overdue ──
        vis_overdue = [t for t in overdue if _visible(t.dimension, focus)]
        if vis_overdue:
            L(_t("label", f"  OVERDUE ({len(vis_overdue)})"))
            for t in vis_overdue[:4]:
                L(_t("overdue", f"  !  {t.title[:40]}"))
            B()

        # ── Week log preview ──
        recent_logs = storage.get_recent_journals(days=7)
        if recent_logs:
            L(_t("label", "  THIS WEEK  (journal)"))
            for log_date, content in recent_logs[:5]:
                first = next(
                    (ln.strip() for ln in content.splitlines() if ln.strip()), ""
                )
                L(_t("dim",  f"  {log_date}  "),
                  _t("dim",  f"{first[:34]}"))
            B()

        # ── Backlog (current project filter) ──
        active_projects = [p for p in storage.get_projects()
                           if p.status == ProjectStatus.ACTIVE
                           and _visible(p.dimension, focus)]
        backlog_tasks = [
            t for t in all_tasks
            if t.status == TaskStatus.BACKLOG
            and _visible(t.dimension, focus)
        ]
        if active_projects and backlog_tasks:
            cur_proj = active_projects[0]
            proj_backlog = [t for t in backlog_tasks if t.project_id == cur_proj.id]
            other_backlog = [t for t in backlog_tasks if not t.project_id or t.project_id != cur_proj.id]

            L(_t("label", f"  BACKLOG  [{cur_proj.title[:20]}]"))
            for t in (proj_backlog or other_backlog)[:6]:
                L(_t("dim", f"  ·  {t.title[:40]}"))
            B()
        elif backlog_tasks:
            L(_t("label", f"  BACKLOG ({len(backlog_tasks)})"))
            for t in backlog_tasks[:5]:
                L(_t("dim", f"  ·  {t.title[:40]}"))
            B()

        # ── Due soon ──
        soon_cutoff = (date.today() + timedelta(days=2)).isoformat()
        due_soon = [
            t for t in all_tasks
            if t.due and t.due <= soon_cutoff
            and t.status not in (TaskStatus.DONE,)
        ]
        if due_soon:
            L(_t("label", f"  DUE SOON ({len(due_soon)})"))
            for t in sorted(due_soon, key=lambda x: x.due or "")[:4]:
                seq = f"[{t.seq_id}]  " if t.seq_id else ""
                L(_t("warn", f"  !  {seq}{t.title[:32]:<32}"),
                  _t("dim",  f"  {t.due}"))
            B()

        # ── Triage inbox ──
        try:
            triage_sty = "warn" if triage_unprocessed else "dim"
            L(_t(triage_sty, f"  Triage: {len(triage_unprocessed)} unprocessed"))
            for item in triage_unprocessed[:3]:
                L(_t("dim", f"  ·  {item.content[:40]}"))
            B()
        except Exception:
            pass

        # ── Footer ──
        L(_t("dim", f"  Last plan: {state.last_plan or 'never'}   "
                    f"Streak: {state.current_streak}d"))

    except Exception as e:
        lines.append([_t("overdue", f"  Error: {e}")])

    return lines


# ── Panel: Review ──────────────────────────────────────────────────────────────

def _build_project_plan_context(session: dict, lines: list, L, B) -> list[list]:
    """Left-pane context shown during a project planning session."""
    project  = session.get("project", {})
    existing = session.get("existing_plan")

    L(_t("accent", f"  {project.get('seq_id','Project')}  ·  {project.get('title','')[:32]}"))
    lines.append(_div())
    B()

    goal = session.get("linked_goal")
    if goal:
        L(_t("dim", f"  Goal: {goal.get('title','')[:38]}"))
        B()

    if project.get("deadline"):
        L(_t("dim", f"  Deadline: {project['deadline']}"))
    if project.get("budget_cap"):
        L(_t("dim", f"  Budget cap: \u20b9{project['budget_cap']:,.0f}"))
    if project.get("deadline") or project.get("budget_cap"):
        B()

    # ── Existing scope ──
    scope = existing.get("scope_md", "") if existing else ""
    L(_t("label", "  SCOPE"))
    if scope:
        for line in scope[:300].split("\n")[:4]:
            if line.strip():
                L(_t("dim", f"  {line.strip()[:48]}"))
    else:
        L(_t("dim", "  Not yet defined — discuss in the chat."))
    B()

    # ── Milestones ──
    try:
        milestones = storage.get_milestones(project_id=project.get("id"))
        if milestones:
            L(_t("label", "  MILESTONES"))
            for m in sorted(milestones, key=lambda x: x.due_date or "9999")[:6]:
                mark = "\u2713" if m.is_done else "\u00b7"
                sty  = "done" if m.is_done else "dim"
                date_str = f"  {m.due_date}" if m.due_date else ""
                L(_t(sty, f"  {mark}  {m.title[:34]}{date_str}"))
            B()
    except Exception:
        pass

    # ── Success criteria ──
    criteria = existing.get("success_criteria", []) if existing else []
    if criteria:
        L(_t("label", "  SUCCESS CRITERIA"))
        for c in criteria[:4]:
            L(_t("dim", f"  \u00b7  {c[:46]}"))
        B()

    L(_t("dim", "  Say 'save' or 'done' to finalise."))
    return lines


def _build_review_panel(session: Optional[dict]) -> list[list]:
    lines: list[list] = []

    def L(*toks): lines.append(list(toks))
    def B():      lines.append(_blank())

    L(_t("accent", "  Review"))
    lines.append(_div())
    B()

    if not session:
        L(_t("dim", "  No active session."))
        return lines

    if session.get("type") == "project_plan":
        return _build_project_plan_context(session, lines, L, B)

    if session.get("type") != "review":
        L(_t("dim", "  No active review session."))
        return lines

    cadence = session.get("cadence", "weekly")
    today   = session.get("today", "")
    review_data = session.get("review_data", {})

    # ── Period ──
    pstart = review_data.get("period_start", "")
    pend   = review_data.get("period_end", today)
    if pstart:
        L(_t("dim", f"  {cadence.upper()} REVIEW  {pstart} → {pend}"))
        B()

    # ── Tasks this period ──
    try:
        tasks = storage.get_tasks(include_habits=False)
        done_tasks  = [t for t in tasks if getattr(t, "status", None) and "done" in str(t.status).lower()]
        open_tasks  = [t for t in tasks if not (getattr(t, "status", None) and "done" in str(t.status).lower())]
        L(_t("label", f"  TASKS"))
        if done_tasks:
            for t in done_tasks[:5]:
                L(_t("done", f"  \u2713  {t.title[:44]}"))
        if open_tasks:
            for t in open_tasks[:8]:
                L(_t("todo", f"  \u00b7  {t.title[:44]}"))
        if not done_tasks and not open_tasks:
            L(_t("dim", "  No tasks."))
        B()
    except Exception:
        pass

    # ── Journals written so far ──
    dims     = _REVIEW_DIMS
    dim_idx  = session.get("dim_idx", 0)
    phase    = session.get("phase", "retro")

    if phase in ("journal", "plan"):
        L(_t("label", "  JOURNALS"))
        dim_summaries = session.get("dim_summaries", {})
        for i, dim in enumerate(dims):
            if dim in dim_summaries:
                if dim_summaries[dim] == "skipped":
                    L(_t("dim",  f"  \u2500  {dim:<14}  skipped"))
                else:
                    L(_t("done", f"  \u2713  {dim:<14}  written"))
            elif i == dim_idx and phase == "journal":
                L(_t("warn", f"  \u25cf  {dim:<14}  in progress"))
            else:
                L(_t("dim",  f"  \u00b7  {dim:<14}  pending"))
        B()

    # ── Phase indicator ──
    phase_labels = {"retro": "Retrospective", "journal": "Dimension Journals", "plan": "Plan Proposal"}
    L(_t("dim", f"  Phase: {phase_labels.get(phase, phase)}"))

    return lines


# ── Panel: Research ────────────────────────────────────────────────────────────

def _build_research(jobs: list) -> list[list]:
    lines: list[list] = []

    def L(*toks): lines.append(list(toks))
    def B():      lines.append(_blank())

    L(_t("accent", "  Research"))
    lines.append(_div())
    B()

    if not jobs:
        L(_t("dim",  "  No research jobs yet."))
        L(_t("dim",  "  Type  \"research <topic>\"  to start one."))
        return lines

    SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    for job in jobs:
        status  = job["status"]
        topic   = job["topic"]
        elapsed = job.get("elapsed", 0)
        mins    = elapsed // 60
        secs    = elapsed % 60

        if status == "running":
            tick    = job.get("tick", 0)
            spinner = SPINNER[tick % len(SPINNER)]
            L(_t("spinner", f"  {spinner}  "),
              _t("todo",    f"{topic[:38]}"),
              _t("dim",     f"  running  {mins}:{secs:02d}"))
        elif status == "done":
            L(_t("done",  f"  ✓  {topic[:38]}"),
              _t("dim",   f"  {mins}:{secs:02d}"))
            result = job.get("result", "")
            if result:
                for ln in result.splitlines()[:6]:
                    if ln.strip():
                        L(_t("dim", f"    {ln[:46]}"))
            L(_t("dim", "    [scroll ↑↓ for full result]"))
        elif status == "error":
            L(_t("overdue", f"  ✗  {topic[:38]}"),
              _t("dim",     f"  {job.get('error','error')[:30]}"))
        B()

    return lines


# ── ANSI sanitiser ─────────────────────────────────────────────────────────────

import re as _re

# Matches cursor-movement / screen-manipulation CSI sequences but NOT SGR (color)
# codes (which end in 'm').  These must not be replayed inside the chat pane.
_CURSOR_RE = _re.compile(
    r'\x1b\[(?:\d+(?:;\d+)*)?[ABCDEFGHJKSTf]'   # cursor move / erase / position
    r'|\x1b\[\?(?:25[lh]|2004[lh])'              # cursor show/hide, bracketed paste
    r'|\x1b[78]'                                  # ESC 7/8 save/restore cursor
    r'|\r(?!\n)'                                  # bare CR (not CRLF)
)


def _sanitize_ansi(text: str) -> str:
    """Strip cursor-positioning codes; keep color/style SGR codes."""
    return _CURSOR_RE.sub('', text)


class _NullStdin:
    """Drop-in stdin replacement that raises EOFError immediately.

    Prevents background threads from calling Python's built-in input() and
    pulling the terminal out of prompt_toolkit's raw mode.
    """
    def readline(self):
        raise EOFError("dashboard: non-interactive")
    def read(self, n=-1):
        raise EOFError("dashboard: non-interactive")
    def isatty(self):
        return False
    def fileno(self):
        raise io.UnsupportedOperation("fileno")


# ── Rich output capture ────────────────────────────────────────────────────────

@contextlib.contextmanager
def _capture_rich(width: int = 60):
    """Temporarily replace module-level consoles to capture rich output."""
    import viyugam.main as _m
    import viyugam.repl as _r

    buf = io.StringIO()
    cap = RichConsole(
        file=buf,
        force_terminal=True,     # Enables ANSI codes and proper word wrapping
        color_system="truecolor",
        width=max(width, 40),
        highlight=False,
    )
    # Prevent Prompt.ask() / Confirm.ask() from blocking stdin in a background
    # thread.  The lambda previously used was missing keyword-only args, causing
    # TypeError that let the real console.input() run and corrupt the terminal.
    def _no_input(prompt="", *, markup=True, emoji=True, password=False, stream=None):
        raise EOFError("dashboard: non-interactive")
    cap.input = _no_input

    old = {}
    for mod in (_m, _r):
        if hasattr(mod, "console"):
            old[mod] = mod.console
            mod.console = cap

    import sys as _sys
    old_stdin = _sys.stdin
    _sys.stdin = _NullStdin()
    try:
        yield buf
    finally:
        _sys.stdin = old_stdin
        for mod, c in old.items():
            mod.console = c


# ── Background command runner ──────────────────────────────────────────────────

def _run_command_bg(
    text: str,
    state: _State,
    app: Application,
    chat_width: int,
) -> None:
    """Run _ai_dispatch in background, capture output into chat pane."""
    import viyugam.repl as _repl_mod
    from viyugam.repl import _ai_dispatch

    state.running = True
    state.chat.append({"role": "system", "text": "thinking…"})
    app.invalidate()

    _repl_mod._tl.dashboard = True
    try:
        with _capture_rich(width=chat_width) as buf:
            _ai_dispatch(text)
        output = _sanitize_ansi(buf.getvalue())
    except Exception as e:
        output = f"Error: {e}"
    finally:
        _repl_mod._tl.dashboard = False

    # Remove the "thinking…" placeholder
    if state.chat and state.chat[-1].get("text") == "thinking…":
        state.chat.pop()

    if output.strip():
        state.chat.append({"role": "assistant", "ansi": output})
    state.running = False
    state.dirty   = True   # force panel cache refresh
    state.scroll_r = max(0, _count_chat_lines(state.chat) - 20)
    app.invalidate()


def _run_plan_bg(state: _State, app: Application, chat_width: int) -> None:
    """Run plan with bypass attrs, then enter staging mode."""
    from viyugam.main import cmd_plan
    from viyugam.storage import get_day_type, load_config

    state.running = True
    state.chat.append({"role": "system", "text": "Planning your day…"})
    app.invalidate()

    try:
        config   = load_config()
        day_type = get_day_type(date.today().isoformat(), config)
        ns = argparse.Namespace(
            replan=False,
            _catch_up_notes="",
            _day_type_override=day_type,
        )
        with _capture_rich(width=chat_width) as buf:
            cmd_plan(ns)
        output = _sanitize_ansi(buf.getvalue())
    except Exception as e:
        output = f"Plan error: {e}"
    finally:
        state.running = False

    if state.chat and state.chat[-1].get("text") == "Planning your day…":
        state.chat.pop()

    if output.strip():
        state.chat.append({"role": "assistant", "ansi": output})

    state.staging = True
    state.panel   = 3  # switch to Daily panel
    state.dirty   = True
    state.chat.append({
        "role": "system",
        "text": "Plan staged in Daily panel. Type 'approve' to confirm.",
    })
    state.scroll_r = max(0, _count_chat_lines(state.chat) - 20)
    app.invalidate()


def _run_research_bg(
    topic: str,
    job: dict,
    state: _State,
    app: Application,
) -> None:
    """Run research in background, update job dict when done."""
    from viyugam.main import cmd_research

    state.running = True
    start = time.time()
    try:
        with _capture_rich(width=80) as buf:
            cmd_research(argparse.Namespace(topic=topic.split()))
        result = _sanitize_ansi(buf.getvalue())
        # Strip remaining ANSI color codes for plain-text storage in Research panel
        plain = _re.sub(r'\x1b\[[0-9;]*m', '', result)
        job["status"]  = "done"
        job["result"]  = plain.strip()
    except Exception as e:
        job["status"] = "error"
        job["error"]  = str(e)
    finally:
        job["elapsed"] = int(time.time() - start)
        state.running = False

    state.panel = 4  # switch to Research panel
    state.chat.append({
        "role": "system",
        "text": f"Research done: \"{topic}\" — switched to Research panel.",
    })
    app.invalidate()


# ── Session management (multi-turn review / plan inside dashboard) ────────────

_REVIEW_DIMS = ["career", "wealth", "health", "relationships", "joy", "learning"]


def _session_chat(role: str, text: str, state: "_State", app: Application) -> None:
    if role == "assistant":
        state.chat.append({"role": "assistant", "ansi": text})
    else:
        state.chat.append({"role": role, "text": text})
    # In triage mode, don't auto-scroll to bottom — keep user's message at top.
    if state.ui_mode != "triage":
        state.scroll_r = max(0, _count_chat_lines(state.chat) - 20)
    app.invalidate()


def _start_review_session(cadence: str, state: "_State", app: Application) -> None:
    """Build context, run first retro turn, set active_session. Runs in bg thread."""
    state.running = True
    app.invalidate()
    try:
        from viyugam.agents import reviewer as rev
        today = date.today()
        try:
            pstart = storage.period_start(cadence, today)
            tasks  = storage.get_tasks(include_habits=False)
            goals  = storage.get_goals()
            plan   = storage.load_plan(cadence)
            done   = [t.title for t in tasks
                      if getattr(t, "status", None) and "done" in str(t.status).lower()]
            review_data = {
                "period_start": pstart.isoformat(),
                "period_end":   today.isoformat(),
                "prior_plan":   plan,
                "completed_tasks": done[:10],
                "goals": [g.title for g in goals[:10]],
            }
        except Exception:
            review_data = {}

        opening_ctx = (
            f"Starting {cadence} review. "
            f"Period: {review_data.get('period_start','?')} – {review_data.get('period_end','?')}. "
            f"Goals: {', '.join(review_data.get('goals',[])[:3]) or 'none set'}. "
            f"Completed this period: {', '.join(review_data.get('completed_tasks',[])[:3]) or 'none logged'}."
        )
        history = []
        opening, _ = rev.retro_turn(history, opening_ctx, cadence, review_data)
        history.append({"role": "assistant", "content": opening})

        state.active_session = {
            "type":         "review",
            "phase":        "retro",
            "cadence":      cadence,
            "today":        today.isoformat(),
            "retro_history": history,
            "review_data":  review_data,
            "dim_idx":      0,
            "dim_history":  [],
            "dim_summaries": {},
            "start_time":   time.time(),
            "canvas_before":   [],
            "canvas_proposed": [],
            "canvas_diff_mode": True,
        }
        state.ui_mode     = "review"
        state.ui_mode_arg = cadence
        state.panel       = 0  # Session (canvas) panel
        _session_chat("assistant", opening, state, app)
        _session_chat("system",
            "Type your reflections. 'next' to advance, 'quit' to end.", state, app)
    except Exception as exc:
        state.active_session = None
        _session_chat("system", f"Could not start review: {exc}", state, app)
    finally:
        state.running = False
        app.invalidate()


def _start_plan_session(scope: str, state: "_State", app: Application) -> None:
    """Generate initial plan proposal, set active_session. Runs in bg thread."""
    state.running = True
    app.invalidate()
    try:
        from viyugam.agents.chairman import generate_initial_plan_proposal
        today  = date.today()
        pstart = storage.period_start(scope, today)
        pend   = storage.period_end(scope, today)
        tasks  = [t.model_dump() for t in storage.get_tasks(include_habits=False)[:20]]
        goals  = [g.model_dump() for g in storage.get_goals()[:10]]
        parent_scope = {"daily": "weekly", "weekly": "monthly",
                        "monthly": "quarterly"}.get(scope, "")
        parent_plan  = storage.load_plan(parent_scope) if parent_scope else {}
        values        = storage.load_values()
        budget        = storage.get_budget_envelope_summary()
        okrs          = ([o.model_dump() for o in storage.get_okrs(active_only=True)]
                         if scope in ("weekly", "monthly") else None)

        result   = generate_initial_plan_proposal(
            scope=scope, tasks=tasks, goals=goals,
            parent_plan=parent_plan, values=values,
            budget_envelopes=budget,
            period_start=pstart.isoformat(), period_end=pend.isoformat(),
            okrs=okrs,
        )
        proposal = result.get("proposal") or result.get("raw", "")
        opening  = result.get("vision") or proposal[:400]
        history  = [{"role": "assistant", "content": opening}]

        state.active_session = {
            "type":             "plan",
            "scope":            scope,
            "today":            today.isoformat(),
            "plan_history":     history,
            "current_proposal": proposal,
            "canvas_before":    [],
            "canvas_proposed":  [],
            "canvas_diff_mode": True,
        }
        state.ui_mode     = "plan"
        state.ui_mode_arg = scope
        state.panel       = 0  # Strategy panel
        _session_chat("assistant", opening or "Here is the proposed plan.", state, app)
        if proposal and proposal != opening:
            _session_chat("system", proposal[:600], state, app)
        _session_chat("system",
            "Discuss the plan. Say 'approve' or 'save' to finalise.", state, app)
    except Exception as exc:
        state.active_session = None
        _session_chat("system", f"Could not start plan: {exc}", state, app)
    finally:
        state.running = False
        app.invalidate()


def _start_project_plan_session(project_id: str, state: "_State",
                                app: Application) -> None:
    """Start a project planning boardroom session. Runs in a bg thread."""
    state.running = True
    app.invalidate()
    try:
        from viyugam.agents.project_planner import start_project_plan_session
        project = next(
            (p for p in storage.get_projects() if p.seq_id == project_id
             or p.id == project_id), None
        )
        if not project:
            _session_chat("system", f"Project not found: {project_id}", state, app)
            return
        goals        = storage.get_goals()
        existing_plan = storage.get_project_plan(project.id)
        linked_goal  = next((g for g in goals if g.id == project.goal_id), None)

        opening = start_project_plan_session(
            project=project.model_dump(),
            existing_plan=existing_plan.model_dump() if existing_plan else None,
            goals=[g.model_dump() for g in goals],
        )
        history = [{"role": "assistant", "content": opening}]

        state.active_session = {
            "type":          "project_plan",
            "project_id":    project.id,
            "project":       project.model_dump(),
            "existing_plan": existing_plan.model_dump() if existing_plan else None,
            "linked_goal":   linked_goal.model_dump() if linked_goal else None,
            "history":       history,
            "canvas_before":    [],
            "canvas_proposed":  [],
            "canvas_diff_mode": True,
        }
        state.ui_mode     = "project"
        state.ui_mode_arg = project.seq_id or project.id
        state.panel       = 0  # Scope (canvas) panel
        _session_chat("section", f"── {project.seq_id or 'PROJECT'}: {project.title[:30]} ──",
                      state, app)
        _session_chat("assistant", opening, state, app)
        _session_chat("system", "Say 'save' or 'done' when ready to finalise.", state, app)
    except Exception as exc:
        state.active_session = None
        _session_chat("system", f"Could not start project planning: {exc}", state, app)
    finally:
        state.running = False
        app.invalidate()


def _project_plan_turn(text: str, tl: str, session: dict, state: "_State",
                       app: Application) -> None:
    """Handle one turn of the project planning conversation."""
    from viyugam.agents.project_planner import project_plan_turn, extract_project_plan
    from viyugam.models import ProjectPlan, Milestone

    history = session.get("history", [])
    history.append({"role": "user", "content": text})

    reply, is_done = project_plan_turn(history, text, session["project"])
    history.append({"role": "assistant", "content": reply})
    session["history"] = history

    # Parse PLAN_STATE: block from reply, update canvas, show only display text
    display_text, canvas_items = _parse_canvas_block(reply)
    if canvas_items:
        session["canvas_proposed"] = canvas_items
    _session_chat("assistant", display_text or reply, state, app)

    if is_done:
        # Extract structured plan from conversation
        extracted = extract_project_plan(history, session["project"])
        project_id = session["project_id"]

        # Build and save ProjectPlan
        existing    = session.get("existing_plan") or {}
        plan_kwargs = dict(
            project_id=project_id,
            scope_md=extracted.get("scope_md", ""),
            success_criteria=extracted.get("success_criteria", []),
            out_of_scope=extracted.get("out_of_scope", []),
            total_budget=extracted.get("total_budget", 0.0),
            notes=extracted.get("notes", ""),
        )
        if existing.get("id"):
            plan_kwargs["id"] = existing["id"]
        plan = ProjectPlan(**plan_kwargs)
        try:
            storage.save_project_plan(plan)
        except Exception as exc:
            _session_chat("system", f"Could not save plan: {exc}", state, app)

        # Save any new milestones extracted
        milestone_count = 0
        for m_data in extracted.get("milestones", []):
            if m_data.get("title"):
                m = Milestone(
                    project_id=project_id,
                    title=m_data["title"],
                    due_date=m_data.get("due_date"),
                )
                try:
                    storage.save_milestone(m)
                    milestone_count += 1
                except Exception:
                    pass

        summary = f"\u2713 Project plan saved."
        if milestone_count:
            summary += f"  {milestone_count} milestone(s) added."
        _session_chat("system", summary, state, app)
        _exit_mode(state, app)


def _continue_session(text: str, state: "_State", app: Application) -> None:
    """Route a user message into the active session. Runs in bg thread."""
    session = state.active_session
    if not session:
        return
    state.running = True
    app.invalidate()
    tl = text.lower().strip()
    try:
        if tl in ("quit", "exit", "q"):
            state.dirty = True
            _exit_mode(state, app)
            _session_chat("system", "Session ended.", state, app)
            return
        stype = session["type"]
        if stype == "review":
            _review_turn(text, tl, session, state, app)
        elif stype == "plan":
            _plan_turn(text, tl, session, state, app)
        elif stype == "project_plan":
            _project_plan_turn(text, tl, session, state, app)
        elif stype == "goal_plan":
            _goal_plan_turn(text, tl, session, state, app)
        elif stype == "triage":
            _triage_session_turn(text, tl, session, state, app)
        else:
            state.active_session = None
    except Exception as exc:
        _session_chat("system", f"Error: {exc}", state, app)
    finally:
        state.running = False
        app.invalidate()


def _retro_phase(text: str, tl: str, session: dict, state: "_State",
                 app: Application) -> None:
    from viyugam.agents import reviewer as rev
    history = session["retro_history"]
    history.append({"role": "user", "content": text})
    response, done = rev.retro_turn(history, text, session["cadence"],
                                    session.get("review_data", {}))
    history.append({"role": "assistant", "content": response})

    # Parse PLAN_STATE: block — update canvas with retro insights
    display_text, canvas_items = _parse_canvas_block(response)
    if canvas_items:
        session["canvas_proposed"] = canvas_items
        app.invalidate()

    if tl == "next" or done:
        if session.get("cadence") == "daily":
            # Daily review: skip dimension journals, go straight to plan
            _session_chat("system",
                "Retro done. Generating plan proposal\u2026", state, app)
            _review_generate_plan(session, state, app)
        else:
            _session_chat("system",
                "Moving to journals — 6 dimensions. 'next' writes & continues, 'skip' skips.",
                state, app)
            session["phase"]       = "journal"
            session["dim_idx"]     = 0
            session["dim_history"] = []
            _journal_open_dim(session, state, app)
    else:
        _session_chat("assistant", display_text or response, state, app)


def _journal_phase(text: str, tl: str, session: dict, state: "_State",
                   app: Application) -> None:
    from viyugam.agents import reviewer as rev
    cadence = session["cadence"]
    today   = session["today"]
    dims    = _REVIEW_DIMS
    idx     = session.get("dim_idx", 0)

    if idx >= len(dims):
        _review_finish_journals(session, state, app)
        return

    dim = dims[idx]

    if tl in ("next", "skip"):
        if tl == "skip":
            content = "skipped"
        else:
            try:
                content = rev.synthesize_dim_journal(
                    session.get("dim_history", []), dim, cadence, today)
            except Exception:
                content = " ".join(
                    m["content"] for m in session.get("dim_history", [])
                    if m.get("role") == "user") or "no notes"
        try:
            jp = storage.JOURNAL / f"{today}-{cadence}-{dim}.md"
            jp.parent.mkdir(parents=True, exist_ok=True)
            jp.write_text(f"# {dim} — {today}\n\n{content}\n")
        except Exception:
            pass
        dim_summaries = session.setdefault("dim_summaries", {})
        dim_summaries[dim] = content[:400] if content != "skipped" else "skipped"
        _session_chat("system", f"\u2713 {dim} saved.", state, app)
        session["dim_idx"]     = idx + 1
        session["dim_history"] = []
        if session["dim_idx"] >= len(dims):
            _review_finish_journals(session, state, app)
        else:
            _journal_open_dim(session, state, app)
    else:
        dim_history = session.get("dim_history", [])
        dim_history.append({"role": "user", "content": text})
        response, done = rev.dim_journal_turn(
            dim_history, text, dim, cadence,
            prior_summaries=session.get("dim_summaries", {}))
        dim_history.append({"role": "assistant", "content": response})
        session["dim_history"] = dim_history
        _session_chat("assistant", response, state, app)
        if done:
            _journal_phase("next", "next", session, state, app)


def _task_confirm_phase(text: str, tl: str, session: dict, state: "_State",
                        app: Application) -> None:
    if tl == "confirm":
        extracted = session.get("pending_task_confirm", {})
        added = 0
        try:
            for task_title in extracted.get("new_tasks", []):
                storage.append_triage(task_title, source="review")
                added += 1
        except Exception:
            pass
        session.pop("pending_task_confirm", None)
        _session_chat("system", f"\u2713 {added} task(s) added to triage.", state, app)
    else:
        _session_chat("system", "Tasks skipped.", state, app)
        session.pop("pending_task_confirm", None)
    _review_generate_plan(session, state, app)


def _review_turn(text: str, tl: str, session: dict, state: "_State",
                 app: Application) -> None:
    phase = session["phase"]
    if   phase == "retro":        _retro_phase(text, tl, session, state, app)
    elif phase == "journal":      _journal_phase(text, tl, session, state, app)
    elif phase == "task_confirm": _task_confirm_phase(text, tl, session, state, app)
    elif phase == "plan":         _plan_turn(text, tl, session, state, app)


def _journal_open_dim(session: dict, state: "_State", app: Application) -> None:
    from viyugam.agents import reviewer as rev
    dim     = _REVIEW_DIMS[session["dim_idx"]]
    cadence = session["cadence"]
    try:
        opening, _ = rev.dim_journal_turn(
            [], "start", dim, cadence,
            prior_summaries=session.get("dim_summaries", {}),
        )
    except Exception:
        opening = f"Let's reflect on your {dim} dimension. What stands out this {cadence}?"
    session["dim_history"] = [{"role": "assistant", "content": opening}]
    _session_chat("section", f"\u2500\u2500 {dim.upper()} \u2500\u2500", state, app)
    _session_chat("assistant", opening, state, app)


def _render_plan_proposal(proposal: str, state: "_State", app: Application) -> None:
    """Render a structured plan proposal with colored priority bullets."""
    lines = [l.strip() for l in proposal.split("\n") if l.strip()]
    for line in lines:
        lw = line.lower()
        if "priority 1" in lw[:20]:
            _session_chat("plan.p1", line, state, app)
        elif "priority 2" in lw[:20]:
            _session_chat("plan.p2", line, state, app)
        elif "priority 3" in lw[:20]:
            _session_chat("plan.p3", line, state, app)
        elif lw.startswith("defer") or "defer this" in lw[:20]:
            _session_chat("plan.defer", line, state, app)
        else:
            _session_chat("assistant", line, state, app)


def _review_finish_journals(session: dict, state: "_State", app: Application) -> None:
    from viyugam.agents import reviewer as rev
    cadence = session["cadence"]

    # ── Duration tracking ──
    elapsed_min = int((time.time() - session.get("start_time", time.time())) / 60)
    _session_chat("system",
        f"\u2713 All journals written \u2014 {elapsed_min} min. Extracting action items…",
        state, app)

    # ── Task extraction from dim summaries ──
    dim_summaries = session.get("dim_summaries", {})
    try:
        extracted = rev.extract_review_tasks(dim_summaries)
        new_tasks = extracted.get("new_tasks", [])
        done_hints = extracted.get("completed_hints", [])
        if new_tasks or done_hints:
            session["pending_task_confirm"] = extracted
            session["phase"] = "task_confirm"
            _session_chat("section", "\u2500\u2500 TASK REVIEW \u2500\u2500", state, app)
            if new_tasks:
                _session_chat("system", "New tasks found:", state, app)
                for t in new_tasks:
                    _session_chat("system", f"  \u00b7 {t}", state, app)
            if done_hints:
                _session_chat("system", "Mentioned as done:", state, app)
                for t in done_hints:
                    _session_chat("system", f"  \u2713 {t}", state, app)
            _session_chat("system",
                "Type 'confirm' to add these, 'skip' to ignore.",
                state, app)
            return
    except Exception:
        pass

    _review_generate_plan(session, state, app)


def _review_generate_plan(session: dict, state: "_State", app: Application) -> None:
    """Generate the plan proposal after journals (and optional task confirm)."""
    cadence = session["cadence"]
    _session_chat("system", "Generating plan proposal\u2026", state, app)
    session["phase"]            = "plan"
    session["plan_history"]     = []
    session["current_proposal"] = ""
    try:
        from viyugam.agents.chairman import generate_initial_plan_proposal
        today_d = date.fromisoformat(session["today"])
        pstart  = storage.period_start(cadence, today_d)
        pend    = storage.period_end(cadence, today_d)
        tasks   = [t.model_dump() for t in storage.get_tasks(include_habits=False)[:20]]
        goals   = [g.model_dump() for g in storage.get_goals()[:10]]
        values  = storage.load_values()
        result  = generate_initial_plan_proposal(
            scope=cadence, tasks=tasks, goals=goals,
            parent_plan={}, values=values, budget_envelopes=[],
            period_start=pstart.isoformat(), period_end=pend.isoformat(),
        )
        proposal = result.get("proposal") or result.get("raw", "")
        session["current_proposal"] = proposal
        if proposal:
            _render_plan_proposal(proposal, state, app)
    except Exception as exc:
        _session_chat("system", f"Could not generate plan: {exc}", state, app)
    _session_chat("system", "Discuss or say 'approve' to save and finish.", state, app)


def _plan_turn(text: str, tl: str, session: dict, state: "_State",
               app: Application) -> None:
    from viyugam.agents.chairman import directive_boardroom_turn
    scope = session.get("scope") or session.get("cadence", "weekly")

    if tl in APPROVE_KW or tl in ("save", "done"):
        elapsed_min = int((time.time() - session.get("start_time", time.time())) / 60)
        try:
            storage.save_plan(scope, {
                "proposal": session.get("current_proposal", ""),
                "date":     session.get("today"),
                "cadence":  scope,
            })
            state.dirty = True
        except Exception:
            pass
        _exit_mode(state, app)
        _session_chat("system",
            f"\u2713 Plan saved. Review complete \u2014 {elapsed_min} min. Good luck this {scope}!",
            state, app)
        return

    history = session.get("plan_history", [])
    history.append({"role": "user", "content": text})
    result   = directive_boardroom_turn(
        scope=scope, context="", user_message=text,
        history=history, current_proposal=session.get("current_proposal", ""),
    )
    response = result.get("vision") or result.get("raw", "")
    proposal = result.get("proposal") or session.get("current_proposal", "")
    history.append({"role": "assistant", "content": response})
    session["plan_history"]     = history
    session["current_proposal"] = proposal
    # Update canvas items from structured output
    _op_map = {"+": "add", "-": "del", "=": "ctx"}
    canvas_items = result.get("canvas_items") or []
    if canvas_items:
        session["canvas_proposed"] = [
            {"op": _op_map.get(item.get("op", "="), "ctx"), "text": item.get("text", "")}
            for item in canvas_items
        ]
    _session_chat("assistant", response, state, app)
    if proposal and proposal != response:
        _session_chat("system", f"Updated plan:\n{proposal[:500]}", state, app)


# ── Ticker thread (elapsed time + spinner) ────────────────────────────────────

def _ticker_thread(state: _State, app: Application, stop: threading.Event,
                   request_build_fn=None) -> None:
    _reentry_checked = False
    while not stop.is_set():
        time.sleep(1)
        state.tick += 1
        for job in state.research:
            if job["status"] == "running":
                job["elapsed"] = job.get("elapsed", 0) + 1
                job["tick"]    = state.tick

        # Re-entry detection (check once per session, on tick 2)
        if not _reentry_checked and state.tick == 2:
            _reentry_checked = True
            try:
                sys_state = storage.load_state()
                if sys_state.last_log:
                    days_away = (date.today() - date.fromisoformat(sys_state.last_log)).days
                    if days_away >= 3 and not state.running:
                        state.chat.append({
                            "role": "system",
                            "text": (
                                f"Welcome back. You've been away {days_away} days. "
                                f"Want to run a quick weekly replan? Type 'plan week'."
                            ),
                        })
                        state.scroll_r = max(0, _count_chat_lines(state.chat) - 20)
            except Exception:
                pass

        # Pre-build execute panels in the background so switching is instant
        if request_build_fn is not None and state.ui_mode == "execute":
            for p in range(4):  # GPS, Strategic, Tactical, Daily
                request_build_fn(p, state.focus_mode, state.staging)

        app.invalidate()


# ── Chat rendering ─────────────────────────────────────────────────────────────

def _chat_tokens(chat: list) -> list[tuple[str, str]]:
    """Render all chat entries to a flat token list (no scrolling applied)."""
    _PLAN_STYLES = {"plan.p1", "plan.p2", "plan.p3", "plan.defer"}
    out: list[tuple[str, str]] = []
    for entry in chat:
        role = entry.get("role")
        if role == "user":
            out.append(("class:chat.user", f"  > {entry['text']}"))
            out.append(("", "\n"))
        elif role == "assistant":
            ansi_str = entry.get("ansi", "")
            if ansi_str:
                out.extend(ANSI(ansi_str).__pt_formatted_text__())
            out.append(("", "\n"))
        elif role == "system":
            out.append(("class:chat.system", f"  {entry['text']}"))
            out.append(("", "\n"))
        elif role == "section":
            out.append(("", "\n"))
            out.append((f"class:chat.section", f"  {entry['text']}"))
            out.append(("", "\n"))
        elif role in _PLAN_STYLES:
            out.append((f"class:{role}", f"  {entry['text']}"))
            out.append(("", "\n"))
    return out


def _count_chat_lines(chat: list) -> int:
    """Count the number of rendered lines in the chat (approx)."""
    total = 0
    for entry in chat:
        role = entry.get("role")
        if role == "assistant":
            total += entry.get("ansi", "").count("\n") + 1
        elif role == "section":
            total += 2  # blank line + heading line
        else:
            total += 1
    return max(0, total)


def _render_chat(state: _State) -> list[tuple[str, str]]:
    """Return tokens for the chat pane, skipping the first scroll_r lines."""
    tokens = _chat_tokens(state.chat)
    if state.scroll_r <= 0:
        return tokens
    # Skip exactly scroll_r newline tokens
    skipped = 0
    for i, (style, text) in enumerate(tokens):
        if style == "" and text == "\n":
            skipped += 1
            if skipped >= state.scroll_r:
                return tokens[i + 1:]
    return []


# ── Panel content renderer ────────────────────────────────────────────────────

def _render_panel(panel_lines: list[list], scroll: int) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    visible = panel_lines[scroll:]
    for line_toks in visible:
        if line_toks:
            out.extend(line_toks)
        out.append(("", "\n"))
    return out


# ── Key bindings ──────────────────────────────────────────────────────────────

def _setup_keybindings(kb, state: "_State", input_buffer, stop_tick,
                       cache: dict, building: set, panel_lines_fn) -> None:
    """Register all key bindings on kb. Extracted from run_dashboard for clarity."""
    is_normal = Condition(lambda: state.mode == "normal")
    is_insert = Condition(lambda: state.mode == "insert")

    # ── Normal mode: navigation ──
    @kb.add("left", eager=True, filter=is_normal)
    def _left(event):
        state.panel = max(0, state.panel - 1)

    @kb.add("right", eager=True, filter=is_normal)
    def _right(event):
        panels = PANEL_SETS.get(state.ui_mode, PANEL_SETS["execute"])
        state.panel = min(len(panels) - 1, state.panel + 1)

    @kb.add("up", eager=True, filter=is_normal)
    def _up(event):
        if state.scroll_focus == "right":
            state.scroll_r = max(0, state.scroll_r - 3)
        else:
            state.scroll_l[state.panel] = max(0, state.scroll_l[state.panel] - 1)

    @kb.add("down", eager=True, filter=is_normal)
    def _down(event):
        if state.scroll_focus == "right":
            total = _count_chat_lines(state.chat)
            state.scroll_r = min(max(0, total - 5), state.scroll_r + 3)
        else:
            mx = max(0, len(panel_lines_fn()) - 5)
            state.scroll_l[state.panel] = min(mx, state.scroll_l[state.panel] + 1)

    @kb.add("tab", filter=is_normal)
    def _toggle_pane(event):
        state.scroll_focus = "right" if state.scroll_focus == "left" else "left"

    @kb.add("c-up")
    @kb.add("pageup")
    def _scroll_chat_up(event):
        state.scroll_r = max(0, state.scroll_r - 5)

    @kb.add("c-down")
    @kb.add("pagedown")
    def _scroll_chat_down(event):
        total = _count_chat_lines(state.chat)
        state.scroll_r = min(max(0, total - 5), state.scroll_r + 5)

    @kb.add("f", filter=is_normal)
    def _toggle_focus(event):
        try:
            idx = FOCUS_CYCLE.index(state.focus_mode)
        except ValueError:
            idx = 0
        state.focus_mode = FOCUS_CYCLE[(idx + 1) % len(FOCUS_CYCLE)]
        for k in list(cache.keys()):
            del cache[k]
        building.clear()

    @kb.add("d", filter=is_normal)
    def _toggle_diff(event):
        """Toggle canvas diff/clean view in plan, review, or project modes."""
        if state.ui_mode in ("plan", "review", "project") and state.active_session:
            sess = state.active_session
            sess["canvas_diff_mode"] = not sess.get("canvas_diff_mode", True)
            event.app.invalidate()

    # ── Paste from clipboard (Ctrl+V) ──
    def _do_paste():
        import subprocess
        for cmd in (
            ["wl-paste", "--no-newline"],
            ["xclip", "-selection", "clipboard", "-o"],
            ["xsel", "--clipboard", "--output"],
        ):
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
                if r.returncode == 0 and r.stdout:
                    return r.stdout
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        return None

    @kb.add("c-v", filter=is_normal)
    def _paste_normal(event):
        state.mode = "insert"
        text = _do_paste()
        if text:
            input_buffer.insert_text(text)

    @kb.add("c-v", filter=is_insert)
    def _paste_insert(event):
        text = _do_paste()
        if text:
            input_buffer.insert_text(text)

    # ── Normal mode: enter insert ──
    @kb.add("i", filter=is_normal)
    @kb.add("/", filter=is_normal)
    def _enter_insert(event):
        state.mode = "insert"

    # ── Insert mode: back to normal ──
    @kb.add("escape", filter=is_insert)
    def _exit_insert(event):
        state.mode = "normal"

    # ── C-d: force quit always ──
    @kb.add("c-d")
    def _force_quit(event):
        stop_tick.set()
        event.app.exit()

    # ── Normal mode: Esc — exit mode if modal, else quit app ──
    @kb.add("escape", filter=is_normal)
    def _close(event):
        if state.ui_mode != "execute":
            if state.active_session:
                state.pending_exit = True
                state.chat.append({"role": "system",
                    "text": "Quit mid-session? Unsaved changes will be lost. [y/n]"})
                state.mode = "insert"
            else:
                state.ui_mode     = "execute"
                state.ui_mode_arg = None
                state.panel       = 0  # return to GPS panel
            event.app.invalidate()
        else:
            stop_tick.set()
            event.app.exit()

    @kb.add("enter", filter=is_insert)
    def _enter(event):
        text = input_buffer.text.strip()
        if not text:
            state.mode = "normal"
            return

        input_buffer.reset()
        state.mode = "normal"
        # In triage mode, align user's message to top so response flows below it.
        # In other modes, stay near bottom (standard chat feel).
        lines_before = _count_chat_lines(state.chat)
        state.chat.append({"role": "user", "text": text})
        if state.ui_mode == "triage":
            state.scroll_r = lines_before
        else:
            state.scroll_r = max(0, _count_chat_lines(state.chat) - 20)

        tl = text.lower()

        # ── Pending exit confirmation ──
        if state.pending_exit:
            state.pending_exit = False
            if tl in ("y", "yes"):
                state.active_session = None
                state.ui_mode        = "execute"
                state.ui_mode_arg    = None
                state.panel          = 0  # return to GPS panel
                state.chat.append({"role": "system", "text": "Session discarded."})
            else:
                state.chat.append({"role": "system", "text": "Continuing session."})
            event.app.invalidate()
            return

        # ── Active session: route message into it ──
        if state.active_session:
            t = threading.Thread(
                target=_continue_session,
                args=(text, state, event.app),
                daemon=True,
            )
            t.start()
            return

        # ── Approve staged plan (backwards compat) ──
        if state.staging and tl in APPROVE_KW:
            state.staging = False
            state.chat.append({"role": "system", "text": "Plan confirmed. Have a great day!"})
            event.app.invalidate()
            return

        # ── Inline relationship commands ──
        # "T-001 blocks T-002" or "T-001 serves G-001"
        m_blocks = _re_cmd.match(r"(t-\d+)\s+blocks\s+(t-\d+)", tl)
        m_serves = _re_cmd.match(r"(t-\d+)\s+serves\s+(g-\d+)", tl)
        if m_blocks:
            _handle_blocks_cmd(m_blocks.group(1).upper(), m_blocks.group(2).upper(),
                               state, event.app)
            return
        if m_serves:
            _handle_serves_cmd(m_serves.group(1).upper(), m_serves.group(2).upper(),
                               state, event.app)
            return

        # ── Slash commands ──
        if tl.startswith("/"):
            _handle_slash(text[1:], state, event.app)
            return

        # ── Free-form → general boardroom ──
        import shutil as _sh
        chat_w = max(40, int(_sh.get_terminal_size().columns * 0.4) - 4)
        threading.Thread(
            target=_run_command_bg,
            args=(text, state, event.app, chat_w),
            daemon=True,
        ).start()


# ── Modal mode helpers ────────────────────────────────────────────────────────

import re as _re_cmd


def _handle_blocks_cmd(src_seq: str, dst_seq: str, state: "_State", app: "Application") -> None:
    """Handle 'T-001 blocks T-002': add dst to src's blocks list."""
    src = storage.get_task_by_id(src_seq)
    dst = storage.get_task_by_id(dst_seq)
    if not src:
        state.chat.append({"role": "system", "text": f"Task {src_seq} not found."})
    elif not dst:
        state.chat.append({"role": "system", "text": f"Task {dst_seq} not found."})
    else:
        if dst.id not in src.blocks:
            src.blocks.append(dst.id)
            storage.save_task(src)
        state.chat.append({"role": "system",
            "text": f"{src_seq} now blocks {dst_seq}: '{src.title}' -> '{dst.title}'"})
        state.dirty = True
    app.invalidate()


def _handle_serves_cmd(task_seq: str, goal_seq: str, state: "_State", app: "Application") -> None:
    """Handle 'T-001 serves G-001': add goal to task's aligns_to list."""
    task = storage.get_task_by_id(task_seq)
    goals = storage.get_goals(active_only=False)
    goal = next((g for g in goals if g.seq_id == goal_seq or g.seq_id == goal_seq.upper()), None)
    if not task:
        state.chat.append({"role": "system", "text": f"Task {task_seq} not found."})
    elif not goal:
        state.chat.append({"role": "system", "text": f"Goal {goal_seq} not found."})
    else:
        if goal.id not in task.aligns_to:
            task.aligns_to.append(goal.id)
            storage.save_task(task)
        state.chat.append({"role": "system",
            "text": f"{task_seq} now serves {goal_seq}: '{task.title}' -> '{goal.title}'"})
        state.dirty = True
    app.invalidate()


def _exit_mode(state: "_State", app: "Application") -> None:
    """Return to execute mode, clear active session."""
    state.active_session = None
    state.ui_mode        = "execute"
    state.ui_mode_arg    = None
    state.panel          = 0  # return to GPS panel
    app.invalidate()


# ── Slash command routing ──────────────────────────────────────────────────────

def _handle_slash(cmd_str: str, state: "_State", app: "Application") -> None:
    """Route /command args to the appropriate handler."""
    parts = cmd_str.strip().split(None, 1)
    if not parts:
        state.chat.append({"role": "system", "text": (
            "Available commands:\n"
            "  /plan [day|week|quarter]   — start a planning session\n"
            "  /plan P-NNN               — project planning boardroom\n"
            "  /plan G-NNN               — goal planning boardroom\n"
            "  /review [day|week|quarter] — start a review session\n"
            "  /triage                   — process inbox items\n"
            "  /log <note>               — capture a thought or task\n"
            "  /research <topic>         — run background research\n"
            "  /clear                    — clear chat history\n"
            "  /exit                     — exit current mode or quit"
        )})
        app.invalidate()
        return
    cmd  = parts[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "clear":
        state.chat     = [{"role": "assistant", "ansi": _WELCOME_HINTS}]
        state.scroll_r = 0
        storage.save_chat_session([])
        app.invalidate()

    elif cmd == "plan":
        _slash_plan(args, state, app)

    elif cmd == "review":
        cadence = ("quarterly" if "quarter" in args
                   else "weekly"    if "week"    in args
                   else "daily")
        state.ui_mode     = "review"
        state.ui_mode_arg = cadence
        state.panel       = 0
        threading.Thread(target=_start_review_session,
                         args=(cadence, state, app), daemon=True).start()

    elif cmd == "triage":
        state.ui_mode = "triage"
        state.panel   = 0
        threading.Thread(target=_start_triage_session,
                         args=(state, app), daemon=True).start()

    elif cmd == "research":
        if args:
            job = {"topic": args, "status": "running", "elapsed": 0, "tick": 0}
            state.research.append(job)
            state.panel = 4  # Research panel
            threading.Thread(target=_run_research_bg,
                             args=(args, job, state, app), daemon=True).start()

    elif cmd in ("capture", "log"):
        state.chat.append({"role": "system", "text": f"/{cmd} — coming soon."})
        app.invalidate()

    elif cmd == "exit":
        if state.active_session:
            state.pending_exit = True
            state.chat.append({"role": "system",
                "text": "Quit mid-session? Unsaved changes will be lost. [y/n]"})
            state.mode = "insert"
            app.invalidate()
        else:
            _exit_mode(state, app)

    else:
        state.chat.append({"role": "system", "text": f"Unknown command: /{cmd}"})
        app.invalidate()


def _slash_plan(args: str, state: "_State", app: "Application") -> None:
    """Route /plan args to the right session starter."""
    al = args.lower().strip()

    # /plan P-001 → project mode
    m = _re_cmd.match(r"(p-\d+)$", al)
    if m:
        proj_id = m.group(1).upper()
        state.ui_mode     = "project"
        state.ui_mode_arg = proj_id
        state.panel       = 0
        threading.Thread(target=_start_project_plan_session,
                         args=(proj_id, state, app), daemon=True).start()
        return

    # /plan G-001 → goal mode
    m = _re_cmd.match(r"(g-\d+)$", al)
    if m:
        goal_id = m.group(1).upper()
        state.ui_mode     = "goal"
        state.ui_mode_arg = goal_id
        state.panel       = 0
        threading.Thread(target=_start_goal_plan_session,
                         args=(goal_id, state, app), daemon=True).start()
        return

    # /plan [day|week|quarter] → period plan
    scope = ("quarterly" if "quarter" in al
             else "monthly" if "month"   in al
             else "weekly"  if "week"    in al
             else "daily"   if "day"     in al
             else "weekly")
    state.ui_mode     = "plan"
    state.ui_mode_arg = scope
    state.panel       = 0
    if scope == "daily":
        threading.Thread(target=_run_plan_bg,
                         args=(state, app, 60), daemon=True).start()
    else:
        threading.Thread(target=_start_plan_session,
                         args=(scope, state, app), daemon=True).start()


# ── Canvas: parse / render ─────────────────────────────────────────────────────

def _parse_canvas_block(reply: str) -> "tuple[str, list[dict]]":
    """Split AI reply into display text and structured canvas items.

    Returns (display_text, items) where items = [{"op": "add"|"del"|"ctx", "text": ...}].
    If no PLAN_STATE: block present, returns (reply, []).
    """
    if "PLAN_STATE:" not in reply:
        return reply, []
    text_part, state_part = reply.split("PLAN_STATE:", 1)
    items: list[dict] = []
    for line in state_part.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("+"):
            items.append({"op": "add", "text": line[1:].strip()})
        elif line.startswith("-"):
            items.append({"op": "del", "text": line[1:].strip()})
        elif line.startswith("="):
            items.append({"op": "ctx", "text": line[1:].strip()})
    return text_part.strip(), items


def _canvas_diff_render(proposed: list, lines: list) -> None:
    """Render proposed canvas items with git-diff-style markers into lines."""
    for item in proposed:
        op   = item.get("op", "ctx")
        text = item.get("text", "")
        if op == "add":
            lines.append([_t("canvas.add", f"  [+] {text}")])
        elif op == "del":
            lines.append([_t("canvas.del", f"  [-] {text}")])
        else:
            lines.append([_t("dim", f"  [=] {text}")])


def _canvas_clean_render(proposed: list, lines: list) -> None:
    """Render final-state view (add + ctx only, no markers, no deletions)."""
    for item in proposed:
        op   = item.get("op", "ctx")
        text = item.get("text", "")
        if op != "del":
            lines.append([[_t("body", "    "), _t("body", text)][0]])
            lines[-1] = [_t("body", f"    {text}")]


def _build_canvas_panel(session: "dict | None") -> "list[list]":
    """Canvas panel for plan/review/project modes — collaborative working document."""
    if not session:
        return [[_t("dim", "  No active session.")]]

    proposed  = session.get("canvas_proposed", [])
    diff_mode = session.get("canvas_diff_mode", True)
    stype     = session.get("type", "")
    scope     = session.get("scope") or session.get("cadence") or session.get("project_id", "")

    lines: list[list] = []

    # Header
    label = {
        "plan":         f"Draft  ({scope})",
        "review":       f"Session  ({scope})",
        "project_plan": f"Scope  ({scope})",
    }.get(stype, scope or stype)
    lines.append([_t("label", f"  {label.upper()}")])
    lines.append(_div())

    if not proposed:
        lines.append([_t("dim", "  Conversation in progress — canvas will update as plan develops.")])
        lines.append([_t("dim", "  Items appear here when the AI proposes changes.")])
    elif diff_mode:
        _canvas_diff_render(proposed, lines)
    else:
        _canvas_clean_render(proposed, lines)

    lines.append(_blank())
    view_label = "diff" if diff_mode else "clean"
    lines.append([_t("dim", f"  ── d: toggle view ({view_label}) ─────────────────")])
    return lines


# ── Plan mode: Agenda + Context panels ────────────────────────────────────────

def _build_plan_agenda(scope: str, focus: str) -> "list[list]":
    """Plan mode Agenda panel — what to process at plan time."""
    lines: list[list] = []

    def L(tok): lines.append([tok])
    def B():    lines.append(_blank())

    L(_t("label", f"  AGENDA  ({scope.upper()})"))
    lines.append(_div())

    try:
        triage_items = [t for t in storage.get_triage() if not t.processed]
        if triage_items:
            L(_t("label", f"  TRIAGE  ({len(triage_items)} pending)"))
            for ti in triage_items[:8]:
                L(_t("body", f"  · {ti.content[:50]}"))
            if len(triage_items) > 8:
                L(_t("dim", f"    … {len(triage_items) - 8} more"))
            B()
    except Exception:
        pass

    if scope in ("weekly", "quarterly"):
        try:
            goals = storage.get_goals()
            active = [g for g in goals if g.status == "active"]
            if active:
                L(_t("label", f"  GOALS  ({len(active)} active)"))
                for g in active[:5]:
                    pct = getattr(g, "progress", 0) or 0
                    filled = int(pct / 10)
                    bar = "█" * filled + "░" * (10 - filled)
                    L(_t("body", f"  {getattr(g, 'seq_id', '') or '─'}  {g.title[:28]}"))
                    L(_t("dim",  f"     {bar}  {pct:.0f}%"))
                B()
        except Exception:
            pass

    try:
        today = date.today()
        if scope == "daily":
            tasks = [t for t in storage.get_tasks(include_habits=False)
                     if not t.is_done and (not t.due or t.due <= today.isoformat())]
        else:
            tasks = [t for t in storage.get_tasks(include_habits=False) if not t.is_done]
        tasks = tasks[:10]
        if tasks:
            L(_t("label", "  OPEN TASKS"))
            for t in tasks:
                due_tag = f"  {t.due}" if t.due else ""
                overdue = t.due and t.due < today.isoformat()
                sty = "overdue" if overdue else "body"
                L(_t(sty, f"  {getattr(t, 'seq_id', '') or '·'}  {t.title[:40]}{due_tag}"))
            B()
    except Exception:
        pass

    return lines


def _build_plan_context_mode(scope: str, focus: str) -> "list[list]":
    """Plan mode Context panel — season, goals, values, dimensions, constraints."""
    lines: list[list] = []

    def L(tok): lines.append([tok])
    def B():    lines.append(_blank())

    L(_t("label", f"  CONTEXT  ({scope.upper()})"))
    lines.append(_div())

    # ── 1. Season ──
    try:
        cfg = storage.load_config()
        if cfg.season:
            s = cfg.season
            focus_val = s.focus.value if hasattr(s.focus, "value") else str(s.focus)
            L(_t("label", "  SEASON"))
            L(_t("body",  f"  {s.name}"))
            L(_t("dim",   f"  Focus: {focus_val}"))
            drift = storage.get_season_drift(cfg)
            if drift:
                L(_t("warn", f"  ⚠ {drift[:56]}"))
            B()
    except Exception:
        pass

    # ── 2. Goals ──
    if scope in ("weekly", "quarterly"):
        try:
            active_goals = storage.get_goals(active_only=True)
            active_goals = [g for g in active_goals if not g.is_pseudo]
            if active_goals:
                L(_t("label", f"  GOALS  ({len(active_goals)} active)"))
                for g in active_goals[:7]:
                    sid = g.seq_id or "—"
                    dim = g.dimension.value if hasattr(g.dimension, "value") else str(g.dimension)
                    L(_t("body", f"  {sid}  {g.title[:36]}"))
                    L(_t("dim",  f"      [{dim}]"))
                B()
        except Exception:
            pass

    # ── 3. Values / Prayer ──
    try:
        values = storage.load_values()
        if values.get("prayer"):
            L(_t("label", "  VALUES / PRAYER"))
            for line in values["prayer"].strip().splitlines()[:4]:
                if line.strip():
                    L(_t("dim", f"  {line.strip()[:58]}"))
            B()
    except Exception:
        pass

    # ── 4. Dimension balance ──
    try:
        dim_scores = storage.get_avg_dimension_scores(days=14)
        if dim_scores:
            L(_t("label", "  DIMENSIONS  (14-day avg)"))
            dim_scores.sort(key=lambda x: x.get("score", 0), reverse=True)
            for ds in dim_scores:
                d     = ds.get("dimension", "")
                score = ds.get("score", 0)
                bar   = "█" * int(score / 10) + "░" * (10 - int(score / 10))
                sty   = "done" if score >= 7 else ("warn" if score >= 4 else "dim")
                L(_t(sty, f"  {d:<14}  {bar}  {score:.1f}"))
            B()
    except Exception:
        pass

    # ── 5. Constraints ──
    try:
        values = storage.load_values()
        constraints = values.get("constraints", [])
        if not constraints:
            # Fall back to config-level constraints if any
            cfg = storage.load_config()
            constraints = getattr(cfg, "constraints", []) or []
        if constraints:
            L(_t("label", "  CONSTRAINTS"))
            if isinstance(constraints, str):
                constraints = [constraints]
            for c in constraints[:6]:
                L(_t("dim", f"  · {str(c)[:56]}"))
            B()
    except Exception:
        pass

    # ── Parent plan (for daily/weekly only) ──
    try:
        parent_scope = {"daily": "weekly", "weekly": "quarterly"}.get(scope, "")
        if parent_scope:
            parent_plan = storage.load_plan(parent_scope)
            if parent_plan.get("proposal"):
                L(_t("label", f"  {parent_scope.upper()} PLAN  (parent context)"))
                for line in parent_plan["proposal"].splitlines()[:5]:
                    L(_t("dim", f"  {line[:56]}"))
                B()
    except Exception:
        pass

    return lines


# ── Plan mode: Combined Strategy panel (inline — built with live session) ─────

def _wrap_text(text: str, width: int, indent: str = "  ") -> "list[str]":
    """Word-wrap text to width, returning lines with indent prefix."""
    import textwrap
    wrapped = textwrap.fill(text.strip(), width=width - len(indent),
                            break_long_words=True, break_on_hyphens=False)
    return [indent + ln for ln in wrapped.splitlines()] if wrapped else []


def _build_strategy_panel(session: "dict | None", state: "_State") -> "list[list]":
    """
    Combined Strategy panel for plan mode:
      Prayer → Season → Canvas diff/clean → Active goals+projects → Backlog
    Built inline (live canvas data + stored goals).
    """
    lines: list[list] = []

    def L(*toks):        lines.append(list(toks))
    def B():             lines.append(_blank())
    def Lw(sty, text, width=54, indent="  "):
        for ln in _wrap_text(text, width, indent):
            lines.append([_t(sty, ln)])

    scope = (session or {}).get("scope", "quarterly")
    L(_t("label", f"  STRATEGY  ({scope.upper()})"))
    lines.append(_div())

    # ── Prayer ──────────────────────────────────────────────────────────────
    try:
        values = storage.load_values()
        prayer = values.get("prayer", "").strip()
        if prayer:
            for line in prayer.splitlines()[:5]:
                if line.strip():
                    Lw("dim", line.strip(), width=56)
            B()
    except Exception:
        pass

    # ── Season ──────────────────────────────────────────────────────────────
    try:
        cfg = storage.load_config()
        if cfg.season:
            s = cfg.season
            focus_val = s.focus.value if hasattr(s.focus, "value") else str(s.focus)
            L(_t("label", "  SEASON"))
            L(_t("body",  f"  {s.name}  ·  {focus_val}"))
            drift = storage.get_season_drift(cfg)
            if drift:
                L(_t("warn", f"  ⚠ {drift[:54]}"))
            B()
    except Exception:
        pass

    # ── Canvas (plan draft diff) ─────────────────────────────────────────────
    if session:
        proposed  = session.get("canvas_proposed", [])
        diff_mode = session.get("canvas_diff_mode", True)
        if proposed:
            L(_t("label", "  PLAN DRAFT"))
            if diff_mode:
                _canvas_diff_render(proposed, lines)
            else:
                _canvas_clean_render(proposed, lines)
            L(_t("dim", "  ── d: toggle diff/clean ──────────────"))
            B()

    # ── Active goals + projects ──────────────────────────────────────────────
    try:
        all_goals    = storage.get_goals(active_only=False)
        all_projects = storage.get_projects()

        def _goal_dim(g) -> str:
            return g.dimension.value if hasattr(g.dimension, "value") else str(g.dimension)

        active = [g for g in all_goals if g.is_active and not g.is_pseudo]
        if active:
            L(_t("accent", f"  ACTIVE GOALS  ({len(active)})"))
            lines.append(_div())
            for g in active:
                dim = _goal_dim(g)
                sid = g.seq_id or "—"
                L(_t("body", f"  {sid}  "), _t("body", f"{g.title}  "), _t("dim", f"[{dim}]"))
                linked = [p for p in all_projects if p.goal_id == g.id]
                if linked:
                    from viyugam.models import ProjectStatus
                    for p in linked[:5]:
                        p_sid   = p.seq_id or "·"
                        sty     = "done" if p.status == ProjectStatus.COMPLETED else (
                                  "dim"  if p.status in (ProjectStatus.PAUSED,
                                                         ProjectStatus.ICEBOX) else "body")
                        status  = p.status.value if hasattr(p.status, "value") else str(p.status)
                        L(_t(sty, f"    {p_sid}  "), _t(sty, f"{p.title}  "), _t("dim", f"[{status}]"))
                else:
                    L(_t("dim", "    (no linked projects)"))
                B()

        backlog = [g for g in all_goals if not g.is_active and not g.is_pseudo]
        if backlog:
            lines.append(_div())
            L(_t("dim", f"  BACKLOG  ({len(backlog)})"))
            lines.append(_div())
            for g in backlog[:6]:
                dim = _goal_dim(g)
                sid = g.seq_id or "—"
                L(_t("dim", f"  {sid}  {g.title}  [{dim}]"))
                linked = [p for p in all_projects if p.goal_id == g.id]
                for p in linked[:3]:
                    p_sid = p.seq_id or "·"
                    L(_t("dim", f"    {p_sid}  {p.title}"))
                if linked:
                    B()
    except Exception as exc:
        L(_t("dim", f"  (goals unavailable: {exc})"))

    return lines


# ── Plan mode: Strategic View panel ──────────────────────────────────────────

def _build_plan_strategic(scope: str, focus: str) -> "list[list]":
    """
    Plan mode Strategic panel — two sections:
      Section 1: Active goals and their linked projects (with dimension).
      Section 2: Backlog (inactive) goals and their linked projects.
    """
    lines: list[list] = []

    def L(tok): lines.append([tok])
    def B():    lines.append(_blank())

    L(_t("label", f"  STRATEGIC VIEW  ({scope.upper()})"))
    lines.append(_div())

    try:
        all_goals    = storage.get_goals(active_only=False)
        all_projects = storage.get_projects()
    except Exception:
        L(_t("dim", "  Could not load goals."))
        return lines

    def _goal_dim(g) -> str:
        return g.dimension.value if hasattr(g.dimension, "value") else str(g.dimension)

    def _proj_line(p) -> None:
        sid   = p.seq_id or "·"
        title = p.title[:38]
        from viyugam.models import ProjectStatus
        sty   = "done" if p.status == ProjectStatus.COMPLETED else (
                "dim"  if p.status in (ProjectStatus.PAUSED, ProjectStatus.ICEBOX) else "body")
        status_tag = f"  [{p.status.value if hasattr(p.status, 'value') else p.status}]"
        L(_t(sty, f"    {sid}  {title}{status_tag}"))

    # ── Section 1: Active goals ────────────────────────────────────────────────
    active = [g for g in all_goals if g.is_active and not g.is_pseudo]
    if active:
        L(_t("accent", f"  ACTIVE  ({len(active)})"))
        lines.append(_div())
        for g in active:
            dim   = _goal_dim(g)
            sid   = g.seq_id or "—"
            L(_t("body", f"  {sid}  {g.title[:40]}"))
            L(_t("dim",  f"      [{dim}]"))

            linked = [p for p in all_projects if p.goal_id == g.id]
            if linked:
                for p in linked[:4]:
                    _proj_line(p)
            else:
                L(_t("dim", "    (no linked projects)"))
            B()
    else:
        L(_t("dim", "  No active goals."))
        B()

    # ── Section 2: Backlog goals ───────────────────────────────────────────────
    backlog = [g for g in all_goals if not g.is_active and not g.is_pseudo]
    if backlog:
        lines.append(_div())
        L(_t("dim", f"  BACKLOG  ({len(backlog)})"))
        lines.append(_div())
        for g in backlog[:8]:
            dim = _goal_dim(g)
            sid = g.seq_id or "—"
            L(_t("dim", f"  {sid}  {g.title[:40]}"))
            L(_t("dim", f"      [{dim}]"))

            linked = [p for p in all_projects if p.goal_id == g.id]
            if linked:
                for p in linked[:3]:
                    p_sid   = p.seq_id or "·"
                    p_title = p.title[:36]
                    L(_t("dim", f"    {p_sid}  {p_title}"))
            B()

    return lines


# ── Review mode: Activity + Captures panels ───────────────────────────────────

def _build_rev_activity(scope: str, focus: str) -> "list[list]":
    """Review mode Activity panel — completions, progress, energy."""
    lines: list[list] = []

    def L(tok): lines.append([tok])
    def B():    lines.append(_blank())

    L(_t("label", f"  ACTIVITY  ({scope.upper()})"))
    lines.append(_div())

    try:
        today = date.today()
        lookback = {"daily": 1, "weekly": 7, "quarterly": 90}.get(scope, 7)
        since = (today - __import__("datetime").timedelta(days=lookback)).isoformat()

        tasks = storage.get_tasks(include_habits=False)
        done_tasks = [t for t in tasks if t.is_done
                      and (t.done_at or "") >= since]

        if done_tasks:
            L(_t("label", f"  COMPLETED  ({len(done_tasks)})"))
            # Group by project
            by_proj: dict[str, list] = {}
            for t in done_tasks[:20]:
                pid = t.project_id or "__none__"
                by_proj.setdefault(pid, []).append(t)
            projects = {p.id: p for p in storage.get_projects()}
            for pid, proj_tasks in sorted(by_proj.items(), key=lambda x: -len(x[1]))[:5]:
                proj = projects.get(pid)
                proj_name = proj.title[:24] if proj else "No project"
                L(_t("done", f"  ✓ {proj_name}  ({len(proj_tasks)})"))
                for t in proj_tasks[:3]:
                    L(_t("dim", f"    · {t.title[:40]}"))
            B()
        else:
            L(_t("dim", f"  No tasks completed in the last {lookback} day(s)."))
            B()
    except Exception:
        pass

    try:
        projects = [p for p in storage.get_projects() if p.status == "active"]
        if projects:
            L(_t("label", "  PROJECT PROGRESS"))
            for p in projects[:5]:
                pct = getattr(p, "progress", 0) or 0
                filled = int(pct / 10)
                bar = "█" * filled + "░" * (10 - filled)
                L(_t("body", f"  {getattr(p, 'seq_id', '') or '·'}  {p.title[:26]}"))
                L(_t("dim",  f"     {bar}  {pct:.0f}%"))
            B()
    except Exception:
        pass

    return lines


def _build_rev_captures(scope: str, focus: str) -> "list[list]":
    """Review mode Captures panel — new triage items surfaced during review."""
    lines: list[list] = []

    def L(tok): lines.append([tok])
    def B():    lines.append(_blank())

    L(_t("label", f"  CAPTURES  ({scope.upper()})"))
    lines.append(_div())

    try:
        triage_items = storage.get_triage()
        unprocessed  = [t for t in triage_items if not t.processed]
        recent_raw   = sorted(
            unprocessed,
            key=lambda x: x.created_at or "",
            reverse=True,
        )[:10]

        if recent_raw:
            L(_t("label", f"  TRIAGE INBOX  ({len(unprocessed)} pending)"))
            for ti in recent_raw:
                L(_t("body", f"  · {ti.content[:52]}"))
                if ti.boardroom_notes:
                    L(_t("dim", f"    {ti.boardroom_notes[:50]}"))
            B()
        else:
            L(_t("dim", "  Inbox is clear."))
            B()
    except Exception:
        pass

    try:
        today = date.today()
        lookback = {"daily": 1, "weekly": 7, "quarterly": 90}.get(scope, 7)
        since = (today - __import__("datetime").timedelta(days=lookback)).isoformat()
        all_triage = storage.get_triage(unprocessed_only=False)
        new_ones   = [t for t in all_triage if (t.created_at or "") >= since]
        if new_ones:
            L(_t("label", f"  CAPTURED THIS {scope.upper()}  ({len(new_ones)})"))
            for ti in new_ones[:8]:
                sty = "done" if ti.processed else "body"
                L(_t(sty, f"  {'✓' if ti.processed else '·'} {ti.content[:52]}"))
            B()
    except Exception:
        pass

    return lines


# ── Phase 3: project mode panels ─────────────────────────────────────────────

def _build_proj_scope(project_id: str, focus: str) -> "list[list]":
    """Project Scope panel — scope, milestones, success criteria, out-of-scope, notes."""
    lines: list[list] = []

    def L(tok): lines.append([tok])
    def B():    lines.append(_blank())

    try:
        project = next(
            (p for p in storage.get_projects()
             if p.seq_id == project_id or p.id == project_id), None
        )
    except Exception:
        project = None

    if not project:
        L(_t("dim", f"  Project {project_id} not found."))
        return lines

    # Header
    status_tag = f"[{project.status}]" if project.status else ""
    L(_t("accent", f"  {project.seq_id or project_id}  {project.title[:36]}"))
    lines.append([
        _t("dim", f"  {status_tag}"),
        _t("dim", f"  dim:{project.dimension or '—'}"),
        _t("dim", f"  {'  ' + project.deadline if project.deadline else ''}"),
    ])
    lines.append(_div())
    B()

    # Linked goal
    try:
        goals = storage.get_goals()
        linked = next((g for g in goals if g.id == project.goal_id), None) if project.goal_id else None
        if linked:
            L(_t("dim", f"  Goal: {linked.seq_id or '—'}  {linked.title[:36]}"))
            B()
    except Exception:
        pass

    # Budget
    if project.budget_cap:
        L(_t("dim", f"  Budget cap: \u20b9{project.budget_cap:,.0f}"))
        B()

    # Scope
    L(_t("label", "  SCOPE"))
    try:
        plan = storage.get_project_plan(project.id)
    except Exception:
        plan = None

    if plan and plan.scope_md:
        for line in plan.scope_md[:400].split("\n")[:5]:
            if line.strip():
                L(_t("body", f"  {line.strip()[:56]}"))
    elif project.description:
        L(_t("body", f"  {project.description[:200]}"))
    else:
        L(_t("dim", "  No scope defined yet."))
    B()

    # Milestones
    try:
        milestones = storage.get_milestones(project_id=project.id)
        if milestones:
            L(_t("label", "  MILESTONES"))
            for m in sorted(milestones, key=lambda x: x.due_date or "9999")[:6]:
                mark = "\u2713" if m.is_done else ("\u2192" if not m.is_done else "\u00b7")
                sty  = "done" if m.is_done else "body"
                date_str = f"  {m.due_date}" if m.due_date else ""
                L(_t(sty, f"  {mark}  {m.title[:36]}{date_str}"))
            B()
    except Exception:
        pass

    # Success criteria
    if plan and plan.success_criteria:
        L(_t("label", "  SUCCESS CRITERIA"))
        for c in plan.success_criteria[:4]:
            L(_t("dim", f"  \u00b7  {c[:52]}"))
        B()

    # Out of scope
    if plan and plan.out_of_scope:
        L(_t("label", "  OUT OF SCOPE"))
        for c in plan.out_of_scope[:3]:
            L(_t("dim", f"  \u00d7  {c[:52]}"))
        B()

    # Notes/risks
    if plan and plan.notes:
        L(_t("label", "  NOTES / RISKS"))
        for line in plan.notes[:200].split("\n")[:3]:
            if line.strip():
                L(_t("dim", f"  {line.strip()[:56]}"))
        B()

    return lines


def _build_proj_tasks(project_id: str, focus: str) -> "list[list]":
    """Project Tasks panel — this week, backlog, done."""
    lines: list[list] = []

    def L(tok): lines.append([tok])
    def B():    lines.append(_blank())

    try:
        project = next(
            (p for p in storage.get_projects()
             if p.seq_id == project_id or p.id == project_id), None
        )
        if not project:
            L(_t("dim", f"  Project {project_id} not found."))
            return lines

        tasks = storage.get_tasks(project_id=project.id, include_habits=False)
        today = date.today()
        week_end = (today + __import__("datetime").timedelta(days=7)).isoformat()

        week_tasks = [t for t in tasks if not t.is_done
                      and t.due and t.due <= week_end]
        backlog    = [t for t in tasks if not t.is_done
                      and (not t.due or t.due > week_end)]
        done       = sorted(
            [t for t in tasks if t.is_done],
            key=lambda x: x.done_at or "", reverse=True
        )

        L(_t("label", f"  {project.seq_id or project_id}  TASKS"))
        lines.append(_div())

        if week_tasks:
            L(_t("label", f"  THIS WEEK  ({len(week_tasks)})"))
            for t in week_tasks[:8]:
                overdue = t.due and t.due < today.isoformat()
                sty = "overdue" if overdue else "todo"
                L(_t(sty, f"  {t.seq_id or '·'}  {t.title[:42]}  [{t.status or 'todo'}]"))
            B()

        if backlog:
            L(_t("label", f"  BACKLOG  ({len(backlog)})"))
            for t in backlog[:6]:
                L(_t("dim", f"  {t.seq_id or '·'}  {t.title[:44]}"))
            if len(backlog) > 6:
                L(_t("dim", f"    … {len(backlog) - 6} more"))
            B()

        if done:
            L(_t("label", f"  DONE  ({len(done)})"))
            for t in done[:5]:
                date_str = f"  {(t.done_at or '')[:10]}" if t.done_at else ""
                L(_t("done", f"  {t.seq_id or '·'}  {t.title[:42]}\u2713{date_str}"))
            B()

        if not tasks:
            L(_t("dim", "  No tasks for this project yet."))

    except Exception as exc:
        L(_t("overdue", f"  Error: {exc}"))

    return lines


def _build_proj_context(project_id: str, focus: str) -> "list[list]":
    """Project Context panel — linked goal, effort allocation, OKRs, competing projects."""
    lines: list[list] = []

    def L(tok): lines.append([tok])
    def B():    lines.append(_blank())

    try:
        projects = storage.get_projects()
        project  = next(
            (p for p in projects if p.seq_id == project_id or p.id == project_id), None
        )
        if not project:
            L(_t("dim", f"  Project {project_id} not found."))
            return lines

        L(_t("label", f"  CONTEXT  {project.seq_id or project_id}"))
        lines.append(_div())

        # Linked goal
        if project.goal_id:
            try:
                goals = storage.get_goals()
                linked = next((g for g in goals if g.id == project.goal_id), None)
                if linked:
                    L(_t("label", "  LINKED GOAL"))
                    pct = getattr(linked, "progress", 0) or 0
                    filled = int(pct / 10)
                    bar = "█" * filled + "░" * (10 - filled)
                    L(_t("body",  f"  {linked.seq_id or '—'}  {linked.title[:34]}  [{linked.status}]"))
                    L(_t("dim",   f"  Progress: {pct:.0f}%  {bar}"))
                    if linked.deadline:
                        L(_t("dim", f"  Deadline: {linked.deadline}"))
                    B()
            except Exception:
                pass

        # Effort allocation (task count ratio)
        try:
            all_tasks     = storage.get_tasks(include_habits=False)
            today         = date.today()
            week_end      = (today + __import__("datetime").timedelta(days=7)).isoformat()
            week_all      = [t for t in all_tasks if not t.is_done
                             and t.due and t.due <= week_end]
            week_this     = [t for t in week_all if t.project_id == project.id]
            total_active  = [t for t in all_tasks if not t.is_done]
            proj_active   = [t for t in total_active if t.project_id == project.id]

            L(_t("label", "  EFFORT ALLOCATION"))
            if week_all:
                pct_week = len(week_this) / len(week_all) * 100
                bar_w = int(pct_week / 10)
                L(_t("body", f"  This week:  {len(week_this)} tasks  "
                              f"{'█' * bar_w}{'░' * (10 - bar_w)}  {pct_week:.0f}%"))
            if total_active:
                pct_all = len(proj_active) / len(total_active) * 100
                bar_a = int(pct_all / 10)
                L(_t("dim", f"  All active: {len(proj_active)} of {len(total_active)} tasks  "
                             f"{'█' * bar_a}{'░' * (10 - bar_a)}  {pct_all:.0f}%"))
            B()
        except Exception:
            pass

        # Active OKRs for this dimension
        try:
            if project.dimension:
                okrs = storage.get_okrs(active_only=True)
                dim_okrs = [o for o in okrs
                            if getattr(o, "dimension", "") == project.dimension]
                if dim_okrs:
                    L(_t("label", f"  ACTIVE OKRs  ({project.dimension})"))
                    for o in dim_okrs[:3]:
                        obj = getattr(o, "objective", getattr(o, "title", ""))[:40]
                        L(_t("body", f"  {obj}"))
                        for kr in (getattr(o, "key_results", []) or [])[:2]:
                            kr_text = kr.get("text", "")[:38] if isinstance(kr, dict) else str(kr)[:38]
                            L(_t("dim", f"    KR: {kr_text}"))
                    B()
        except Exception:
            pass

        # Competing projects (same dimension)
        try:
            competing = [p for p in projects
                         if p.id != project.id
                         and p.status == "active"
                         and p.dimension == project.dimension]
            if competing:
                L(_t("label", "  COMPETING PROJECTS"))
                for cp in competing[:4]:
                    dims = f"{cp.dimension or '—'}"
                    pct  = getattr(cp, "progress", 0) or 0
                    L(_t("dim", f"  {cp.seq_id or '·'}  {cp.title[:30]}  {dims}  {pct:.0f}%"))
                B()
        except Exception:
            pass

    except Exception as exc:
        lines.append([_t("overdue", f"  Error: {exc}")])

    return lines


# ── Phase 3b: goal mode panels + session ─────────────────────────────────────

def _start_goal_plan_session(goal_id: str, state: "_State",
                              app: "Application") -> None:
    """Start a goal planning boardroom session. Runs in a bg thread."""
    state.running = True
    app.invalidate()
    try:
        from viyugam.agents.goal_planner import start_goal_plan_session
        goals = storage.get_goals(active_only=False)
        goal  = next(
            (g for g in goals if g.seq_id == goal_id or g.id == goal_id), None
        )
        if not goal:
            _session_chat("system", f"Goal not found: {goal_id}", state, app)
            _exit_mode(state, app)
            return

        projects = storage.get_projects()
        okrs     = storage.get_okrs(active_only=True)
        values   = storage.load_values()
        dim_okrs = [o for o in okrs if o.dimension == goal.dimension]

        opening = start_goal_plan_session(
            goal=goal.model_dump(),
            existing_okrs=[o.model_dump() for o in dim_okrs],
            projects=[p.model_dump() for p in projects],
            values=values,
        )
        history = [{"role": "assistant", "content": opening}]

        state.active_session = {
            "type":             "goal_plan",
            "goal_id":          goal.id,
            "goal":             goal.model_dump(),
            "history":          history,
            "canvas_before":    [],
            "canvas_proposed":  [],
            "canvas_diff_mode": True,
        }
        state.ui_mode     = "goal"
        state.ui_mode_arg = goal.seq_id or goal.id
        state.panel       = 0   # OKRs panel (canvas while session active)
        _session_chat("section",
                      f"── {goal.seq_id or 'GOAL'}: {goal.title[:36]} ──",
                      state, app)
        _session_chat("assistant", opening, state, app)
        _session_chat("system",
                      "Refine OKRs and success criteria. Say 'save' or 'done' to finish.",
                      state, app)
    except Exception as exc:
        state.active_session = None
        _session_chat("system", f"Could not start goal planning: {exc}", state, app)
        _exit_mode(state, app)
    finally:
        state.running = False
        app.invalidate()


def _goal_plan_turn(text: str, tl: str, session: dict, state: "_State",
                    app: "Application") -> None:
    """Handle one turn of the goal planning conversation."""
    from viyugam.agents.goal_planner import goal_plan_turn

    history = session.get("history", [])
    history.append({"role": "user", "content": text})

    reply, is_done = goal_plan_turn(history, text, session["goal"])
    history.append({"role": "assistant", "content": reply})
    session["history"] = history

    display_text, canvas_items = _parse_canvas_block(reply)
    if canvas_items:
        session["canvas_proposed"] = canvas_items
    _session_chat("assistant", display_text or reply, state, app)

    if is_done:
        _session_chat("system", "\u2713 Goal plan captured.", state, app)
        _exit_mode(state, app)


def _build_goal_okrs(goal_id: str, focus: str) -> "list[list]":
    """Goal OKRs panel — objective, key results, success criteria."""
    lines: list[list] = []

    def L(tok): lines.append([tok])
    def B():    lines.append(_blank())

    try:
        goals = storage.get_goals(active_only=False)
        goal  = next((g for g in goals if g.seq_id == goal_id or g.id == goal_id), None)
    except Exception:
        goal = None

    if not goal:
        L(_t("dim", f"  Goal {goal_id} not found."))
        return lines

    L(_t("accent", f"  {goal.seq_id or goal_id}  {goal.title[:40]}"))
    lines.append([
        _t("dim", f"  dim:{goal.dimension or '—'}"),
        _t("dim", f"  {'[inactive]' if not goal.is_active else '[active]'}"),
    ])
    lines.append(_div())
    B()

    if goal.description:
        L(_t("body", f"  {goal.description[:200]}"))
        B()

    try:
        okrs     = storage.get_okrs(active_only=True)
        dim_okrs = [o for o in okrs if o.dimension == goal.dimension]
        if dim_okrs:
            L(_t("label", "  KEY RESULTS"))
            for o in dim_okrs[:4]:
                L(_t("body", f"  [{o.quarter}]  {o.objective[:44]}"))
                for kr in (o.key_results or [])[:4]:
                    kr_text = kr.text[:44] if hasattr(kr, "text") else str(kr)[:44]
                    is_done = kr.is_done if hasattr(kr, "is_done") else False
                    mark = "\u2713" if is_done else "\u00b7"
                    L(_t("done" if is_done else "dim", f"    {mark}  {kr_text}"))
            B()
        else:
            L(_t("dim", f"  No OKRs defined for '{goal.dimension}' dimension."))
            L(_t("dim", "  Use /plan G-NNN to start a planning session."))
            B()
    except Exception:
        pass

    return lines


def _build_goal_projects(goal_id: str, focus: str) -> "list[list]":
    """Goal Projects panel — projects linked to this goal."""
    lines: list[list] = []

    def L(tok): lines.append([tok])
    def B():    lines.append(_blank())

    try:
        goals = storage.get_goals(active_only=False)
        goal  = next((g for g in goals if g.seq_id == goal_id or g.id == goal_id), None)
    except Exception:
        goal = None

    if not goal:
        L(_t("dim", f"  Goal {goal_id} not found."))
        return lines

    L(_t("label", f"  PROJECTS  {goal.seq_id or goal_id}"))
    lines.append(_div())
    B()

    try:
        projects  = storage.get_projects()
        linked    = [p for p in projects if p.goal_id == goal.id]
        active    = [p for p in linked if p.status == "active"]
        planned   = [p for p in linked if p.status not in ("active", "done")]
        all_tasks = storage.get_tasks(include_habits=False)
        today     = date.today()
        week_end  = (today + __import__("datetime").timedelta(days=7)).isoformat()

        if active:
            L(_t("label", f"  ACTIVE  ({len(active)})"))
            for p in active[:6]:
                pct    = getattr(p, "progress", 0) or 0
                filled = int(pct / 10)
                bar    = "█" * filled + "░" * (10 - filled)
                wk     = [t for t in all_tasks if t.project_id == p.id
                          and not t.is_done and t.due and t.due <= week_end]
                L(_t("body", f"  {p.seq_id or '·'}  {p.title[:30]}"))
                L(_t("dim",  f"     {bar}  {pct:.0f}%   {len(wk)} tasks this week"))
            B()

        if planned:
            L(_t("label", f"  PLANNED  ({len(planned)})"))
            for p in planned[:4]:
                L(_t("dim", f"  {p.seq_id or '·'}  {p.title[:40]}"))
            B()

        if not linked:
            L(_t("dim", "  No projects linked to this goal yet."))
            B()

        goal_tasks  = [t for t in all_tasks
                       if t.project_id in {p.id for p in linked} and not t.is_done]
        total_open  = [t for t in all_tasks if not t.is_done]
        if total_open:
            pct_load = len(goal_tasks) / len(total_open) * 100
            L(_t("dim", f"  Goal share of open tasks: {len(goal_tasks)}"
                        f" / {len(total_open)}  {pct_load:.0f}%"))
            B()

    except Exception as exc:
        L(_t("overdue", f"  Error: {exc}"))

    return lines


def _build_goal_alignment(goal_id: str, focus: str) -> "list[list]":
    """Goal Alignment panel — values connection, seasonal context, competing goals."""
    lines: list[list] = []

    def L(tok): lines.append([tok])
    def B():    lines.append(_blank())

    try:
        goals = storage.get_goals(active_only=False)
        goal  = next((g for g in goals if g.seq_id == goal_id or g.id == goal_id), None)
    except Exception:
        goal = None

    if not goal:
        L(_t("dim", f"  Goal {goal_id} not found."))
        return lines

    L(_t("label", f"  ALIGNMENT  {goal.seq_id or goal_id}"))
    lines.append(_div())
    B()

    try:
        values = storage.load_values()
        if values.get("prayer"):
            L(_t("label", "  VALUES CONNECTION"))
            L(_t("dim", f"  {values['prayer'][:120]}"))
            B()
    except Exception:
        pass

    try:
        config    = storage.load_config()
        season    = config.get("season", {}) if isinstance(config, dict) else {}
        if season:
            focus_dim = season.get("focus", "")
            aligned   = focus_dim == goal.dimension
            L(_t("label", "  SEASONAL CONTEXT"))
            L(_t("body",  f"  Season: {season.get('name', '—')}"))
            L(_t("body",  f"  Focus: {focus_dim}  Secondary: {season.get('secondary', '—')}"))
            L(_t("done" if aligned else "dim",
                 f"  OKR alignment: {'✓ well-aligned' if aligned else '⚠ not the season focus'}"))
            B()
    except Exception:
        pass

    try:
        all_goals = storage.get_goals(active_only=True)
        competing = [g for g in all_goals if g.id != goal.id and not g.is_pseudo]
        if competing:
            L(_t("label", "  OTHER ACTIVE GOALS"))
            all_tasks = storage.get_tasks(include_habits=False)
            all_projs = storage.get_projects()
            today     = date.today()
            week_end  = (today + __import__("datetime").timedelta(days=7)).isoformat()
            for g in competing[:4]:
                g_projs  = {p.id for p in all_projs if p.goal_id == g.id}
                wk_tasks = [t for t in all_tasks if t.project_id in g_projs
                            and not t.is_done and t.due and t.due <= week_end]
                L(_t("dim", f"  {g.seq_id or '·'}  {g.title[:32]}"
                            f"  {g.dimension or '—'}  {len(wk_tasks)}/wk"))
            B()
    except Exception:
        pass

    return lines


# ── Phase 4: triage mode ──────────────────────────────────────────────────────

def _start_triage_session(state: "_State", app: "Application") -> None:
    """Load unprocessed triage items and open triage mode."""
    state.running = True
    app.invalidate()
    try:
        items = [t for t in storage.get_triage() if not t.processed]
        if not items:
            _session_chat("system", "Inbox is clear — nothing to triage.", state, app)
            _exit_mode(state, app)
            return

        state.active_session = {
            "type":          "triage",
            "items":         [t.model_dump() for t in items],
            "current_idx":   0,
            "processed":     [],
            "debate_active": False,
        }
        state.ui_mode = "triage"
        state.panel   = 0
        _triage_show_current(state.active_session, state, app)
    except Exception as exc:
        _session_chat("system", f"Could not start triage: {exc}", state, app)
        _exit_mode(state, app)
    finally:
        state.running = False
        app.invalidate()


def _triage_show_current(session: dict, state: "_State", app: "Application") -> None:
    """Display the current triage item prompt."""
    items = session.get("items", [])
    idx   = session.get("current_idx", 0)
    if idx >= len(items):
        done_count = len(session.get("processed", []))
        _session_chat("system",
            f"\u2713 Triage complete — {done_count} item(s) processed.", state, app)
        _exit_mode(state, app)
        return

    item      = items[idx]
    remaining = len(items) - idx
    content   = item.get("content", "")
    captured  = (item.get("created_at") or "")[:10]

    _session_chat("system", (
        f"{remaining} item(s) to triage.\n\n"
        f"{'─' * 44}\n"
        f"{content}\n"
        f"captured: {captured}\n"
        f"{'─' * 44}\n\n"
        "[y] Accept   [n] Reject   [s] Snooze   [b] Dig deeper   [skip] Skip\n"
        "Type a key or letter to act."
    ), state, app)
    app.invalidate()


def _triage_session_turn(text: str, tl: str, session: dict,
                          state: "_State", app: "Application") -> None:
    """Handle one user input turn inside the triage session."""
    items   = session.get("items", [])
    idx     = session.get("current_idx", 0)
    if idx >= len(items):
        _exit_mode(state, app)
        return

    item = items[idx]

    # ── Debate sub-session ────────────────────────────────────────────────────
    if session.get("debate_active"):
        _triage_debate_turn(text, tl, session, state, app)
        return

    # ── Classification flow ────────────────────────────────────────────────────
    # After 'y': expect entity type selection
    if session.get("pending_classify"):
        _triage_classify_step(text, tl, item, session, state, app)
        return

    # ── Snooze flow ───────────────────────────────────────────────────────────
    if session.get("pending_snooze"):
        _triage_snooze_step(text, tl, item, session, state, app)
        return

    # ── Main triage keys ─────────────────────────────────────────────────────
    if tl in ("y", "yes", "accept"):
        session["pending_classify"] = True
        _session_chat("system",
            "What is this?\n"
            "[t] Task   [p] Project   [g] Goal   [n] Note", state, app)

    elif tl in ("n", "no", "reject", "delete"):
        storage.mark_triage_processed([item["id"]])
        session["processed"].append({**item, "action": "rejected"})
        session["current_idx"] = idx + 1
        session.pop("pending_classify", None)
        _session_chat("system", f"  \u00d7 Rejected.", state, app)
        _triage_show_current(session, state, app)

    elif tl in ("s", "snooze"):
        session["pending_snooze"] = True
        _session_chat("system",
            "Snooze until?\n"
            "[d] Tomorrow   [w] Next week   [m] Next month   [Enter/skip] Next plan",
            state, app)

    elif tl in ("b", "dig", "deeper", "dig deeper"):
        threading.Thread(
            target=_triage_start_debate,
            args=(item, session, state, app),
            daemon=True,
        ).start()

    elif tl in ("split", "decompose", "break", "break up"):
        threading.Thread(
            target=_triage_split_item,
            args=(item, session, state, app),
            daemon=True,
        ).start()

    elif tl in ("skip", "later", "next"):
        # Push to bottom of queue
        session["items"].append(session["items"].pop(idx))
        _session_chat("system", "  \u2193 Moved to bottom.", state, app)
        _triage_show_current(session, state, app)

    else:
        _session_chat("system",
            "Type: [y]es / [n]o / [s]nooze / [b]dig deeper / [split] / [skip]",
            state, app)


def _triage_prompt_parent_task(session: dict, state: "_State", app: "Application") -> None:
    """Ask which project to link a new task to, listing active projects."""
    try:
        from viyugam.models import ProjectStatus
        projects = [p for p in storage.get_projects()
                    if p.status == ProjectStatus.ACTIVE]
    except Exception:
        projects = []
    lines = ["Link to a project? (Enter to skip)\n"]
    for p in projects[:8]:
        sid  = p.seq_id or p.id
        name = p.title or "Untitled"
        lines.append(f"  {sid}  {name[:40]}")
    if not projects:
        lines.append("  (no active projects)")
    _session_chat("system", "\n".join(lines), state, app)


def _triage_prompt_parent_project(session: dict, state: "_State", app: "Application") -> None:
    """Ask which goal to link a new project to, listing active goals."""
    try:
        goals = [g for g in storage.get_goals() if g.is_active and not g.is_pseudo]
    except Exception:
        goals = []
    lines = ["Link to a goal? (Enter to skip)\n"]
    for g in goals[:8]:
        sid  = g.seq_id or g.id
        name = g.title or "Untitled"
        dim  = g.dimension or ""
        lines.append(f"  {sid}  {name[:36]}  [{dim}]")
    if not goals:
        lines.append("  (no active goals)")
    _session_chat("system", "\n".join(lines), state, app)


def _triage_classify_step(text: str, tl: str, item: dict, session: dict,
                            state: "_State", app: "Application") -> None:
    """Handle entity type and parent selection after 'y'."""
    entity_map = {"t": "task", "p": "project", "g": "goal", "n": "note",
                  "task": "task", "project": "project", "goal": "goal", "note": "note"}

    # Step 1: select entity type
    if not session.get("classify_type"):
        etype = entity_map.get(tl)
        if not etype:
            _session_chat("system",
                "Choose: [t] Task  [p] Project  [g] Goal  [n] Note", state, app)
            return
        session["classify_type"] = etype

        # task → link to project; project → link to goal; note/goal → no parent
        if etype == "task":
            _triage_prompt_parent_task(session, state, app)
        elif etype == "project":
            _triage_prompt_parent_project(session, state, app)
        else:
            _triage_save_and_advance(item, session, state, app)
        return

    # Step 2: parent linkage (optional)
    parent_id = None
    if tl and tl not in ("skip", "none", "no", "enter", ""):
        m = _re_cmd.match(r"([pg]-\d+)", tl)
        if m:
            parent_id = m.group(1).upper()

    session.pop("pending_classify", None)
    _triage_save_and_advance(item, session, state, app, parent_id=parent_id)


def _triage_save_and_advance(item: dict, session: dict, state: "_State",
                               app: "Application", parent_id: str | None = None) -> None:
    """Save classification, mark processed, advance to next item."""
    from viyugam.models import TriageItem
    etype  = session.pop("classify_type", None)
    debate = item.get("debate_summary", "")

    try:
        ti = TriageItem(**{
            k: v for k, v in item.items()
            if k in TriageItem.model_fields
        })
        ti.processed     = True
        ti.entity_type   = etype
        ti.parent_id     = parent_id
        if debate:
            ti.boardroom_notes = debate
        storage.save_triage_item(ti)
    except Exception as exc:
        _session_chat("system", f"Save error: {exc}", state, app)

    session["processed"].append({**item, "action": "accepted", "entity_type": etype})
    session["current_idx"] = session.get("current_idx", 0) + 1
    label = f"[{parent_id}]" if parent_id else ""
    _session_chat("system", f"  \u2713 Accepted as {etype}{label}.", state, app)
    _triage_show_current(session, state, app)


def _triage_snooze_step(text: str, tl: str, item: dict, session: dict,
                         state: "_State", app: "Application") -> None:
    """Handle snooze date selection."""
    from viyugam.models import TriageItem
    today = date.today()
    import datetime as _dt

    snooze_map = {
        "d": (today + _dt.timedelta(days=1)).isoformat(),
        "tomorrow": (today + _dt.timedelta(days=1)).isoformat(),
        "w": (today + _dt.timedelta(weeks=1)).isoformat(),
        "week": (today + _dt.timedelta(weeks=1)).isoformat(),
        "next week": (today + _dt.timedelta(weeks=1)).isoformat(),
        "m": (today + _dt.timedelta(days=30)).isoformat(),
        "month": (today + _dt.timedelta(days=30)).isoformat(),
    }

    snooze_until = snooze_map.get(tl)
    if not snooze_until and tl not in ("", "skip", "plan", "next plan", "enter"):
        _session_chat("system",
            "[d] Tomorrow  [w] Next week  [m] Next month  [Enter] Next plan",
            state, app)
        return

    try:
        ti = TriageItem(**{k: v for k, v in item.items()
                           if k in TriageItem.model_fields})
        ti.snooze_until = snooze_until or None
        storage.save_triage_item(ti)
    except Exception as exc:
        _session_chat("system", f"Snooze error: {exc}", state, app)

    label = f"until {snooze_until}" if snooze_until else "until next plan"
    session["processed"].append({**item, "action": "snoozed"})
    session.pop("pending_snooze", None)
    session["current_idx"] = session.get("current_idx", 0) + 1
    _session_chat("system", f"  \u23f8 Snoozed {label}.", state, app)
    _triage_show_current(session, state, app)


def _triage_split_item(item: dict, session: dict,
                        state: "_State", app: "Application") -> None:
    """Decompose a large capture into multiple atomic triage items."""
    state.running = True
    app.invalidate()
    try:
        from viyugam.agents import triage_agent
        history = session.get("debate_history") if session.get("debate_active") else None
        sub_items = triage_agent.decompose_capture(item, history)

        if len(sub_items) < 2:
            _session_chat("system",
                "Couldn't identify multiple distinct items. Try [b] dig deeper first.",
                state, app)
            return

        # Create new TriageItems for each sub-item
        new_triage = []
        for content in sub_items:
            ti = storage.append_triage(content, source="split")
            new_triage.append(ti.model_dump())

        # Mark original as processed
        storage.mark_triage_processed([item["id"]])
        session["processed"].append({**item, "action": "split"})

        # Insert new items right after current position
        idx = session.get("current_idx", 0)
        session["items"][idx:idx + 1] = new_triage  # replace original with new items

        _session_chat("system",
            f"Split into {len(sub_items)} items:\n" +
            "\n".join(f"  · {s[:60]}" for s in sub_items),
            state, app)
        _triage_show_current(session, state, app)
    except Exception as exc:
        _session_chat("system", f"Split error: {exc}", state, app)
    finally:
        state.running = False
        app.invalidate()


def _triage_start_debate(item: dict, session: dict,
                          state: "_State", app: "Application") -> None:
    """Start a boardroom dig-deeper session for this triage item."""
    state.running = True
    app.invalidate()
    try:
        from viyugam.agents import triage_agent
        goals    = storage.get_goals()
        projects = storage.get_projects()
        opening  = triage_agent.start_debate(
            item=item,
            context="",
            goals=[g.model_dump() for g in goals],
            projects=[p.model_dump() for p in projects],
        )
        session["debate_active"]  = True
        session["debate_history"] = [{"role": "assistant", "content": opening}]
        session["debate_item"]    = item
        _session_chat("assistant", opening, state, app)
    except Exception as exc:
        _session_chat("system", f"Dig deeper error: {exc}", state, app)
        session["debate_active"] = False
    finally:
        state.running = False
        app.invalidate()


def _triage_debate_turn(text: str, tl: str, session: dict,
                         state: "_State", app: "Application") -> None:
    """Handle one turn of the triage dig-deeper debate."""
    from viyugam.agents import triage_agent

    item    = session.get("debate_item", {})
    history = session.get("debate_history", [])

    if tl in ("cancel", "abort", "back", "quit"):
        session["debate_active"] = False
        session.pop("debate_history", None)
        session.pop("debate_item", None)
        _session_chat("system",
            "Debate cancelled.\n\n[y] Accept  [n] Reject  [s] Snooze  [split] Split  [skip] Skip",
            state, app)
        app.invalidate()
        return

    done_kw = triage_agent.DONE_KW
    if any(kw in tl for kw in done_kw):
        # Extract summary
        try:
            summary = triage_agent.extract_debate_summary(history, item)
        except Exception:
            summary = ""
        session["debate_item"]["debate_summary"] = summary
        session["debate_active"] = False
        idx  = session.get("current_idx", 0)
        items = session.get("items", [])
        if idx < len(items):
            items[idx] = session["debate_item"]
        msg = "Got it. Summary captured."
        if summary:
            msg += f"\n\n{summary}"
        msg += "\n\n[y] Accept  [n] Reject  [s] Snooze  [split] Split into items  [skip] Skip"
        _session_chat("system", msg, state, app)
        app.invalidate()
        return

    history.append({"role": "user", "content": text})
    try:
        reply, _ = triage_agent.debate_turn(history, text, item)
    except Exception as exc:
        _session_chat("system", f"Error: {exc}", state, app)
        return
    history.append({"role": "assistant", "content": reply})
    session["debate_history"] = history
    _session_chat("assistant", reply, state, app)
    app.invalidate()


def _build_triage_inbox(state: "_State") -> "list[list]":
    """Triage Inbox panel — live queue of pending items."""
    lines: list[list] = []

    def L(tok): lines.append([tok])
    def B():    lines.append(_blank())

    session = state.active_session if (
        state.active_session and state.active_session.get("type") == "triage"
    ) else None

    if session:
        items = session.get("items", [])
        idx   = session.get("current_idx", 0)
        pending = items[idx:]
        total   = len(pending)

        L(_t("label", f"  INBOX  ({total} pending)"))
        lines.append(_div())

        for i, item in enumerate(pending[:10]):
            content  = item.get("content", "")
            captured = (item.get("created_at") or "")[:10]
            if i == 0:
                L(_t("accent", f"  \u25b6 {content[:48]}"))
                L(_t("dim",    f"    {captured}"))
            else:
                L(_t("dim",    f"  \u00b7 {content[:50]}"))
        if total > 10:
            L(_t("dim", f"  … {total - 10} more"))
        B()
        if session.get("debate_active"):
            L(_t("dim", "  (in debate — type to continue, or [cancel] to exit)"))
        else:
            L(_t("dim", "  [y]es  [n]o  [s]nooze  [b]dig deeper  [split]  [skip]"))
    else:
        # Static view when no session
        try:
            items = [t for t in storage.get_triage() if not t.processed]
            L(_t("label", f"  INBOX  ({len(items)} pending)"))
            lines.append(_div())
            for ti in items[:12]:
                L(_t("body", f"  \u00b7 {ti.content[:52]}"))
                L(_t("dim",  f"    {(ti.created_at or '')[:10]}"))
            if not items:
                L(_t("dim", "  Inbox is clear."))
            B()
            L(_t("dim", "  /triage to start processing"))
        except Exception:
            L(_t("dim", "  Triage inbox unavailable."))

    return lines


def _build_triage_done(state: "_State") -> "list[list]":
    """Triage Done panel — items processed this session."""
    lines: list[list] = []

    def L(tok): lines.append([tok])
    def B():    lines.append(_blank())

    session = state.active_session if (
        state.active_session and state.active_session.get("type") == "triage"
    ) else None

    L(_t("label", "  PROCESSED"))
    lines.append(_div())

    if session:
        processed = session.get("processed", [])
        if processed:
            for item in reversed(processed[-12:]):
                action = item.get("action", "—")
                etype  = item.get("entity_type", "")
                content = item.get("content", "")[:44]
                icons   = {"accepted": "\u2713", "rejected": "\u00d7", "snoozed": "\u23f8", "split": "\u2702"}
                stys    = {"accepted": "done", "rejected": "dim", "snoozed": "dim", "split": "accent"}
                icon    = icons.get(action, "\u00b7")
                sty     = stys.get(action, "dim")
                label   = f" \u2192 {etype}" if etype and action == "accepted" else (
                          " \u2192 split" if action == "split" else "")
                L(_t(sty, f"  {icon} {content}{label}"))
        else:
            L(_t("dim", "  Nothing processed yet this session."))
        B()
        total = len(processed)
        L(_t("dim", f"  {total} item(s) processed this session."))
    else:
        try:
            all_triage = storage.get_triage(unprocessed_only=False)
            done       = sorted(
                [t for t in all_triage if t.processed],
                key=lambda x: x.created_at or "", reverse=True
            )[:12]
            if done:
                for ti in done:
                    etype = f" \u2192 {ti.entity_type}" if ti.entity_type else ""
                    L(_t("done", f"  \u2713 {ti.content[:44]}{etype}"))
            else:
                L(_t("dim", "  No processed items yet."))
        except Exception:
            L(_t("dim", "  Could not load triage history."))

    return lines


# ── Main Application ──────────────────────────────────────────────────────────

def run_dashboard() -> None:
    """Open the full-screen split dashboard. Blocks until Esc/C-d."""

    state     = _State()
    stop_tick = threading.Event()

    # Restore previous session if available
    prior = storage.load_last_chat_session()
    if prior:
        state.chat = [{"role": "assistant", "ansi": _WELCOME_HINTS}] + prior
        state.scroll_r = max(0, _count_chat_lines(state.chat) - 20)

    # ── Async panel cache ──────────────────────────────────────────────────────
    # _panel_lines() ONLY reads from cache — never does disk I/O on the UI thread.
    # Background threads build panels and call app.invalidate() when ready.
    _cache:    dict[str, list[list]] = {}
    _building: set[str]              = set()
    _app_ref:  list                  = [None]   # set after app creation
    # Refresh period: rebuild the panel every N ticks (1 tick = 1 s)
    _REFRESH_TICKS = 30

    def _do_build(key: str, mode: str, mode_arg: "str | None",
                  panel: int, focus: str, staging_flag: bool) -> None:
        """Build one panel in a background thread, then invalidate the app."""
        try:
            if mode == "execute":
                if panel == 0:   result = _build_gps(focus)
                elif panel == 1: result = _build_strategic(focus)
                elif panel == 2: result = _build_tactical(focus)
                elif panel == 3: result = _build_daily(focus, staging_flag)
                elif panel == 4: result = _build_research(state.research)
                else:            result = []  # panel 5 inline
            elif mode == "project":
                builders = [_build_proj_scope, _build_proj_tasks, _build_proj_context]
                result = builders[panel](mode_arg or "", focus) if panel < len(builders) else []
            elif mode == "goal":
                builders = [_build_goal_okrs, _build_goal_projects, _build_goal_alignment]
                result = builders[panel](mode_arg or "", focus) if panel < len(builders) else []
            elif mode == "plan":
                result = []  # Strategy panel (panel 0) is always built inline
            elif mode == "review":
                if panel == 1:   result = _build_rev_activity(mode_arg or "weekly", focus)
                elif panel == 2: result = _build_rev_captures(mode_arg or "weekly", focus)
                else:            result = []  # panel 0 inline (canvas)
            elif mode == "triage":
                if panel == 0:   result = _build_triage_inbox(state)
                elif panel == 1: result = _build_triage_done(state)
                else:            result = []
            else:
                result = []
            _cache[key] = result
        except Exception as exc:
            _cache[key] = [[_t("overdue", f"  Error: {exc}")]]
        finally:
            _building.discard(key)
        if _app_ref[0] is not None:
            _app_ref[0].invalidate()

    def _request_build(panel: int, focus: str, staging_flag: bool) -> None:
        """Trigger a background build unless one is already in flight."""
        mode     = state.ui_mode
        mode_arg = state.ui_mode_arg
        bucket   = state.tick // _REFRESH_TICKS
        key = f"{mode}:{mode_arg}:{panel}:{focus}:{staging_flag}:{bucket}"
        if key not in _cache and key not in _building:
            _building.add(key)
            threading.Thread(
                target=_do_build,
                args=(key, mode, mode_arg, panel, focus, staging_flag),
                daemon=True,
            ).start()

    def _panel_lines() -> list[list]:
        """Return cached panel content — never blocks, never does I/O."""
        mode  = state.ui_mode
        panel = state.panel
        focus = state.focus_mode
        staging_flag = state.staging

        # Always built inline (tracks live session state):
        if mode == "execute" and panel == 5:
            return _build_review_panel(state.active_session)
        # Plan mode has a single Strategy panel — always built inline
        if mode == "plan" and panel == 0:
            return _build_strategy_panel(state.active_session, state)
        if mode in ("review", "project") and panel == 0 and state.active_session:
            return _build_canvas_panel(state.active_session)

        bucket = state.tick // _REFRESH_TICKS
        key = f"{mode}:{state.ui_mode_arg}:{panel}:{focus}:{staging_flag}:{bucket}"

        if key in _cache:
            return _cache[key]

        if key not in _building:
            _building.add(key)
            threading.Thread(
                target=_do_build,
                args=(key, mode, state.ui_mode_arg, panel, focus, staging_flag),
                daemon=True,
            ).start()

        prefix = f"{mode}:{state.ui_mode_arg}:{panel}:"
        for k in sorted(_cache, reverse=True):
            if k.startswith(prefix):
                return _cache[k]

        return [[_t("dim", "  Loading...")]]

    input_buffer = Buffer(
        name="dash_input",
        read_only=Condition(lambda: state.mode == "normal"),
    )

    # ── Header ──
    def _header_tokens() -> list:
        mode_sty  = "header.mode.work" if state.focus_mode != "all" else "header.mode.all"
        mode_str  = f" {state.focus_mode.upper()} "
        spinner   = "⟳ " if state.running else ""
        return [
            ("class:header.title", "  Viyugam  "),
            ("class:header",       "·  "),
            ("class:header",       datetime.now().strftime("%a %-d %b  %H:%M")),
            ("class:header",       "   "),
            (f"class:{mode_sty}",  mode_str),
            ("class:header",       "  "),
            ("class:chat.spinner", spinner),
        ]

    # ── Tab bar (left panel) ──
    def _tab_tokens() -> list:
        panels = PANEL_SETS.get(state.ui_mode, PANEL_SETS["execute"])
        mode_tag = "" if state.ui_mode == "execute" else f" [{state.ui_mode.upper()}]"
        out = [("class:tab", f"  {mode_tag} " if mode_tag else "  ")]
        for i, name in enumerate(panels):
            sty = "tab.active" if i == state.panel else "tab"
            out.append((f"class:{sty}", f" {name} "))
            if i < len(panels) - 1:
                out.append(("class:tab.sep", " │ "))
        # Show scroll-active indicator on the left tab bar
        if state.scroll_focus == "left":
            out.append(("class:tab.active", " ↑↓ "))
        else:
            out.append(("class:tab", "     "))
        return out

    # ── Chat header (right panel) ──
    def _chat_header_tokens() -> list:
        mode_sty = "class:mode.insert" if state.mode == "insert" else "class:mode.normal"
        mode_str = " INSERT " if state.mode == "insert" else " NORMAL "
        scroll_sty = "class:tab.active" if state.scroll_focus == "right" else "class:dim"
        return [
            ("class:chat.header", "  Chat  "),
            (mode_sty,            mode_str),
            (scroll_sty,          " ↑↓ " if state.scroll_focus == "right" else "    "),
        ]

    # ── Content controls ──
    panel_ctrl = FormattedTextControl(
        lambda: _render_panel(_panel_lines(), state.scroll_l[state.panel]),
        focusable=False,
    )
    chat_ctrl = FormattedTextControl(
        lambda: _render_chat(state),
        focusable=False,
    )

    # ── Toolbar ──
    def _toolbar_tokens() -> list:
        if state.mode == "insert":
            return [
                ("class:toolbar",        "  "),
                ("class:toolbar.insert", "INSERT"),
                ("class:toolbar",        "   Enter submit   PgUp/PgDn scroll   'clear' new chat   Esc normal mode  "),
            ]
        pane_label = "chat" if state.scroll_focus == "right" else "panel"
        return [
            ("class:toolbar", "  "),
            ("class:mode.normal", "NORMAL"),
            ("class:toolbar", f"   ← → panels   ↑ ↓ scroll [{pane_label}]   Tab switch pane   f dimension   i type   Esc exit  "),
        ]

    def _prompt_prefix(lineno: int, wrap_count: int) -> FormattedText:
        if wrap_count > 0:
            return FormattedText([("", "  ")])
        if state.mode == "insert":
            return FormattedText([("class:prompt", "> ")])
        return FormattedText([("class:prompt.normal", "  (i to type)  ")])

    # ── Slash command hint panel ──
    def _slash_hint_tokens() -> list:
        """Filtered command suggestions shown while typing a slash command."""
        raw = input_buffer.text
        if not raw.startswith("/"):
            return []
        typed = raw[1:].lower()   # strip leading /

        # Determine which entries match
        matched: list[tuple[str, str, str, bool]] = []  # (cmd, args, desc, is_best)
        for cmd, args, desc in SLASH_HINTS:
            full = cmd if not args else f"{cmd} {args}"
            if typed == "" or cmd.startswith(typed) or full.lower().startswith(typed):
                # is_best: exact command match or typed is empty
                is_best = (typed == "" or cmd == typed or
                           full.lower() == typed or cmd.startswith(typed))
                matched.append((cmd, args, desc, is_best))

        if not matched:
            return [("class:hint.desc", "  No matching command.\n")]

        toks: list = [("class:hint.border", "  ")]
        toks.append(("class:hint.desc", "\n"))
        for cmd, args, desc, is_best in matched:
            cmd_sty  = "class:hint.match"       if is_best else "class:hint.cmd"
            arg_sty  = "class:hint.match.args"  if is_best else "class:hint.args"
            desc_sty = "class:hint.match.desc"  if is_best else "class:hint.desc"
            cmd_str  = f"  /{cmd}"
            arg_str  = f" {args}" if args else ""
            # Pad to fixed width so descriptions align
            pad = max(0, 30 - len(cmd_str) - len(arg_str))
            toks.append((cmd_sty,  cmd_str))
            toks.append((arg_sty,  arg_str))
            toks.append((desc_sty, " " * pad + f"  {desc}\n"))

        toks.append(("class:hint.border", "  "))
        return toks

    # ── Key bindings ──
    kb = KeyBindings()
    _setup_keybindings(kb, state, input_buffer, stop_tick, _cache, _building, _panel_lines)

    # ── Layout ──
    import shutil as _shutil
    _cols    = _shutil.get_terminal_size().columns
    _left_w  = max(40, int(_cols * 0.60))
    _right_w = max(28, _cols - _left_w - 1)

    layout = Layout(
        HSplit([
            Window(
                height=1,
                content=FormattedTextControl(_header_tokens),
                style="class:header",
            ),
            VSplit([
                HSplit([
                    Window(
                        height=1,
                        content=FormattedTextControl(_tab_tokens),
                        style="class:tab",
                    ),
                    Window(height=1, char="─", style="class:sep"),
                    Window(content=panel_ctrl),
                ], width=_left_w),
                Window(width=1, char="│", style="class:div"),
                HSplit([
                    Window(
                        height=1,
                        content=FormattedTextControl(_chat_header_tokens),
                        style="class:chat.header",
                    ),
                    Window(height=1, char="─", style="class:sep"),
                    Window(content=chat_ctrl, wrap_lines=True),
                    Window(height=1, char="─", style="class:sep"),
                    ConditionalContainer(
                        content=Window(
                            content=FormattedTextControl(_slash_hint_tokens),
                            height=D(min=1, max=8),
                            style="class:hint.desc",
                        ),
                        filter=Condition(
                            lambda: state.mode == "insert"
                                    and input_buffer.text.startswith("/")
                        ),
                    ),
                    Window(
                        height=D(min=1, max=5),
                        content=BufferControl(buffer=input_buffer),
                        get_line_prefix=_prompt_prefix,
                        style="class:input.line",
                        wrap_lines=True,
                    ),
                ], width=_right_w),
            ]),
            Window(
                height=1,
                content=FormattedTextControl(_toolbar_tokens),
                style="class:toolbar",
            ),
        ])
    )

    app = Application(
        layout=layout,
        key_bindings=kb,
        style=STYLE,
        full_screen=True,
        mouse_support=False,
    )
    _app_ref[0] = app  # allow background builds to invalidate

    # Kick off initial build for the first panel before the ticker starts
    _request_build(state.panel, state.focus_mode, state.staging)

    # Start ticker thread
    ticker = threading.Thread(
        target=_ticker_thread,
        args=(state, app, stop_tick, _request_build),
        daemon=True,
    )
    ticker.start()

    app.run()
    stop_tick.set()
    # Persist chat so next session restores it
    storage.save_chat_session(state.chat)
