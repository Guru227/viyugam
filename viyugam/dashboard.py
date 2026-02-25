"""
dashboard.py — Full-screen dashboard TUI for Viyugam.

Like htop: read-only viewer, three navigable panels.
Triggered by "show dashboard" / "dashboard" from the REPL.

  ← →   switch panel (Daily / Tactical / Strategic)
  ↑ ↓   scroll within panel
  Enter  dispatch typed query (closes dashboard, runs in REPL)
  Esc    close without action
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.styles import Style

import viyugam.storage as storage


# ── Style ──────────────────────────────────────────────────────────────────────

STYLE = Style.from_dict({
    "header":           "bg:#0f111a #aaaacc",
    "header.active":    "bg:#0f111a #00d4ff bold",
    "header.sep":       "bg:#0f111a #333355",
    "sep":              "#222233",
    "label":            "#555577 bold",
    "accent":           "#00d4ff",
    "done":             "#44aa66",
    "todo":             "#ccccdd",
    "overdue":          "#ff6644",
    "dim":              "#444466",
    "warn":             "#ffaa44",
    "bar.filled":       "#00d4ff",
    "bar.empty":        "#222244",
    "toolbar":          "bg:#090b12 #333355",
    "prompt":           "#00d4ff bold",
    "input.line":       "bg:#090b12 #ffffff",
})

PANELS = ["Daily", "Tactical", "Strategic"]

# ── Token helpers ──────────────────────────────────────────────────────────────

# A "line" is a list of (style_class, text) tuples.
# We build a list[list[tuple]] per panel.

def _tok(style: str, text: str) -> tuple[str, str]:
    return (f"class:{style}", text)


def _line(*tokens: tuple[str, str]) -> list[tuple[str, str]]:
    return list(tokens)


def _blank() -> list[tuple[str, str]]:
    return []


def _divider(width: int = 42) -> list[tuple[str, str]]:
    return [_tok("sep", "  " + "─" * width)]


# ── Panel builders ─────────────────────────────────────────────────────────────

def _build_daily() -> list[list[tuple[str, str]]]:
    lines: list[list[tuple[str, str]]] = []
    today = date.today().isoformat()
    now = datetime.now()

    try:
        from viyugam.models import TaskStatus

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
        todo_today = [t for t in tasks_today if t.status in (TaskStatus.TODO, TaskStatus.IN_PROGRESS)]

        lines.append(_line(_tok("accent", f"  {now.strftime('%A, %-d %b %Y')}  ·  {now.strftime('%H:%M')}")))
        lines.append(_divider())
        lines.append(_blank())

        # ── Schedule ──
        lines.append(_line(_tok("label", f"  SCHEDULE  ({len(done_today)}/{len(tasks_today)} done)")))
        if tasks_today:
            for t in sorted(tasks_today, key=lambda x: (x.status == TaskStatus.DONE, x.id)):
                if t.status == TaskStatus.DONE:
                    marker, sty = "✓", "done"
                elif t.status == TaskStatus.IN_PROGRESS:
                    marker, sty = "●", "todo"
                else:
                    marker, sty = "○", "dim"
                period = f"  {t.time_period[:3] if t.time_period else '   '}"
                lines.append(_line(
                    _tok(sty, f"  {marker}  {t.title[:32]:<32}"),
                    _tok("dim",  f"  {t.estimated_minutes}m{period}"),
                ))
        else:
            lines.append(_line(_tok("dim", "    No tasks scheduled today")))
        lines.append(_blank())

        # ── Habits ──
        if habits:
            lines.append(_line(_tok("label", "  HABITS")))
            for h in habits[:8]:
                done  = h.last_done == today
                mark  = "✓" if done else "○"
                sty   = "done" if done else "dim"
                lines.append(_line(
                    _tok(sty, f"  {mark}  {h.title[:32]:<32}"),
                    _tok("dim", f"  streak {h.streak}"),
                ))
            lines.append(_blank())

        # ── Overdue ──
        if overdue:
            lines.append(_line(_tok("label", f"  OVERDUE ({len(overdue)})")))
            for t in overdue[:5]:
                lines.append(_line(_tok("overdue", f"  !  {t.title[:38]}")))
            lines.append(_blank())

        # ── Inbox / activity ──
        inbox_sty = "warn" if inbox else "dim"
        lines.append(_line(_tok(inbox_sty, f"  Inbox: {len(inbox)} unprocessed")))
        lines.append(_line(_tok("dim", f"  Last plan:   {state.last_plan  or 'never'}")))
        lines.append(_line(_tok("dim", f"  Last log:    {state.last_log   or 'never'}")))
        lines.append(_line(_tok("dim", f"  Streak:      {state.current_streak} days")))

    except Exception as e:
        lines.append(_line(_tok("overdue", f"  Error: {e}")))

    return lines


def _build_tactical() -> list[list[tuple[str, str]]]:
    lines: list[list[tuple[str, str]]] = []

    try:
        from viyugam.models import ProjectStatus

        config     = storage.load_config()
        quarter    = storage.get_current_quarter()
        projects   = storage.get_projects()
        goals      = storage.get_goals()
        okrs       = storage.get_okrs()
        milestones = storage.get_milestones()
        state      = storage.load_state()
        today      = date.today().isoformat()

        active_projects = [
            p for p in projects
            if p.status in (ProjectStatus.ACTIVE,)
        ]

        season_name = config.season.name if config.season else "No season"
        lines.append(_line(_tok("accent", f"  {quarter}  ·  {season_name}")))
        lines.append(_divider())
        lines.append(_blank())

        # ── Projects ──
        lines.append(_line(_tok("label", f"  PROJECTS  ({len(active_projects)} active)")))
        if active_projects:
            for p in active_projects[:7]:
                dim = p.dimension.value if p.dimension else "—"
                lines.append(_line(
                    _tok("todo", f"  ●  {p.title[:34]:<34}"),
                    _tok("dim",  f"  {dim}"),
                ))
        else:
            lines.append(_line(_tok("dim", "    No active projects")))
        lines.append(_blank())

        # ── OKRs ──
        current_okrs = [o for o in okrs if o.quarter == quarter and o.is_active]
        if current_okrs:
            lines.append(_line(_tok("label", f"  OKRs  ({quarter})")))
            for okr in current_okrs[:3]:
                dim = okr.dimension.value if okr.dimension else ""
                lines.append(_line(_tok("accent", f"  {okr.objective[:38]}")))
                krs = okr.key_results or []
                done_krs = sum(1 for kr in krs if kr.is_done)
                for kr in krs[:4]:
                    mark = "✓" if kr.is_done else "○"
                    sty  = "done" if kr.is_done else "dim"
                    lines.append(_line(_tok(sty, f"    {mark}  {kr.text[:38]}")))
                if krs:
                    bar_filled = int((done_krs / len(krs)) * 12)
                    bar = "█" * bar_filled + "░" * (12 - bar_filled)
                    lines.append(_line(
                        _tok("bar.filled", "    ["),
                        _tok("bar.filled", "█" * bar_filled),
                        _tok("bar.empty",  "░" * (12 - bar_filled)),
                        _tok("bar.filled", "]"),
                        _tok("dim", f"  {done_krs}/{len(krs)} done"),
                    ))
            lines.append(_blank())

        # ── Goals ──
        if goals:
            lines.append(_line(_tok("label", "  GOALS")))
            for g in goals[:6]:
                dim = g.dimension.value if g.dimension else "—"
                lines.append(_line(
                    _tok("dim", f"  ○  {g.title[:34]:<34}"),
                    _tok("dim", f"  {dim}"),
                ))
            lines.append(_blank())

        # ── Upcoming milestones ──
        upcoming = sorted(
            [m for m in milestones
             if getattr(m, "due_date", None) and m.due_date >= today
             and not getattr(m, "done", False)],
            key=lambda m: m.due_date,
        )
        if upcoming:
            lines.append(_line(_tok("label", "  MILESTONES (upcoming)")))
            for m in upcoming[:5]:
                lines.append(_line(
                    _tok("dim",  f"  {m.due_date}  "),
                    _tok("todo", f"{m.title[:32]}"),
                ))
            lines.append(_blank())

        lines.append(_line(_tok("dim", f"  Last weekly review:  {state.last_review or 'never'}")))

    except Exception as e:
        lines.append(_line(_tok("overdue", f"  Error: {e}")))

    return lines


def _build_strategic() -> list[list[tuple[str, str]]]:
    lines: list[list[tuple[str, str]]] = []

    try:
        config       = storage.load_config()
        slow_burns   = storage.get_slow_burns()
        constitution = storage.load_constitution()
        state        = storage.load_state()
        today        = date.today().isoformat()

        # ── Season ──
        if config.season:
            s = config.season
            until_str = f"  until {s.until}" if s.until else ""
            lines.append(_line(_tok("accent", f"  Season: {s.name}{until_str}")))
            sec = f"  ·  {s.secondary.value}" if s.secondary else ""
            lines.append(_line(_tok("dim", f"  Focus: {s.focus.value}{sec}")))
        else:
            lines.append(_line(_tok("warn", "  No season configured — run 'setup'")))
        lines.append(_divider())
        lines.append(_blank())

        # ── Slow burns ──
        lines.append(_line(_tok("label", f"  SLOW BURNS ({len(slow_burns)})")))
        if slow_burns:
            for sb in slow_burns[:8]:
                dim = sb.dimension if isinstance(sb.dimension, str) else (
                    sb.dimension.value if sb.dimension else "—"
                )
                lines.append(_line(
                    _tok("dim", f"  ●  {sb.title[:36]:<36}"),
                    _tok("dim", f"  {dim}"),
                ))
        else:
            lines.append(_line(_tok("dim", "    None yet — add long-horizon aspirations")))
        lines.append(_blank())

        # ── Horizon (4–12 weeks) ──
        from viyugam.models import TaskStatus
        h_start = (date.today() + timedelta(weeks=4)).isoformat()
        h_end   = (date.today() + timedelta(weeks=12)).isoformat()
        h_tasks = [
            t for t in storage.get_tasks(include_habits=False)
            if t.scheduled_date and h_start <= t.scheduled_date <= h_end
            and t.status not in (TaskStatus.DONE,)
        ]
        h_milestones = sorted(
            [m for m in storage.get_milestones()
             if getattr(m, "due_date", None)
             and h_start <= m.due_date <= h_end
             and not getattr(m, "done", False)],
            key=lambda m: m.due_date,
        )
        if h_tasks or h_milestones:
            lines.append(_line(_tok("label", "  HORIZON  (4–12 weeks)")))
            for m in h_milestones[:4]:
                lines.append(_line(_tok("todo", f"  ◆  {m.due_date}  {m.title[:30]}")))
            for t in h_tasks[:4]:
                lines.append(_line(_tok("dim",  f"  ·  {t.scheduled_date}  {t.title[:30]}")))
            lines.append(_blank())

        # ── Constitution snippet ──
        lines.append(_line(_tok("label", "  CONSTITUTION")))
        if constitution:
            for l in constitution.strip().splitlines()[:5]:
                if l.strip():
                    lines.append(_line(_tok("dim", f"  {l[:44]}")))
        else:
            lines.append(_line(_tok("dim", "    Not set — run 'my constitution'")))
        lines.append(_blank())

        # ── Review cadence ──
        lines.append(_line(_tok("dim", f"  Last review:   {state.last_review or 'never'}")))
        lines.append(_line(_tok("dim", f"  Last think:    {state.last_think  or 'never'}")))

    except Exception as e:
        lines.append(_line(_tok("overdue", f"  Error: {e}")))

    return lines


# ── Application ────────────────────────────────────────────────────────────────

def run_dashboard() -> Optional[str]:
    """
    Open full-screen dashboard.
    Returns the query string if user pressed Enter with text, else None.
    """
    panels_lines = [
        _build_daily(),
        _build_tactical(),
        _build_strategic(),
    ]

    active   = [0]               # current panel index
    scrolls  = [[0], [0], [0]]   # scroll offset per panel
    result   = [None]            # text to return on Enter

    input_buffer = Buffer(name="dash_input")

    # ── Header ──
    def _header_tokens() -> list[tuple[str, str]]:
        out = [("class:header", "  ")]
        for i, name in enumerate(PANELS):
            if i == active[0]:
                out.append(("class:header.active", f" {name} "))
            else:
                out.append(("class:header",        f" {name} "))
            if i < len(PANELS) - 1:
                out.append(("class:header.sep", " │ "))
        out.append(("class:header", "  "))
        return out

    # ── Content ──
    def _content_tokens() -> list[tuple[str, str]]:
        panel_lines = panels_lines[active[0]]
        offset      = scrolls[active[0]][0]
        visible     = panel_lines[offset:]

        out: list[tuple[str, str]] = []
        for line_tokens in visible:
            if line_tokens:
                out.extend(line_tokens)
            out.append(("", "\n"))
        return out

    # ── Toolbar ──
    def _toolbar_tokens() -> list[tuple[str, str]]:
        return [("class:toolbar",
                 "  ← → switch view   ↑ ↓ scroll   Enter dispatch   Esc close  ")]

    def _prompt_prefix(*_) -> FormattedText:
        return FormattedText([("class:prompt", "> ")])

    # ── Key bindings ──
    kb = KeyBindings()

    @kb.add("left")
    def _left(event):
        active[0] = max(0, active[0] - 1)

    @kb.add("right")
    def _right(event):
        active[0] = min(len(PANELS) - 1, active[0] + 1)

    @kb.add("up")
    def _up(event):
        scrolls[active[0]][0] = max(0, scrolls[active[0]][0] - 1)

    @kb.add("down")
    def _down(event):
        max_scroll = max(0, len(panels_lines[active[0]]) - 5)
        scrolls[active[0]][0] = min(max_scroll, scrolls[active[0]][0] + 1)

    @kb.add("escape")
    def _esc(event):
        result[0] = None
        event.app.exit()

    @kb.add("c-d")
    def _ctrl_d(event):
        result[0] = None
        event.app.exit()

    @kb.add("enter")
    def _enter(event):
        text = input_buffer.text.strip()
        result[0] = text if text else None
        event.app.exit()

    # ── Layout ──
    layout = Layout(
        HSplit([
            Window(
                height=1,
                content=FormattedTextControl(_header_tokens),
                style="class:header",
            ),
            Window(height=1, char="─", style="class:sep"),
            Window(
                content=FormattedTextControl(
                    _content_tokens,
                    focusable=False,
                ),
            ),
            Window(height=1, char="─", style="class:sep"),
            Window(
                height=1,
                content=FormattedTextControl(_toolbar_tokens),
                style="class:toolbar",
            ),
            Window(
                height=1,
                content=BufferControl(buffer=input_buffer),
                get_line_prefix=_prompt_prefix,
                style="class:input.line",
            ),
        ])
    )

    app = Application(
        layout=layout,
        key_bindings=kb,
        style=STYLE,
        full_screen=True,
        mouse_support=False,
        color_depth=None,
    )

    app.run()
    return result[0]
