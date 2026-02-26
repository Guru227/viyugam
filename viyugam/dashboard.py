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
    HSplit, Layout, VSplit, Window,
)
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import D
from prompt_toolkit.styles import Style
from rich.console import Console as RichConsole

import viyugam.storage as storage

# ── Constants ──────────────────────────────────────────────────────────────────

PANELS      = ["Strategic", "Tactical", "Daily", "Research"]
WORK_DIMS   = {"career", "learning", "wealth"}
APPROVE_KW  = {"approve", "looks good", "lgtm", "confirmed", "yes", "ok", "okay", "ship it"}

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
    "chat.spinner":     "#ffbb55",

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
    panel:        int        = 2          # 0=strategic 1=tactical 2=daily 3=research
    scroll_l:     list       = field(default_factory=lambda: [0, 0, 0, 0])
    scroll_r:     int        = 0
    focus_mode:   str        = "all"      # "all" | "work"
    staging:      bool       = False      # plan staged, awaiting approval
    mode:         str        = "normal"   # "normal" | "insert"
    scroll_focus: str        = "left"     # "left" | "right" — which pane ↑↓ scrolls
    dirty:        bool       = False      # cleared panel cache when True
    chat:        list       = field(default_factory=lambda: [
        {"role": "assistant", "ansi": _WELCOME_HINTS},
    ])
    research:    list       = field(default_factory=list)
    running:     bool       = False
    tick:        int        = 0          # incremented by ticker thread


# ── Focus filter ───────────────────────────────────────────────────────────────

def _visible(dimension, focus_mode: str) -> bool:
    if focus_mode == "all" or dimension is None:
        return True
    d = dimension.value if hasattr(dimension, "value") else str(dimension)
    return d in WORK_DIMS


# ── Project completion ─────────────────────────────────────────────────────────

def _project_stats(project_id: str) -> tuple[int, int, int, float]:
    """Returns (pct_done, mins_done, mins_total, budget_cap)."""
    try:
        from viyugam.models import TaskStatus
        tasks = [t for t in storage.get_tasks()
                 if t.project_id == project_id and not t.is_habit]
        if not tasks:
            return 0, 0, 0, 0.0
        total_e   = sum(t.energy_cost for t in tasks) or 1
        done_e    = sum(t.energy_cost for t in tasks if t.status == TaskStatus.DONE)
        mins_tot  = sum(t.estimated_minutes for t in tasks)
        mins_done = sum(t.estimated_minutes for t in tasks if t.status == TaskStatus.DONE)
        pct       = int(done_e / total_e * 100)

        proj = next((p for p in storage.get_projects() if p.id == project_id), None)
        budget = proj.budget_cap if proj else 0.0
        return pct, mins_done, mins_tot, budget
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
        constitution = storage.load_constitution()

        # ── Season ──
        if config.season:
            s   = config.season
            sec = f"  ·  {s.secondary.value}" if s.secondary else ""
            until = f"  until {s.until}" if s.until else ""
            L(_t("accent", f"  Season: {s.name}{until}"))
            L(_t("dim",    f"  Focus: {s.focus.value}{sec}"))
        else:
            L(_t("warn", "  No season — run 'setup'"))
        lines.append(_div())
        B()

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

        # ── Active goals ──
        active_goals   = [g for g in goals if getattr(g, "active", True)
                          and _visible(g.dimension, focus)]
        inactive_goals = [g for g in goals if not getattr(g, "active", True)
                          and _visible(g.dimension, focus)]
        L(_t("label", f"  GOALS  ({len(active_goals)} active)"))
        if active_goals:
            for g in active_goals[:10]:
                dim = g.dimension.value if g.dimension else "—"
                L(_t("todo", f"  ◆  {g.title[:36]:<36}  "),
                  _t("dim",  dim))
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

        # ── Constitution snippet ──
        L(_t("label", "  CONSTITUTION"))
        if constitution:
            for row in constitution.strip().splitlines()[:4]:
                if row.strip():
                    L(_t("dim", f"  {row[:46]}"))
        else:
            L(_t("dim", "    Not set"))
        B()

        # ── Review cadence ──
        L(_t("dim", f"  Last review:   {state.last_review or 'never'}"))
        L(_t("dim", f"  Last think:    {state.last_think  or 'never'}"))

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

        config     = storage.load_config()
        quarter    = storage.get_current_quarter()
        projects   = storage.get_projects()
        goals      = storage.get_goals()
        okrs       = storage.get_okrs()
        milestones = storage.get_milestones()
        state      = storage.load_state()
        today      = date.today().isoformat()

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
            for p in active[:8]:
                pct, mins_done, mins_tot, budget = _project_stats(p.id)
                dim   = p.dimension.value if p.dimension else "—"
                bar   = _pct_bar(pct, width=8)
                h_done = mins_done // 60
                m_done = mins_done % 60
                row = [_t("todo", f"  ●  {p.title[:28]:<28}  ")]
                row.extend(bar)
                row.append(_t("dim", f"  {pct:>3}%  {h_done}h{m_done:02d}m"))
                if budget:
                    row.append(_t("dim", f"  ₹{budget:,.0f}"))
                lines.append(row)
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

        overdue = [
            t for t in all_tasks
            if t.scheduled_date and t.scheduled_date < today
            and t.status in (TaskStatus.TODO, TaskStatus.IN_PROGRESS)
        ]
        done_today = [t for t in tasks_today if t.status == TaskStatus.DONE]
        vis_today  = [t for t in tasks_today if _visible(t.dimension, focus)]

        L(_t("accent", f"  {now.strftime('%A, %-d %b %Y')}  ·  {now.strftime('%H:%M')}"))
        lines.append(_div())
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

        # ── Footer ──
        inbox_sty = "warn" if inbox else "dim"
        L(_t(inbox_sty, f"  Inbox: {len(inbox)} unprocessed"))
        L(_t("dim", f"  Last plan: {state.last_plan or 'never'}   "
                    f"Streak: {state.current_streak}d"))

    except Exception as e:
        lines.append([_t("overdue", f"  Error: {e}")])

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


