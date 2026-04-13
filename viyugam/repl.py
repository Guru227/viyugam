"""
repl.py — Natural language REPL for Viyugam.
Launched when `viyugam` is called with no arguments.
Type naturally — Claude routes everything.
"""
from __future__ import annotations

import argparse
import os
import shutil
import threading
from datetime import date, datetime

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.console import Console

import viyugam.storage as storage

console = Console()

# Thread-local flag: set True in background threads running inside the dashboard.
# Any code that would call pt_prompt() interactively must check this first.
_tl = threading.local()


def _in_dashboard() -> bool:
    return getattr(_tl, "dashboard", False)


# ── Context summary ────────────────────────────────────────────────────────────

def _build_context_summary() -> str:
    """Build a compact context string to pass to the intent classifier."""
    today = date.today().isoformat()
    now = datetime.now().strftime("%H:%M")
    day_name = datetime.now().strftime("%A")

    try:
        from viyugam.models import TaskStatus
        tasks_today = storage.get_tasks(scheduled_date=today, include_habits=False)
        todo_today = [t for t in tasks_today if t.status in (TaskStatus.TODO, TaskStatus.IN_PROGRESS)]
        task_names = ", ".join(t.title for t in todo_today[:3])

        all_tasks = storage.get_tasks(include_habits=False)
        overdue = [
            t for t in all_tasks
            if t.scheduled_date and t.scheduled_date < today
            and t.status in (TaskStatus.TODO, TaskStatus.IN_PROGRESS)
        ]

        state = storage.load_state()
        config = storage.load_config()

        last_plan = state.last_plan or "never"
        last_review = state.last_review or "never"
        last_log = state.last_log or "never"

        season_str = ""
        if config.season:
            season_str = f"Season: Q1 {today[:4]}, focus: {config.season.focus}"

        resilience = state.resilience.value if state.resilience else "flow"

        lines = [
            f"Today: {day_name} {today}, {now}",
            f"Tasks today: {len(todo_today)} ({task_names})" if todo_today else "Tasks today: 0",
            f"Overdue: {len(overdue)}",
            f"Last plan: {last_plan} | Last review: {last_review} | Last log: {last_log}",
        ]
        if season_str:
            lines.append(season_str)
        lines.append(f"Resilience: {resilience}")
        return "\n".join(lines)
    except Exception:
        return f"Today: {day_name} {today}, {now}"


# ── Greeting ───────────────────────────────────────────────────────────────────

def _show_greeting() -> None:
    """Show context-aware greeting on REPL start."""
    today = date.today()
    day_str = today.strftime("%A, %-d %b")

    console.print()
    console.print(f"[bold cyan]Viyugam[/bold cyan]  [dim]·[/dim]  [bold]{day_str}[/bold]")
    console.print()

    try:
        from viyugam.models import TaskStatus
        today_str = today.isoformat()
        tasks_today = storage.get_tasks(scheduled_date=today_str, include_habits=False)
        todo_today = [t for t in tasks_today if t.status in (TaskStatus.TODO, TaskStatus.IN_PROGRESS)]
        all_tasks = storage.get_tasks(include_habits=False)
        overdue = [
            t for t in all_tasks
            if t.scheduled_date and t.scheduled_date < today_str
            and t.status in (TaskStatus.TODO, TaskStatus.IN_PROGRESS)
        ]

        state = storage.load_state()
        parts = []
        if todo_today:
            parts.append(f"{len(todo_today)} task{'s' if len(todo_today) != 1 else ''} today")
        if overdue:
            parts.append(f"{len(overdue)} overdue")

        if state.last_review:
            try:
                last = date.fromisoformat(state.last_review)
                days_ago = (today - last).days
                if days_ago >= 7:
                    parts.append(f"Last review: {days_ago} days ago")
            except Exception:
                pass

        if parts:
            console.print(f"[dim]{'.  '.join(parts)}.[/dim]")
            console.print()
    except Exception:
        pass

    console.print("[dim]What's on your mind?[/dim]")
    console.print()


# ── Help ───────────────────────────────────────────────────────────────────────

