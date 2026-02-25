"""
repl.py — Natural language REPL for Viyugam.
Launched when `viyugam` is called with no arguments.
Type naturally — Claude routes everything.
"""
from __future__ import annotations
import argparse
import os
import shutil
from datetime import date, datetime

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.console import Console

import viyugam.storage as storage

console = Console()


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

        last_plan = state.last_plan_date or "never"
        last_review = state.last_review_date or "never"
        last_log = state.last_log_date or "never"

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

        if state.last_review_date:
            try:
                last = date.fromisoformat(state.last_review_date)
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
        console.print(f"[yellow]No tasks matching \"{hint}\" found.[/yellow] Showing picker.")
        task = _pick_task()
        if task:
            cmd_done(argparse.Namespace(task_id=task.id))
        return

    best_task, best_score = scored[0]
    # If clear single winner or strong match, mark directly
    if len(scored) == 1 or best_score >= 100 or (best_score > 0 and scored[0][1] > scored[1][1] * 2):
        cmd_done(argparse.Namespace(task_id=best_task.id))
        return

    # Multiple plausible matches — show picker filtered to top candidates
    console.print(f"[dim]Multiple matches for \"{hint}\".[/dim]")
    task = _pick_task()
    if task:
        cmd_done(argparse.Namespace(task_id=task.id))


# ── AI Dispatcher ──────────────────────────────────────────────────────────────

def _ai_dispatch(text: str) -> None:
    """Classify text with AI, then execute each action in the returned list."""
    from viyugam.main import (
        cmd_plan, cmd_log, cmd_done, cmd_think, cmd_review,
        cmd_status, cmd_finance, cmd_goals, cmd_decisions,
        cmd_backlog, cmd_horizon, cmd_okrs, cmd_slow_burns,
        cmd_research, cmd_find, cmd_calendar, cmd_constitution,
        _check_api_key, _log_entry,
    )
    from viyugam.agents.intent import classify_intent

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
        clarify = item.get("clarify")

        if action == "unknown":
            if clarify:
                console.print(f"[dim]{clarify}[/dim]")
                try:
                    from prompt_toolkit.shortcuts import prompt as pt_prompt
                    follow_up = pt_prompt("> ").strip()
                    if follow_up:
                        _ai_dispatch(follow_up)
                except (KeyboardInterrupt, EOFError):
                    pass
            return

        if action == "plan_day":
            cmd_plan(argparse.Namespace(replan=False))

        elif action == "log_content":
            text_val = args.get("text") or text
            _log_entry(text_val)

        elif action == "mark_done":
            _done_by_hint(args.get("task_title_hint"))

        elif action == "run_think":
            proposal = args.get("proposal") or text
            cmd_think(argparse.Namespace(proposal=[proposal]))

        elif action == "run_review":
            cadence = (args.get("review_cadence") or "").lower()
            cmd_review(argparse.Namespace(
                weekly=(cadence == "weekly"),
                monthly=(cadence == "monthly"),
                quarterly=(cadence == "quarterly"),
            ))

        elif action == "show_status":
            cmd_status(argparse.Namespace())

        elif action == "show_finance":
            cmd_finance(argparse.Namespace(sub="summary"))

        elif action == "log_finance":
            text_val = args.get("text") or text
            _log_entry(text_val)

        elif action == "finance_history":
            cmd_finance(argparse.Namespace(sub="history"))

        elif action == "finance_recurring":
            cmd_finance(argparse.Namespace(sub="recurring"))

        elif action == "finance_insights":
            cmd_finance(argparse.Namespace(sub="insights"))

        elif action == "show_goals":
            cmd_goals(argparse.Namespace(add=False, title=[], dimension=None))

        elif action == "add_goal":
            text_val = args.get("text") or text
            _log_entry(text_val)

        elif action == "show_decisions":
            cmd_decisions(argparse.Namespace())

        elif action == "show_backlog":
            cmd_backlog(argparse.Namespace())

        elif action == "show_horizon":
            cmd_horizon(argparse.Namespace())

        elif action == "show_okrs":
            cmd_okrs(argparse.Namespace())

        elif action == "show_slow_burns":
            cmd_slow_burns(argparse.Namespace(add=False))

        elif action == "run_research":
            query = args.get("query") or text
            cmd_research(argparse.Namespace(topic=query.split()))

        elif action == "run_find":
            query = args.get("query") or text
            cmd_find(argparse.Namespace(query=query.split()))

        elif action == "show_calendar":
            cmd_calendar(argparse.Namespace(add=False, delete=False))

        elif action == "show_constitution":
            cmd_constitution(argparse.Namespace())

        elif action == "show_dashboard":
            from viyugam.dashboard import run_dashboard
            query = run_dashboard()
            if query:
                console.print(f"[dim]> {query}[/dim]")
                _ai_dispatch(query)

        elif action == "help":
            _show_help()

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