# ── Rich output capture ────────────────────────────────────────────────────────

@contextlib.contextmanager
def _capture_rich(width: int = 60):
    """Temporarily replace module-level consoles to capture rich output."""
    import viyugam.main as _m
    import viyugam.repl as _r

    buf = io.StringIO()
    cap = RichConsole(
        file=buf,
        force_terminal=False,    # Prevents Rich's Live/Status from writing cursor
        color_system="truecolor", # codes live; explicit color_system keeps colours.
        width=max(width, 40),
        highlight=False,
        soft_wrap=True,
    )
    # Prevent Prompt.ask() / Confirm.ask() from blocking stdin in a background
    # thread.  Returning "" causes Rich's Prompt to use its declared default.
    cap.input = lambda prompt="": ""

    old = {}
    for mod in (_m, _r):
        if hasattr(mod, "console"):
            old[mod] = mod.console
            mod.console = cap
    try:
        yield buf
    finally:
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

    if state.chat and state.chat[-1].get("text") == "Planning your day…":
        state.chat.pop()

    if output.strip():
        state.chat.append({"role": "assistant", "ansi": output})

    state.staging = True
    state.panel   = 2  # switch to Daily panel
    state.dirty   = True
    state.chat.append({
        "role": "system",
        "text": "Plan staged in Daily panel. Type 'approve' to confirm.",
    })
    state.running = False
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

    state.panel = 3  # switch to Research panel
    state.chat.append({
        "role": "system",
        "text": f"Research done: \"{topic}\" — switched to Research panel.",
    })
    app.invalidate()


# ── Ticker thread (elapsed time + spinner) ────────────────────────────────────

def _ticker_thread(state: _State, app: Application, stop: threading.Event) -> None:
    while not stop.is_set():
        time.sleep(1)
        state.tick += 1
        for job in state.research:
            if job["status"] == "running":
                job["elapsed"] = job.get("elapsed", 0) + 1
                job["tick"]    = state.tick
        app.invalidate()


# ── Chat rendering ─────────────────────────────────────────────────────────────

def _chat_tokens(chat: list) -> list[tuple[str, str]]:
    """Render all chat entries to a flat token list (no scrolling applied)."""
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
    return out


def _count_chat_lines(chat: list) -> int:
    """Count the number of rendered lines in the chat (approx)."""
    total = 0
    for entry in chat:
        role = entry.get("role")
        if role == "assistant":
            total += entry.get("ansi", "").count("\n") + 1
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


# ── Main Application ──────────────────────────────────────────────────────────