def _show_help() -> None:
    console.print()
    console.print("[bold]What Viyugam can do:[/bold]")
    console.print()
    items = [
        ("Plan your day",         "\"plan my day\" or \"what should I do today\""),
        ("Add tasks / notes",     "Just type it — \"call dentist tomorrow\" or \"read clean code\""),
        ("Mark things done",      "\"finished the report\" or \"done with API task\""),
        ("Think through decisions","\"should I take that job offer?\""),
        ("Log expenses/income",   "\"spent 2000 on groceries\" or \"got salary 80k\""),
        ("Finance overview",      "\"show finances\" or \"spending summary\""),
        ("Goals",                 "\"show my goals\" or \"I want to run a marathon\""),
        ("Weekly review",         "\"weekly review\" or \"quarterly review\""),
        ("Research",              "\"research Python async patterns\""),
        ("Search your data",      "\"find tasks about dentist\""),
        ("Calendar",              "\"show calendar\" or \"what's on this week\""),
        ("Your constitution",     "\"show my values\" or \"constitution\""),
        ("Morning check-in",      "\"morning\" or \"hi\" or \"good morning\""),
    ]
    for label, example in items:
        console.print(f"  [cyan]{label:<26}[/cyan] [dim]{example}[/dim]")
    console.print()
    console.print("[dim]No slash commands. Just talk.[/dim]")
    console.print()


# ── Task picker ────────────────────────────────────────────────────────────────

def _pick_task():
    """Interactive numbered task picker. Returns a Task or None."""
    from prompt_toolkit.shortcuts import prompt as pt_prompt

    from viyugam.models import TaskStatus

    all_tasks = storage.get_tasks(include_habits=False)
    active = [
        t for t in all_tasks
        if t.status in (TaskStatus.TODO, TaskStatus.BACKLOG, TaskStatus.IN_PROGRESS)
    ]

    if not active:
        console.print("[dim]No active tasks found.[/dim]")
        return None

    from rich.table import Table
    def _render(tasks) -> None:
        tbl = Table(box=None, show_header=True, header_style="bold dim", padding=(0, 1))
        tbl.add_column("#", style="dim", width=4)
        tbl.add_column("Title", min_width=30)
        tbl.add_column("Info", style="dim")
        for i, t in enumerate(tasks, 1):
            info_parts = []
            if t.dimension:
                info_parts.append(t.dimension.value)
            info_parts.append(f"{t.estimated_minutes}m")
            tbl.add_row(str(i), t.title, " · ".join(info_parts))
        console.print(tbl)

    current = list(active)
    _render(current)

    while True:
        try:
            raw = pt_prompt("Pick number or filter text (Enter to cancel): ").strip()
        except (KeyboardInterrupt, EOFError):
            return None

        if not raw:
            return None

        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(current):
                return current[idx]
            console.print(f"[red]Out of range.[/red] Pick 1–{len(current)}.")
        else:
            filtered = [
                t for t in active
                if raw.lower() in t.title.lower() or raw.lower() in t.id.lower()
            ]
            if not filtered:
                console.print("[yellow]No match.[/yellow] Try again or Enter to cancel.")
            else:
                current = filtered
                _render(current)


# ── Done-by-hint ───────────────────────────────────────────────────────────────

def _done_by_hint(hint: str | None) -> None:
    """Mark a task done by fuzzy-matching hint text. Falls back to picker."""
    from viyugam.main import cmd_done
    from viyugam.models import TaskStatus

    if not hint:
        cmd_done(argparse.Namespace(task_id=None))
        return

    hint_lower = hint.lower()
    all_tasks = storage.get_tasks(include_habits=False)
    active = [
        t for t in all_tasks
        if t.status in (TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.BACKLOG)
    ]

    # Score each task by word overlap
    hint_words = set(hint_lower.split())

    def _score(task) -> int:
        title_lower = task.title.lower()
        # Substring match scores highest
        if hint_lower in title_lower:
            return 100
        # Word overlap
        title_words = set(title_lower.split())
        return len(hint_words & title_words)

    scored = [(t, _score(t)) for t in active]
    scored = [(t, s) for t, s in scored if s > 0]
    scored.sort(key=lambda x: x[1], reverse=True)

    if not scored:
        console.print(f"[yellow]No tasks matching \"{hint}\" found.[/yellow]")
        if not _in_dashboard():
            task = _pick_task()
            if task:
                cmd_done(argparse.Namespace(task_id=task.id))
        return

    best_task, best_score = scored[0]
    # If clear single winner or strong match, mark directly
    if len(scored) == 1 or best_score >= 100 or (best_score > 0 and scored[0][1] > scored[1][1] * 2):
        cmd_done(argparse.Namespace(task_id=best_task.id))
        return

    # Multiple plausible matches
    if _in_dashboard():
        console.print(f"[yellow]Multiple tasks match \"{hint}\" — be more specific:[/yellow]")
        for t, _ in scored[:5]:
            console.print(f"  · {t.title}")
        return
    console.print(f"[dim]Multiple matches for \"{hint}\".[/dim]")
    task = _pick_task()
    if task:
        cmd_done(argparse.Namespace(task_id=task.id))


# ── Delete-goal-by-hint ────────────────────────────────────────────────────────

def _pick_goal_by_number(choices: list):
    """Prompt user to pick a goal by number from a list. Returns Goal or None."""
    try:
        from prompt_toolkit.shortcuts import prompt as pt_prompt
        raw = pt_prompt("Delete number (or Enter to cancel): ").strip()
        if not raw or not raw.isdigit():
            return None
        idx = int(raw) - 1
        if not (0 <= idx < len(choices)):
            console.print("[red]Out of range.[/red]")
            return None
        return choices[idx]
    except (KeyboardInterrupt, EOFError):
        return None


def _find_goal_by_hint(hint: str, goals: list):
    """Fuzzy-match hint against goals. Returns a single goal or None (prints UI if ambiguous)."""
    hint_lower = hint.lower()
    hint_words = set(hint_lower.split())

    def _score(g) -> int:
        t = g.title.lower()
        if hint_lower in t:
            return 100
        return len(hint_words & set(t.split()))

    scored = sorted([(g, _score(g)) for g in goals], key=lambda x: -x[1])
    scored = [(g, s) for g, s in scored if s > 0]

    if not scored:
        console.print(f"[yellow]No goals matching \"{hint}\".[/yellow]")
        return None

    if len(scored) == 1 or scored[0][1] >= 100 or (len(scored) > 1 and scored[0][1] > scored[1][1] * 2):
        return scored[0][0]

    matches = [g for g, _ in scored[:5]]
    if _in_dashboard():
        console.print(f"[yellow]Multiple goals match \"{hint}\" — be more specific:[/yellow]")
        for g in matches:
            console.print(f"  · {g.title}")
        return None
    console.print(f"[dim]Multiple matches for \"{hint}\":[/dim]")
    for i, g in enumerate(matches, 1):
        console.print(f"  [dim]{i}.[/dim]  {g.title}")
    return _pick_goal_by_number(matches)


def _delete_goal_by_hint(hint: str | None) -> None:
    """Delete a goal by fuzzy-matching hint text against goal titles."""
    goals = storage.get_goals(active_only=False)

    if not goals:
        console.print("[dim]No goals to delete.[/dim]")
        return

    if not hint:
        console.print()
        for i, g in enumerate(goals, 1):
            dim = g.dimension.value if g.dimension else "—"
            console.print(f"  [dim]{i}.[/dim]  {g.title}  [dim]{dim}[/dim]")
        console.print()
        if _in_dashboard():
            console.print("[dim]Be more specific, e.g. \"delete goal Run a 10k\"[/dim]")
            return
        goal = _pick_goal_by_number(goals)
    else:
        goal = _find_goal_by_hint(hint, goals)

    if goal is None:
        return

    if storage.delete_goal(goal.id):
        console.print(f"[green]Deleted goal:[/green] {goal.title}")
    else:
        console.print("[red]Could not delete goal.[/red]")


# ── AI Dispatcher ──────────────────────────────────────────────────────────────

def _handle_unknown(text, args, item):
    clarify = item.get("clarify")
    if clarify:
        console.print(f"[dim]{clarify}[/dim]")
        try:
            from prompt_toolkit.shortcuts import prompt as pt_prompt
            follow_up = pt_prompt("> ").strip()
            if follow_up:
                _ai_dispatch(follow_up)
        except (KeyboardInterrupt, EOFError):
            pass


def _handle_plan_day(text, args, item):
    from viyugam.main import cmd_plan
    cadence = (args.get("review_cadence") or "daily").lower()
    cmd_plan(argparse.Namespace(replan=False, scope=cadence))