def run_dashboard() -> None:
    """Open the full-screen split dashboard. Blocks until Esc/C-d."""

    state     = _State()
    stop_tick = threading.Event()

    # ── Lazy panel cache (rebuilt on invalidate) ──
    _cache: dict[str, list] = {}

    def _panel_lines() -> list[list]:
        if state.dirty:
            _cache.clear()
            state.dirty = False
        key = f"{state.panel}:{state.focus_mode}:{state.staging}:{state.tick // 5}"
        if key not in _cache:
            _cache.clear()
            if state.panel == 0:
                _cache[key] = _build_strategic(state.focus_mode)
            elif state.panel == 1:
                _cache[key] = _build_tactical(state.focus_mode)
            elif state.panel == 2:
                _cache[key] = _build_daily(state.focus_mode, state.staging)
            else:
                _cache[key] = _build_research(state.research)
        return _cache[key]

    input_buffer = Buffer(
        name="dash_input",
        read_only=Condition(lambda: state.mode == "normal"),
    )

    # ── Header ──
    def _header_tokens() -> list:
        mode_sty  = "header.mode.work" if state.focus_mode == "work" else "header.mode.all"
        mode_str  = " WORK " if state.focus_mode == "work" else " ALL "
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
        out = [("class:tab", "  ")]
        for i, name in enumerate(PANELS):
            sty = "tab.active" if i == state.panel else "tab"
            out.append((f"class:{sty}", f" {name} "))
            if i < len(PANELS) - 1:
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
                ("class:toolbar",        "   Enter submit   Esc normal mode  "),
            ]
        pane_label = "chat" if state.scroll_focus == "right" else "panel"
        return [
            ("class:toolbar", "  "),
            ("class:mode.normal", "NORMAL"),
            ("class:toolbar", f"   ← → panels   ↑ ↓ scroll [{pane_label}]   Tab switch pane   f focus   i type   Esc exit  "),
        ]

    def _prompt_prefix(*_) -> FormattedText:
        if state.mode == "insert":
            return FormattedText([("class:prompt", "> ")])
        return FormattedText([("class:prompt.normal", "  (i to type)  ")])

    # ── Key bindings ──
    kb = KeyBindings()

    is_normal = Condition(lambda: state.mode == "normal")
    is_insert = Condition(lambda: state.mode == "insert")

    # ── Normal mode: navigation ──
    @kb.add("left", eager=True, filter=is_normal)
    def _left(event):
        state.panel = max(0, state.panel - 1)

    @kb.add("right", eager=True, filter=is_normal)
    def _right(event):
        state.panel = min(len(PANELS) - 1, state.panel + 1)

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
            mx = max(0, len(_panel_lines()) - 5)
            state.scroll_l[state.panel] = min(mx, state.scroll_l[state.panel] + 1)

    @kb.add("tab", filter=is_normal)
    def _toggle_pane(event):
        state.scroll_focus = "right" if state.scroll_focus == "left" else "left"

    @kb.add("c-up")
    def _scroll_chat_up(event):
        state.scroll_r = max(0, state.scroll_r - 3)

    @kb.add("c-down")
    def _scroll_chat_down(event):
        total = _count_chat_lines(state.chat)
        state.scroll_r = min(max(0, total - 5), state.scroll_r + 3)

    @kb.add("f", filter=is_normal)
    def _toggle_focus(event):
        state.focus_mode = "work" if state.focus_mode == "all" else "all"
        _cache.clear()

    # ── Normal mode: enter insert ──
    @kb.add("i", filter=is_normal)
    @kb.add("/", filter=is_normal)
    def _enter_insert(event):
        state.mode = "insert"

    # ── Insert mode: back to normal ──
    @kb.add("escape", filter=is_insert)
    def _exit_insert(event):
        state.mode = "normal"
        input_buffer.reset()

    # ── Normal mode: Esc / C-d exits ──
    @kb.add("escape", filter=is_normal)
    @kb.add("c-d")
    def _close(event):
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
        state.chat.append({"role": "user", "text": text})
        state.scroll_r = max(0, _count_chat_lines(state.chat) - 20)

        # ── Special: approve staged plan ──
        if state.staging and text.lower() in APPROVE_KW:
            state.staging = False
            state.chat.append({"role": "system", "text": "Plan confirmed. Have a great day!"})
            event.app.invalidate()
            return

        # ── Special: plan_day → staging flow ──
        tl = text.lower()
        if any(kw in tl for kw in ("plan my day", "plan for today", "let's plan", "plan day")):
            t = threading.Thread(
                target=_run_plan_bg,
                args=(state, event.app, 60),
                daemon=True,
            )
            t.start()
            return

        # ── Special: research → async Research tab ──
        if tl.startswith("research ") or tl.startswith("research:"):
            topic = text[9:].strip() if tl.startswith("research ") else text[9:].strip()
            if topic:
                job = {"topic": topic, "status": "running", "elapsed": 0, "tick": 0}
                state.research.append(job)
                state.panel = 3  # show Research tab
                t = threading.Thread(
                    target=_run_research_bg,
                    args=(topic, job, state, event.app),
                    daemon=True,
                )
                t.start()
                return

        # ── Default: run through normal NL dispatch ──
        import shutil
        chat_w = max(40, int(shutil.get_terminal_size().columns * 0.4) - 4)
        t = threading.Thread(
            target=_run_command_bg,
            args=(text, state, event.app, chat_w),
            daemon=True,
        )
        t.start()

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
                    Window(content=chat_ctrl),
                    Window(height=1, char="─", style="class:sep"),
                    Window(
                        height=1,
                        content=BufferControl(buffer=input_buffer),
                        get_line_prefix=_prompt_prefix,
                        style="class:input.line",
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

    # Start ticker thread
    ticker = threading.Thread(
        target=_ticker_thread,
        args=(state, app, stop_tick),
        daemon=True,
    )
    ticker.start()

    app.run()
    stop_tick.set()