def _handle_log_content(text, args, item):
    from viyugam.main import _triage_capture
    text_val = args.get("text") or text
    _triage_capture(text_val)


def _handle_mark_done(text, args, item):
    import re as _re
    hint = args.get("task_title_hint") or ""
    if _re.match(r'^[TGPNtgpn]-\d{3,}$', hint.strip()):
        result = storage.mark_entity_done(hint.strip().upper())
        if result:
            console.print(f"[green]{result}[/green]")
        else:
            console.print(f"[yellow]Not found:[/yellow] {hint}")
    else:
        _done_by_hint(hint)


def _handle_run_think(text, args, item):
    from viyugam.main import _triage_capture
    text_val = args.get("proposal") or text
    _triage_capture(text_val)
    console.print("[dim]Captured to triage. Run 'plan' to process it in the boardroom.[/dim]")


def _handle_run_review(text, args, item):
    from viyugam.main import cmd_review
    cadence = (args.get("review_cadence") or "weekly").lower()
    cmd_review(argparse.Namespace(
        weekly=(cadence == "weekly"),
        monthly=(cadence == "monthly"),
        quarterly=(cadence == "quarterly"),
        scope=cadence,
    ))


def _handle_show_status(text, args, item):
    console.print("[dim]Dashboard is always available — run 'viyugam' with no args.[/dim]")


def _handle_show_finance(text, args, item):
    from viyugam.main import cmd_finance
    cmd_finance(argparse.Namespace(sub="summary"))


def _handle_log_finance(text, args, item):
    from viyugam.main import _triage_capture
    text_val = args.get("text") or text
    _triage_capture(text_val)


def _handle_finance_history(text, args, item):
    from viyugam.main import cmd_finance
    cmd_finance(argparse.Namespace(sub="history"))


def _handle_finance_recurring(text, args, item):
    from viyugam.main import cmd_finance
    cmd_finance(argparse.Namespace(sub="recurring"))


def _handle_finance_insights(text, args, item):
    from viyugam.main import cmd_finance
    cmd_finance(argparse.Namespace(sub="insights"))


def _handle_show_goals(text, args, item):
    from viyugam.main import cmd_goals
    cmd_goals(argparse.Namespace(add=False, title=[], dimension=None))


def _handle_delete_goal(text, args, item):
    _delete_goal_by_hint(args.get("task_title_hint"))


def _handle_add_goal(text, args, item):
    from viyugam.main import _triage_capture
    text_val = args.get("text") or text
    _triage_capture(text_val)


def _handle_show_decisions(text, args, item):
    from viyugam.main import cmd_decisions
    cmd_decisions(argparse.Namespace())


def _handle_show_backlog(text, args, item):
    from viyugam.main import cmd_backlog
    cmd_backlog(argparse.Namespace())


def _handle_show_horizon(text, args, item):
    from viyugam.main import cmd_horizon
    cmd_horizon(argparse.Namespace())


def _handle_show_okrs(text, args, item):
    from viyugam.main import cmd_okrs
    cmd_okrs(argparse.Namespace())


def _handle_show_slow_burns(text, args, item):
    from viyugam.main import cmd_slow_burns
    cmd_slow_burns(argparse.Namespace(add=False))


def _handle_run_research(text, args, item):
    from viyugam.main import cmd_research
    query = args.get("query") or text
    cmd_research(argparse.Namespace(topic=query.split()))


def _handle_run_find(text, args, item):
    from viyugam.main import cmd_find
    query = args.get("query") or text
    cmd_find(argparse.Namespace(query=query.split()))


def _handle_show_calendar(text, args, item):
    from viyugam.main import cmd_calendar
    cmd_calendar(argparse.Namespace(add=False, delete=False))


def _handle_show_constitution(text, args, item):
    from viyugam.main import cmd_constitution
    cmd_constitution(argparse.Namespace())


def _handle_show_dashboard(text, args, item):
    from viyugam.dashboard import run_dashboard
    run_dashboard()


def _handle_help(text, args, item):
    _show_help()


_DISPATCH = {
    "plan_day": _handle_plan_day,
    "log_content": _handle_log_content,
    "mark_done": _handle_mark_done,
    "run_think": _handle_run_think,
    "run_review": _handle_run_review,
    "show_status": _handle_show_status,
    "show_finance": _handle_show_finance,
    "log_finance": _handle_log_finance,
    "finance_history": _handle_finance_history,
    "finance_recurring": _handle_finance_recurring,
    "finance_insights": _handle_finance_insights,
    "show_goals": _handle_show_goals,
    "delete_goal": _handle_delete_goal,
    "add_goal": _handle_add_goal,
    "show_decisions": _handle_show_decisions,
    "show_backlog": _handle_show_backlog,
    "show_horizon": _handle_show_horizon,
    "show_okrs": _handle_show_okrs,
    "show_slow_burns": _handle_show_slow_burns,
    "run_research": _handle_run_research,
    "run_find": _handle_run_find,
    "show_calendar": _handle_show_calendar,
    "show_constitution": _handle_show_constitution,
    "show_values": _handle_show_constitution,
    "show_dashboard": _handle_show_dashboard,
    "help": _handle_help,
}


def _ai_dispatch(text: str) -> None:
    """Classify text with AI, then execute each action in the returned list."""
    from viyugam.agents.intent import classify_intent
    from viyugam.main import _check_api_key

    if not _check_api_key():
        return

    try:
        context = _build_context_summary()
        actions = classify_intent(text, context)
    except Exception as e:
        console.print(f"[red]Classification error:[/red] {e}")
        return

    for item in actions:
        action = item.get("action", "unknown")
        args = item.get("args", {}) or {}

        if action == "unknown":
            _handle_unknown(text, args, item)
            return

        handler = _DISPATCH.get(action)
        if handler:
            handler(text, args, item)
        else:
            console.print(f"[dim]Unknown action: {action}[/dim]")


# ── One-shot entry (from CLI with text args) ───────────────────────────────────

def run_one_shot(text: str) -> None:
    """Classify and execute a single natural language command, then exit."""
    import os
    storage.ensure_dirs()

    if not storage.CONFIG_FILE.exists():
        console.print("[yellow]No config found.[/yellow] Run [bold]viyugam setup[/bold] first.")
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        try:
            cfg = storage.load_config()
            if cfg.api_key:
                os.environ["ANTHROPIC_API_KEY"] = cfg.api_key
        except Exception:
            pass

    _ai_dispatch(text)


# ── Visual style ───────────────────────────────────────────────────────────────

_STYLE = Style.from_dict({
    "prompt":         "#ffffff bold",
    "bottom-toolbar": "bg:#1a1a1a #555555",
})


def _cols() -> int:
    return shutil.get_terminal_size().columns


def _bottom_toolbar() -> HTML:
    return HTML('<bottom-toolbar>  Type naturally · Ctrl-D to exit  </bottom-toolbar>')


# ── REPL entry ─────────────────────────────────────────────────────────────────

def run_repl() -> None:
    """Start the interactive Viyugam session."""
    storage.ensure_dirs()

    # First-run: no config → run setup before entering loop
    if not storage.CONFIG_FILE.exists():
        from viyugam.main import cmd_setup
        console.print(
            "\n[yellow]No config found.[/yellow] Let's get you set up first.\n"
        )
        cmd_setup(argparse.Namespace())
        console.print()

    # Load API key into env once for the session
    if not os.environ.get("ANTHROPIC_API_KEY"):
        try:
            cfg = storage.load_config()
            if cfg.api_key:
                os.environ["ANTHROPIC_API_KEY"] = cfg.api_key
        except Exception:
            pass

    history_path = storage.HOME / "history"
    session: PromptSession = PromptSession(
        history=FileHistory(str(history_path)),
        complete_while_typing=False,
        bottom_toolbar=_bottom_toolbar,
        style=_STYLE,
    )

    _show_greeting()

    while True:
        try:
            text = session.prompt("> ")
        except KeyboardInterrupt:
            console.print()
            continue
        except EOFError:
            console.print("\n[dim]Goodbye.[/dim]\n")
            break

        text = text.strip()
        if not text:
            continue

        if text.lower() in ("exit", "quit", "q"):
            console.print("\n[dim]Goodbye.[/dim]\n")
            break

        try:
            _ai_dispatch(text)
        except SystemExit as e:
            if e.code == 0:
                console.print("\n[dim]Goodbye.[/dim]\n")
                break
            raise
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")

        console.print()  # breathing room between responses
