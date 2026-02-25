#!/usr/bin/env python3
"""
Viyugam — A personal Life OS.
Text-only. Claude-powered. Local-first.

Commands:
    viyugam setup                  First-run configuration
    viyugam capture "thought"      Add to inbox (instant, no AI)
    viyugam plan                   Build today's schedule
    viyugam done <id>              Mark a task complete
    viyugam status                 Quick overview
    viyugam log                    Evening journal session
    viyugam think "proposal"       Decision gateway
    viyugam think                  Review someday list
    viyugam review                 Weekly / monthly / quarterly review
    viyugam goals                  View and add long-term goals
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
from datetime import date, datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from rich.prompt import Confirm, Prompt

import viyugam.storage as storage
from viyugam.models import (
    Task, Project, TaskStatus, ResilienceState, SystemState,
    CalendarEntry, CalendarEntryType,
    SlowBurn, Milestone, Budget, Transaction, Decision, ActualRecord,
)

console = Console()


# ── Startup check ──────────────────────────────────────────────────────────────

def _check_api_key() -> bool:
    """Check ANTHROPIC_API_KEY is available, print helpful message if not."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return True
    # Try loading from config
    try:
        cfg = storage.load_config()
        if cfg.api_key:
            os.environ["ANTHROPIC_API_KEY"] = cfg.api_key
            return True
    except Exception:
        pass
    console.print(
        "\n[red]ANTHROPIC_API_KEY not set.[/red]\n\n"
        "Add it to your shell profile:\n"
        "  [bold]export ANTHROPIC_API_KEY=\"your-key-here\"[/bold]\n\n"
        "Or add it to ~/.viyugam/config.yaml:\n"
        "  [bold]api_key: \"your-key-here\"[/bold]\n\n"
        "Get a key at: https://console.anthropic.com\n"
        "[dim]Note: If Claude Code is already working, run:[/dim]\n"
        "  [bold]echo $ANTHROPIC_API_KEY[/bold]\n"
    )
    return False


def startup_check() -> SystemState:
    """Run on every command. Check resilience state and surface if needed."""
    storage.ensure_dirs()

    # First-run: no config yet
    if not storage.CONFIG_FILE.exists():
        console.print(
            "\n[yellow]No config found.[/yellow] "
            "Run [bold]viyugam setup[/bold] to get started.\n"
        )
        sys.exit(0)

    state = storage.load_state()
    resilience = storage.check_resilience(state)
    state.resilience = resilience

    if resilience == ResilienceState.BANKRUPTCY:
        _handle_bankruptcy(state)
        sys.exit(0)
    elif resilience == ResilienceState.DRIFT:
        days = _days_since(state.last_active)
        console.print(
            f"\n[yellow]You've been away for {days} days.[/yellow] "
            "No pressure — let's ease back in.\n"
        )

    return state


def _days_since(iso_str: str | None) -> int:
    if not iso_str:
        return 0
    last = datetime.fromisoformat(iso_str).date()
    return (date.today() - last).days


def _handle_bankruptcy(state: SystemState) -> None:
    days = _days_since(state.last_active)
    console.print(Panel(
        f"[bold]Welcome back.[/bold]\n\n"
        f"You've been away for [yellow]{days} days[/yellow]. "
        "The system has paused to protect your focus.\n\n"
        "A fresh start means: overdue tasks move to backlog, "
        "active projects pause.\nYou pick one thing to do today. That's enough.",
        title="[bold red]Resilience Protocol[/bold red]",
        border_style="red",
        padding=(1, 2),
    ))

    if Confirm.ask("\nReady for a fresh start?"):
        result = storage.settle_bankruptcy()
        console.print(
            f"\n[green]Done.[/green] "
            f"{result['cleared_tasks']} tasks moved to backlog. "
            f"{result['paused_projects']} projects paused.\n"
            "Run [bold]viyugam plan[/bold] to get your recovery schedule."
        )
    else:
        console.print("\nTake your time. Come back when you're ready.\n")


# ── capture ────────────────────────────────────────────────────────────────────

def cmd_capture(args: argparse.Namespace) -> None:
    """Deprecated — routes to cmd_log."""
    console.print("[dim]Note: 'capture' is now 'log'. Routing...[/dim]")
    text = " ".join(args.text) if hasattr(args, "text") and args.text else ""
    if text:
        _log_entry(text)
    else:
        cmd_log(args)


# ── plan ───────────────────────────────────────────────────────────────────────

def cmd_plan(args: argparse.Namespace) -> None:
    from viyugam.agents.chairman import triage_inbox, plan_day

    state = startup_check()
    config = storage.load_config()
    today = date.today().isoformat()

    now = datetime.now()
    current_time = now.strftime("%H:%M")
    current_hour = now.hour
    day_start = config.day_start  # default 10

    # ── Determine planning mode ────────────────────────────────────────────────
    force_replan = getattr(args, "replan", False)
    already_planned = state.last_plan == today

    if already_planned or force_replan:
        mode = "replan"
    elif current_hour >= day_start:
        mode = "midday"
    else:
        mode = "full"

    # ── Mode-specific prompts ──────────────────────────────────────────────────
    catch_up_notes = ""

    if mode == "midday":
        done_today = [
            t for t in storage.get_tasks(status="done")
            if t.last_done == today or t.scheduled_date == today
        ]
        console.print()
        if done_today:
            console.print(f"[dim]It's {current_time} — already done today:[/dim]")
            for t in done_today:
                console.print(f"  [green]✓[/green] {t.title}")
            console.print()
        else:
            console.print(f"[dim]It's {current_time} — planning the rest of your day.[/dim]\n")
        catch_up_notes = Prompt.ask(
            "What did you get done this morning?",
            default="",
        )
        console.print()

    elif mode == "replan":
        console.print(f"\n[dim]It's {current_time}. Replanning from now.[/dim]\n")
        catch_up_notes = Prompt.ask(
            "What changed?  [dim](e.g. meeting ran long, low energy, new priority — Enter for clean replan)[/dim]",
            default="",
        )
        console.print()

    # ── Schedule context ───────────────────────────────────────────────────────
    day_type = storage.get_day_type(today, config)
    calendar_events = storage.get_calendar_entries(today)

    if config.work_schedule:
        ws = config.work_schedule
        day_label = {"office": "office day", "wfh": "WFH day", "off": "day off"}[day_type]
        console.print(f"[dim]Today: {day_label} — {ws.start}–{ws.end}[/dim]")
        for e in calendar_events:
            t = f" {e.start_time}" if e.start_time else ""
            console.print(f"  [dim]· {e.title}{t}[/dim]")
        if calendar_events:
            console.print()
        override = Prompt.ask(
            "Override?", choices=["office", "wfh", "off", ""], default=""
        )
        if override:
            day_type = override
        console.print()

    # 1. Auto-process inbox
    inbox_items = storage.get_inbox(unprocessed_only=True)
    if inbox_items:
        console.print(f"[dim]Processing {len(inbox_items)} inbox item(s)...[/dim]")
        _process_inbox_items(inbox_items, config)

    # 2. Gather context — exclude done tasks for midday/replan
    tasks_today = storage.get_tasks(scheduled_date=today)
    overdue = [
        t for t in storage.get_tasks(status="todo")
        if t.scheduled_date and t.scheduled_date < today and not t.is_habit
    ]
    all_tasks = tasks_today + [t for t in overdue if t not in tasks_today]
    if mode in ("midday", "replan"):
        all_tasks = [t for t in all_tasks if t.status != TaskStatus.DONE]

    habits = storage.get_habits()
    projects = storage.get_projects(status="active")
    goals = storage.get_goals()
    recent_journals = storage.get_recent_journals(days=14)
    nudges = storage.get_nudges(state)

    if not all_tasks and not habits:
        console.print(
            Panel(
                "No tasks scheduled for today.\n\n"
                "Try [bold]viyugam capture \"something you want to do\"[/bold] first.",
                title=f"[bold]Plan · {today}[/bold]",
                border_style="dim",
            )
        )
        _show_nudges(nudges)
        return

    # Load memory + constitution for AI context
    memory_context = storage.get_memory_context()
    constitution   = storage.load_constitution()

    # 3. Generate schedule
    status_msg = {
        "full":   "Building your schedule...",
        "midday": "Planning the rest of your day...",
        "replan": "Replanning from now...",
    }[mode]
    with console.status(f"[dim]{status_msg}[/dim]"):
        plan = plan_day(
            tasks=[t.model_dump() for t in all_tasks],
            habits=[h.model_dump() for h in habits],
            projects=[p.model_dump() for p in projects],
            goals=[g.model_dump() for g in goals],
            recent_journals=recent_journals,
            config=config.model_dump(),
            today=today,
            nudges=nudges,
            current_time=current_time,
            mode=mode,
            catch_up_notes=catch_up_notes,
            work_schedule=config.work_schedule.model_dump() if config.work_schedule else None,
            day_type=day_type,
            calendar_events=[e.model_dump() for e in calendar_events],
            memory_context=memory_context,
            constitution=constitution,
        )

    # 4. Move backlogged tasks
    if plan.get("moved_to_backlog"):
        backlogged_ids = set(plan["moved_to_backlog"])
        tasks_to_update = [t for t in all_tasks if t.id in backlogged_ids]
        for t in tasks_to_update:
            t.status = TaskStatus.BACKLOG
            t.scheduled_date = None
        storage.save_tasks(tasks_to_update)

    # 5. Render schedule
    all_tasks_for_backlog = storage.get_tasks()
    backlog_tasks = [
        t for t in all_tasks_for_backlog
        if t.status.value != "done"
        and (not t.scheduled_date or t.scheduled_date != today)
        and not t.is_habit
    ]
    _render_plan(plan, today, config.user_name, backlog_tasks=backlog_tasks)

    # Update rolling memory
    summary = f"Planned {len(all_tasks)} tasks, mode={mode}, day_type={day_type}"
    if plan.get("energy_read"):
        summary += f". Energy: {plan['energy_read'][:100]}"
    storage.update_memory_summary(summary, source="plan")

    # Show coherence score
    coherence = storage.compute_coherence_score(config)
    if coherence.get("score") is not None:
        score = coherence["score"]
        color = "green" if score >= 70 else "yellow" if score >= 45 else "red"
        console.print(f"  Coherence: [{color}]{score}/100[/{color}]  [dim]{coherence['narrative']}[/dim]")

    state = storage.touch_active(state)
    state.last_plan = today
    storage.save_state(state)


def _process_inbox_items(inbox_items, config) -> None:
    from viyugam.agents.chairman import triage_inbox
    from viyugam.models import Task, Project, ProjectStatus

    config_context = ""
    if config.season:
        config_context = f"User's current season: {config.season.name}, focus: {config.season.focus.value}"

    try:
        results = triage_inbox(
            [item.content for item in inbox_items],
            config_context=config_context,
        )
    except Exception as e:
        console.print(f"[yellow]Inbox triage skipped:[/yellow] {e}")
        return

    processed_ids = []
    inbox_rows: list[tuple[str, str, str, str]] = []  # badge, title, dimension, time

    for result in results:
        if result.get("type") == "task":
            task = Task(
                title=result.get("title", result.get("original", "Untitled")),
                dimension=result.get("dimension"),
                energy_cost=result.get("energy_cost", 5),
                estimated_minutes=result.get("estimated_minutes", 30),
                context=result.get("context"),
                notes=result.get("notes"),
                scheduled_date=date.today().isoformat(),
            )
            storage.save_task(task)
            dim_str = task.dimension.value if task.dimension else "—"
            inbox_rows.append(("Task", task.title, dim_str, f"{task.estimated_minutes}m"))

        elif result.get("type") == "project":
            project = Project(
                title=result.get("title", result.get("original", "Untitled")),
                description=result.get("notes"),
            )
            storage.save_project(project)
            inbox_rows.append(("Project", project.title, "—", "—"))

        elif result.get("type") == "note":
            title = result.get("title", result.get("original", ""))
            inbox_rows.append(("Note", title, "—", "—"))

        processed_ids.append(_find_inbox_id(inbox_items, result.get("original", "")))

    storage.mark_inbox_processed([pid for pid in processed_ids if pid])

    if inbox_rows:
        tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold dim", padding=(0, 1))
        tbl.add_column("Type", style="dim", width=9)
        tbl.add_column("Title", min_width=28)
        tbl.add_column("Dimension", style="dim", width=14)
        tbl.add_column("Time", justify="right", style="dim", width=6)
        for badge, title, dim, time in inbox_rows:
            badge_style = {"Task": "green", "Project": "blue", "Note": "dim"}.get(badge, "dim")
            tbl.add_row(f"[{badge_style}]{badge}[/{badge_style}]", title, dim, time)
        console.print(Panel(tbl, title="[bold]Inbox processed[/bold]", border_style="dim", padding=(0, 1)))
    console.print()


def _find_inbox_id(inbox_items, original_text: str) -> str | None:
    for item in inbox_items:
        if item.content.strip() == original_text.strip():
            return item.id
    if inbox_items:
        return inbox_items[0].id
    return None


def _render_plan(plan: dict, today: str, user_name: str, backlog_tasks=None) -> None:
    from rich.columns import Columns

    schedule = plan.get("schedule", [])
    nudges = plan.get("nudges", [])
    moved = plan.get("moved_to_backlog", [])
    energy_read = plan.get("energy_read", "")
    season_note = plan.get("season_note")

    # Header
    console.print()
    console.print(Panel(
        f"[bold]{today}[/bold]",
        title=f"[bold cyan]Your Day · {user_name}[/bold cyan]",
        border_style="cyan",
        padding=(0, 2),
    ))

    if energy_read:
        console.print(f"\n[dim]{energy_read}[/dim]\n")

    # Build today's schedule table
    if schedule:
        sched_table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
        sched_table.add_column("Time", style="cyan", width=7)
        sched_table.add_column("", width=2)
        sched_table.add_column("Task", min_width=26)
        sched_table.add_column("Dur", justify="right", style="dim", width=5)
        sched_table.add_column("E", justify="center", width=5)

        for item in schedule:
            time_str = item.get("time", "")
            duration = item.get("duration_mins", 0)
            title = item.get("title", "")
            energy = item.get("energy_cost", 0)
            item_type = item.get("type", "task")

            if item_type == "break":
                sched_table.add_row(
                    time_str, "·",
                    Text("Break", style="dim italic"),
                    f"{duration}m", ""
                )
            elif item_type == "habit":
                sched_table.add_row(
                    time_str, "◎",
                    Text(title, style="green"),
                    f"{duration}m",
                    _energy_bar(energy) if energy else "",
                )
            elif item_type == "event":
                sched_table.add_row(
                    time_str, "◆",
                    Text(title, style="cyan italic"),
                    f"{duration}m" if duration else "—", "",
                )
            else:
                sched_table.add_row(
                    time_str, "▸",
                    title,
                    f"{duration}m",
                    _energy_bar(energy) if energy else "",
                )

        today_panel = Panel(sched_table, title="[bold]Today[/bold]", border_style="cyan", padding=(0, 1))
    else:
        today_panel = Panel("[dim]Nothing scheduled.[/dim]", title="[bold]Today[/bold]", border_style="cyan", padding=(0, 1))

    # Build backlog panel
    if backlog_tasks:
        # Group by dimension
        by_dim: dict[str, list] = {}
        for t in backlog_tasks[:20]:
            key = t.dimension.value if t.dimension else "other"
            by_dim.setdefault(key, []).append(t)

        bl_table = Table(box=None, show_header=False, padding=(0, 1))
        bl_table.add_column(style="dim", width=8, no_wrap=True)
        bl_table.add_column(min_width=20)
        bl_table.add_column(style="dim")

        for dim, tasks in sorted(by_dim.items()):
            bl_table.add_row(f"[dim]{dim}[/dim]", "", "")
            for t in tasks:
                bl_table.add_row(
                    f"  [dim]{t.id}[/dim]",
                    t.title,
                    f"{t.estimated_minutes}m",
                )

        backlog_count = len(backlog_tasks)
        overflow_note = f"\n[dim]  … and {backlog_count - 20} more[/dim]" if backlog_count > 20 else ""
        backlog_panel = Panel(
            bl_table,
            title=f"[bold]Everything else[/bold] [dim]({backlog_count})[/dim]",
            border_style="dim",
            padding=(0, 1),
        )
    else:
        backlog_panel = Panel("[dim]Backlog empty.[/dim]", title="[bold]Everything else[/bold]", border_style="dim", padding=(0, 1))

    console.print(Columns([today_panel, backlog_panel], equal=True, expand=True))

    # Moved to backlog
    if moved:
        console.print(f"[dim]  Moved to backlog: {len(moved)} task(s) (over time budget)[/dim]")

    # Season note
    if season_note:
        console.print(f"\n[yellow]  Season note:[/yellow] [dim]{season_note}[/dim]")

    # Nudges
    _show_nudges(nudges)
    console.print()


def _energy_bar(cost: int) -> str:
    filled = round(cost / 2)
    return "⚡" * filled if cost >= 7 else "·" * max(1, filled)


def _show_nudges(nudges: list[str]) -> None:
    if nudges:
        console.print()
        for nudge in nudges:
            console.print(f"  [dim]→ {nudge}[/dim]")


# ── done ───────────────────────────────────────────────────────────────────────

def cmd_done(args: argparse.Namespace) -> None:
    state = startup_check()
    task_id = getattr(args, "task_id", None)

    task = None
    if task_id:
        task = storage.get_task_by_id(task_id)

    if not task:
        if task_id:
            console.print(f"[yellow]No task found with id '{task_id}'.[/yellow]")
        # Fall into picker
        task = _pick_task_for_done()
        if not task:
            return

    _complete_task(task, state)


def _pick_task_for_done() -> Task | None:
    """Show today's + recent tasks as a numbered list for quick selection."""
    today = date.today().isoformat()
    candidates = [
        t for t in storage.get_tasks()
        if t.status == TaskStatus.TODO
        and (t.scheduled_date == today or t.scheduled_date is None)
        and not t.is_habit
    ]
    if not candidates:
        candidates = [t for t in storage.get_tasks() if t.status == TaskStatus.TODO and not t.is_habit]

    if not candidates:
        console.print("[dim]No active tasks found.[/dim]")
        return None

    tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold dim", padding=(0,1))
    tbl.add_column("#", style="dim", width=3)
    tbl.add_column("Title", min_width=28)
    tbl.add_column("Info", style="dim")
    for i, t in enumerate(candidates[:15], 1):
        info = f"{t.estimated_minutes}m"
        if t.dimension:
            info = f"{t.dimension.value} · {info}"
        tbl.add_row(str(i), t.title, info)
    console.print(tbl)

    raw = Prompt.ask("Which task? (number or Enter to cancel)", default="")
    if not raw.strip() or not raw.strip().isdigit():
        return None
    idx = int(raw.strip()) - 1
    if 0 <= idx < len(candidates[:15]):
        return candidates[idx]
    return None


def _complete_task(task: Task, state) -> None:
    today = date.today().isoformat()
    task.status = TaskStatus.DONE
    if task.is_habit:
        if task.last_done != today:
            task.streak += 1
            task.last_done = today
            console.print(f"[green]Done:[/green] {task.title} [dim]· streak {task.streak}[/dim]")
    else:
        console.print(f"[green]Done:[/green] {task.title}")

    storage.save_task(task)

    # Record actual time (skip for habits — they're binary done/not-done)
    if not task.is_habit:
        actual_raw = Prompt.ask(
            f"How long did it actually take? [dim](estimated {task.estimated_minutes}m — Enter to skip)[/dim]",
            default=""
        )
        actual_mins = int(actual_raw.strip()) if actual_raw.strip().isdigit() else None
        record = ActualRecord(
            task_id=task.id,
            task_title=task.title,
            planned_minutes=task.estimated_minutes,
            actual_minutes=actual_mins,
            date=today,
        )
        storage.save_actual(record)

    state = storage.touch_active(state)
    storage.save_state(state)


def _handle_unscheduled_completion(task: Task) -> None:
    """Gracefully handle something done that wasn't planned."""
    config = storage.load_config()
    season_focus = config.season.focus.value if config.season else None

    # Just log it — no judgment. The coach surfaces patterns over time, not one-offs.
    console.print(f"[dim]  Absorbed. Good work.[/dim]")


# ── status ─────────────────────────────────────────────────────────────────────

def cmd_status(args: argparse.Namespace) -> None:
    state = startup_check()
    today = date.today().isoformat()
    config = storage.load_config()

    tasks_today = storage.get_tasks(scheduled_date=today)
    done_today = [t for t in tasks_today if t.status == TaskStatus.DONE]
    todo_today = [t for t in tasks_today if t.status == TaskStatus.TODO]
    habits = storage.get_habits()
    inbox_count = len(storage.get_inbox(unprocessed_only=True))

    console.print()
    console.print(Panel(
        f"[bold]{today}[/bold]  ·  streak: [cyan]{state.current_streak}[/cyan] days",
        title=f"[bold]Status · {config.user_name}[/bold]",
        border_style="dim",
        padding=(0, 2),
    ))

    # Today's progress
    total = len(tasks_today)
    done = len(done_today)
    if total > 0:
        bar = "█" * done + "░" * (total - done)
        console.print(f"\n  Tasks today:  [{bar}] {done}/{total}")

    if todo_today:
        console.print("\n  [bold]Still to do:[/bold]")
        for t in todo_today[:5]:
            console.print(f"  [dim]{t.id}[/dim]  {t.title}  [dim]{t.estimated_minutes}m[/dim]")
        if len(todo_today) > 5:
            console.print(f"  [dim]  ... and {len(todo_today) - 5} more[/dim]")

    if habits:
        console.print("\n  [bold]Habits:[/bold]")
        for h in habits:
            done_marker = "[green]✓[/green]" if h.last_done == today else "[dim]○[/dim]"
            console.print(f"  {done_marker}  {h.title}  [dim]streak: {h.streak}[/dim]")

    if inbox_count > 0:
        console.print(f"\n  [yellow]{inbox_count} unprocessed inbox item(s)[/yellow] — run [bold]viyugam plan[/bold]")

    nudges = storage.get_nudges(state)
    _show_nudges(nudges)
    console.print()


# ── calendar ───────────────────────────────────────────────────────────────────

def cmd_calendar(args: argparse.Namespace) -> None:
    state = startup_check()
    config = storage.load_config()
    today = date.today().isoformat()

    if getattr(args, "add", False):
        _calendar_add()
    elif getattr(args, "delete", False):
        _calendar_delete()
    else:
        _calendar_show(today, days_ahead=7, config=config)


def _calendar_show(today: str, days_ahead: int, config) -> None:
    from datetime import timedelta

    type_styles = {
        "event":   "cyan",
        "block":   "blue",
        "workout": "green",
        "meeting": "yellow",
    }
    type_icons = {
        "event":   "◆",
        "block":   "■",
        "workout": "◉",
        "meeting": "●",
    }

    console.print()
    for i in range(days_ahead + 1):
        d = (date.fromisoformat(today) + timedelta(days=i)).isoformat()
        day_type = storage.get_day_type(d, config)
        entries = storage.get_calendar_entries(d)

        if i > 0 and not entries:
            continue

        dow_label = date.fromisoformat(d).strftime("%a")
        day_label = {"office": "office", "wfh": "WFH", "off": "off"}.get(day_type, "")
        title_str = f"[bold]{d}[/bold] [dim]{dow_label} · {day_label}[/dim]"

        if entries:
            tbl = Table(box=None, show_header=False, padding=(0, 1))
            tbl.add_column(style="dim", width=6, no_wrap=True)
            tbl.add_column(width=2, no_wrap=True)
            tbl.add_column(min_width=22)
            tbl.add_column(style="dim")

            for e in entries:
                etype = e.entry_type.value if hasattr(e.entry_type, "value") else str(e.entry_type)
                style = type_styles.get(etype, "white")
                icon  = type_icons.get(etype, "·")
                time_str = e.start_time or ""
                tbl.add_row(
                    time_str,
                    f"[{style}]{icon}[/{style}]",
                    f"[{style}]{e.title}[/{style}]",
                    e.notes or "",
                )
            content = tbl
        else:
            content = "[dim]No events.[/dim]"

        border = "cyan" if i == 0 else "dim"
        console.print(Panel(content, title=title_str, border_style=border, padding=(0, 1)))

    console.print("[dim]/calendar --add to add an event or block[/dim]")
    console.print()


def _calendar_add() -> None:
    VALID_DAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}

    title = Prompt.ask("Title")
    if not title.strip():
        console.print("[red]Title required.[/red]")
        return

    type_str = Prompt.ask(
        "Type",
        choices=["event", "block", "workout", "meeting"],
        default="event",
    )

    recurring = Prompt.ask("Recurring? (y/n)", default="n").lower().startswith("y")

    recurs_on: list[str] = []
    entry_date: str | None = None

    if recurring:
        days_raw = Prompt.ask("Days (comma-separated, e.g. mon,wed,fri)", default="")
        recurs_on = [d.strip().lower() for d in days_raw.split(",") if d.strip()]
        invalid = [d for d in recurs_on if d not in VALID_DAYS]
        if invalid:
            console.print(f"[red]Invalid day(s): {', '.join(invalid)}. Use mon/tue/wed/thu/fri/sat/sun.[/red]")
            return
        if not recurs_on:
            console.print("[red]Must specify at least one day.[/red]")
            return
    else:
        date_raw = Prompt.ask("Date (YYYY-MM-DD)", default=date.today().isoformat())
        try:
            date.fromisoformat(date_raw)
            entry_date = date_raw
        except ValueError:
            console.print("[red]Invalid date format. Use YYYY-MM-DD.[/red]")
            return

    start_time_raw = Prompt.ask("Start time HH:MM (optional)", default="")
    start_time: str | None = None
    if start_time_raw.strip():
        if re.match(r"^\d{2}:\d{2}$", start_time_raw.strip()):
            start_time = start_time_raw.strip()
        else:
            console.print("[red]Invalid time format. Use HH:MM.[/red]")
            return

    end_time_raw = Prompt.ask("End time HH:MM (optional)", default="")
    end_time: str | None = None
    if end_time_raw.strip():
        if re.match(r"^\d{2}:\d{2}$", end_time_raw.strip()):
            end_time = end_time_raw.strip()
        else:
            console.print("[red]Invalid time format. Use HH:MM.[/red]")
            return

    notes_raw = Prompt.ask("Notes (optional)", default="")
    notes = notes_raw.strip() or None

    entry = CalendarEntry(
        title=title,
        entry_type=CalendarEntryType(type_str),
        recurs_on=recurs_on,
        date=entry_date,
        start_time=start_time,
        end_time=end_time,
        notes=notes,
    )
    storage.save_calendar_entry(entry)
    console.print(f"[green]Saved.[/green] [dim](id: {entry.id})[/dim]")


def _calendar_delete() -> None:
    """List all calendar entries and prompt to delete one."""
    import json as _json
    from viyugam.storage import CALENDAR_FILE
    raw = _json.loads(CALENDAR_FILE.read_text()) if CALENDAR_FILE.exists() else []
    if not raw:
        console.print("[dim]No calendar entries to delete.[/dim]")
        return

    tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold dim", padding=(0,1))
    tbl.add_column("#", style="dim", width=3)
    tbl.add_column("Title", min_width=22)
    tbl.add_column("When", style="dim")
    tbl.add_column("ID", style="dim")
    for i, e in enumerate(raw, 1):
        when = ", ".join(e.get("recurs_on") or []) or e.get("date", "—")
        tbl.add_row(str(i), e.get("title", ""), when, e.get("id", ""))
    console.print(tbl)

    choice = Prompt.ask("Delete which? (number or Enter to cancel)", default="")
    if not choice.strip() or not choice.strip().isdigit():
        return
    idx = int(choice.strip()) - 1
    if not (0 <= idx < len(raw)):
        console.print("[red]Out of range.[/red]")
        return
    entry_id = raw[idx]["id"]
    title = raw[idx].get("title", entry_id)
    if Confirm.ask(f"Delete '{title}'?", default=False):
        storage.delete_calendar_entry(entry_id)
        console.print(f"[green]Deleted.[/green]")


# ── log ────────────────────────────────────────────────────────────────────────

def _build_config_context(config) -> str:
    parts = []
    if config.season:
        parts.append(f"Season: {config.season.name}, focus: {config.season.focus.value}")
    if config.work_schedule:
        parts.append(f"Work: {config.work_schedule.start}-{config.work_schedule.end}")
    return "; ".join(parts)


def _log_entry(text: str, config=None, state=None) -> None:
    """Route a free-text entry to the right place using AI triage."""
    from viyugam.agents.chairman import triage_inbox

    if config is None:
        config = storage.load_config()
    if state is None:
        state = storage.load_state()

    if not text.strip():
        console.print("[red]Nothing to log.[/red]")
        return

    # Store raw in inbox first
    item = storage.append_inbox(text)

    # Triage via AI
    try:
        with console.status("[dim]Routing...[/dim]"):
            results = triage_inbox([text], config_context=_build_config_context(config))
    except Exception as e:
        console.print(f"[green]Captured to inbox.[/green] [dim](AI routing failed: {e})[/dim]")
        state = storage.touch_active(state)
        storage.save_state(state)
        return

    if not results:
        console.print("[green]Captured to inbox.[/green]")
        return

    result = results[0]
    rtype = result.get("type", "task")
    title = result.get("title", text[:80])

    storage.mark_inbox_processed([item.id])

    if rtype == "task":
        task = Task(
            title=title,
            dimension=result.get("dimension"),
            energy_cost=result.get("energy_cost", 5),
            estimated_minutes=result.get("estimated_minutes", 30),
            context=result.get("context"),
            notes=result.get("notes"),
            scheduled_date=date.today().isoformat(),
        )
        storage.save_task(task)
        dim = task.dimension.value if task.dimension else "—"
        console.print(f"[green]Task:[/green] {task.title} [dim]· {dim} · {task.estimated_minutes}m (id: {task.id})[/dim]")

    elif rtype == "habit":
        from viyugam.models import Recurrence
        task = Task(
            title=title,
            is_habit=True,
            recurrence=Recurrence.DAILY,
            dimension=result.get("dimension"),
            energy_cost=result.get("energy_cost", 3),
            estimated_minutes=result.get("estimated_minutes", 20),
            notes=result.get("notes"),
        )
        storage.save_task(task)
        console.print(f"[green]Habit:[/green] {task.title} [dim](id: {task.id})[/dim]")

    elif rtype == "goal":
        from viyugam.models import Goal, Dimension as _Dim
        dim_str = result.get("dimension", "career")
        try:
            dimension = _Dim(dim_str) if dim_str else None
        except ValueError:
            dimension = None
        goal = Goal(title=title, dimension=dimension or _Dim.CAREER)
        storage.save_goal(goal)
        console.print(f"[green]Goal:[/green] {goal.title} [dim](id: {goal.id})[/dim]")

    elif rtype == "slow_burn":
        sb = SlowBurn(title=title, notes=result.get("notes"), dimension=result.get("dimension"))
        storage.save_slow_burn(sb)
        console.print(f"[green]Slow burn:[/green] {sb.title} [dim](id: {sb.id})[/dim]")

    elif rtype == "event":
        entry = CalendarEntry(
            title=title,
            entry_type=CalendarEntryType.EVENT,
            date=date.today().isoformat(),
            notes=result.get("notes"),
        )
        storage.save_calendar_entry(entry)
        console.print(f"[green]Event:[/green] {entry.title} [dim](id: {entry.id})[/dim]")

    elif rtype == "transaction":
        txn = Transaction(
            amount=float(result.get("amount", 0)),
            category=result.get("category", "general"),
            description=result.get("description", title),
        )
        storage.save_transaction(txn)
        console.print(f"[green]Transaction:[/green] {txn.description} [dim]{config.currency}{txn.amount}[/dim]")

    elif rtype == "journal":
        # Just keep in inbox as processed, save to today's journal append
        existing = storage.load_journal() or ""
        note = f"\n---\n{text}\n"
        storage.save_journal(existing + note)
        console.print(f"[green]Journal note saved.[/green]")

    elif rtype == "review_flag":
        # Append to a review flags file
        flags_file = storage.HOME / "review_flags.md"
        existing = flags_file.read_text() if flags_file.exists() else ""
        flags_file.write_text(existing + f"\n- [{date.today().isoformat()}] {text}\n")
        console.print(f"[green]Flagged for review:[/green] {text[:60]}")

    else:
        console.print(f"[green]Captured.[/green] [dim](type: {rtype})[/dim]")

    state = storage.touch_active(state)
    storage.save_state(state)


def cmd_log(args: argparse.Namespace) -> None:
    state = startup_check()
    config = storage.load_config()

    # Check if text was passed directly
    text_parts = getattr(args, "text", None)
    if text_parts:
        text = " ".join(text_parts)
        _log_entry(text, config=config, state=state)
        return

    # No text → journal session (existing coach behaviour)
    _journal_session(args, state, config)


def _journal_session(args: argparse.Namespace, state, config) -> None:
    from viyugam.agents.coach import get_opener, chat_turn, generate_summary, format_journal_markdown

    today = date.today().isoformat()

    # Check if already logged today
    existing = storage.load_journal(today)
    if existing and not getattr(args, "force", False):
        if not Confirm.ask(f"You already logged today ({today}). Start a new session?"):
            return

    # Build context for opener
    tasks_today = storage.get_tasks(scheduled_date=today)
    season_context = _build_config_context(config)
    constitution = storage.load_constitution()
    memory_context = storage.get_memory_context()

    # Season drift check — surface in log if present
    drift = storage.get_season_drift(config)

    console.print()
    console.print(Panel(
        f"[bold]Evening Journal · {today}[/bold]",
        border_style="dim",
        padding=(0, 2),
    ))
    console.print("[dim]Type your thoughts. Press Enter to send. Type 'done' or 'quit' to finish.[/dim]\n")

    if drift:
        console.print(f"[yellow dim]  Season note: {drift}[/yellow dim]\n")

    # Get context-aware opener
    try:
        with console.status("[dim]...[/dim]"):
            opener = get_opener(
                user_name=config.user_name,
                context=season_context,
                today_tasks=[t.model_dump() for t in tasks_today],
                constitution=constitution,
                memory_context=memory_context,
            )
    except Exception:
        opener = "How was today?"

    console.print(f"[bold cyan]Coach:[/bold cyan] {opener}\n")

    # Conversation loop
    history = [{"role": "assistant", "content": opener}]
    max_turns = 10

    for turn in range(max_turns):
        try:
            user_input = Prompt.ask("[bold]You[/bold]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session ended.[/dim]")
            break

        if user_input.lower().strip() in ("done", "quit", "exit", "bye", "q"):
            break

        if not user_input.strip():
            continue

        history.append({"role": "user", "content": user_input})

        try:
            with console.status("[dim]...[/dim]"):
                response, ready = chat_turn(
                    history=history,
                    user_message=user_input,
                    config=config.model_dump(),
                    season_context=season_context,
                    constitution=constitution,
                    memory_context=memory_context,
                )
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            break

        history.append({"role": "assistant", "content": response})
        console.print(f"\n[bold cyan]Coach:[/bold cyan] {response}\n")

        if ready:
            break

    # Generate and save summary
    if len(history) > 1:
        console.print("\n[dim]Saving your journal...[/dim]")
        try:
            summary = generate_summary(history, today,
                                       constitution=constitution,
                                       memory_context=memory_context)
            markdown = format_journal_markdown(history, summary, today)
            path = storage.save_journal(markdown, today)
            console.print(f"[green]Saved.[/green] [dim]{path}[/dim]")

            # Show coach note
            if summary.get("coach_note"):
                console.print(f"\n[dim italic]  {summary['coach_note']}[/dim italic]")

            # Update state
            state = storage.touch_active(state)
            state.last_log = today
            storage.save_state(state)

        except Exception as e:
            console.print(f"[yellow]Could not save summary:[/yellow] {e}")
            # Still save raw conversation
            raw = "\n".join(
                f"{'Coach' if m['role'] == 'assistant' else 'You'}: {m['content']}"
                for m in history
            )
            storage.save_journal(f"# Journal · {today}\n\n{raw}\n", today)
            console.print(f"[dim]Raw conversation saved.[/dim]")
    else:
        console.print("[dim]Nothing to save.[/dim]")

    console.print()


# ── edit ───────────────────────────────────────────────────────────────────────

def cmd_edit(args: argparse.Namespace) -> None:
    state = startup_check()
    task_id = getattr(args, "task_id", None)
    task = storage.get_task_by_id(task_id) if task_id else None
    if not task:
        console.print("[yellow]Task not found.[/yellow]")
        return

    console.print(f"\n[dim]Editing:[/dim] {task.title}")
    new_title    = Prompt.ask("Title", default=task.title)
    new_energy   = Prompt.ask("Energy (1-10)", default=str(task.energy_cost))
    new_minutes  = Prompt.ask("Estimated minutes", default=str(task.estimated_minutes))
    new_date     = Prompt.ask("Scheduled date (YYYY-MM-DD or Enter to keep)", default=task.scheduled_date or "")
    new_notes    = Prompt.ask("Notes", default=task.notes or "")

    task.title             = new_title
    task.energy_cost       = int(new_energy) if new_energy.isdigit() else task.energy_cost
    task.estimated_minutes = int(new_minutes) if new_minutes.isdigit() else task.estimated_minutes
    if new_date:
        try:
            date.fromisoformat(new_date)
            task.scheduled_date = new_date
        except ValueError:
            console.print("[yellow]Invalid date, keeping original.[/yellow]")
    task.notes = new_notes or None
    storage.save_task(task)
    console.print(f"[green]Updated.[/green] {task.title}")

    state = storage.touch_active(state)
    storage.save_state(state)


# ── reschedule ─────────────────────────────────────────────────────────────────

def cmd_reschedule(args: argparse.Namespace) -> None:
    import datetime as _dt
    state = startup_check()
    task_id  = getattr(args, "task_id", None)
    new_date = getattr(args, "new_date", None)

    task = storage.get_task_by_id(task_id) if task_id else None
    if not task:
        console.print("[yellow]Task not found.[/yellow]")
        return

    if not new_date:
        new_date = Prompt.ask("Reschedule to (YYYY-MM-DD, 'tomorrow', 'next-week')",
                              default=(date.today() + _dt.timedelta(days=1)).isoformat())

    # Resolve shortcuts
    if new_date == "tomorrow":
        new_date = (date.today() + _dt.timedelta(days=1)).isoformat()
    elif new_date == "next-week":
        new_date = (date.today() + _dt.timedelta(days=7)).isoformat()

    try:
        date.fromisoformat(new_date)
    except ValueError:
        console.print("[red]Invalid date.[/red]")
        return

    old_date = task.scheduled_date
    task.scheduled_date = new_date
    task.status = TaskStatus.TODO
    storage.save_task(task)
    console.print(f"[green]Rescheduled:[/green] {task.title} [dim]{old_date} → {new_date}[/dim]")

    state = storage.touch_active(state)
    storage.save_state(state)


# ── snooze ─────────────────────────────────────────────────────────────────────

def cmd_snooze(args: argparse.Namespace) -> None:
    import datetime as _dt
    startup_check()
    task_id = getattr(args, "task_id", None)
    task = storage.get_task_by_id(task_id) if task_id else None
    if not task:
        console.print("[yellow]Task not found.[/yellow]")
        return
    tomorrow = (date.today() + _dt.timedelta(days=1)).isoformat()
    task.scheduled_date = tomorrow
    task.status = TaskStatus.TODO
    storage.save_task(task)
    console.print(f"[green]Snoozed:[/green] {task.title} [dim]→ {tomorrow}[/dim]")


# ── backlog ────────────────────────────────────────────────────────────────────

def cmd_backlog(args: argparse.Namespace) -> None:
    startup_check()
    all_tasks = storage.get_tasks()
    backlog = [
        t for t in all_tasks
        if t.status in (TaskStatus.TODO, TaskStatus.BACKLOG)
        and not t.is_habit
        and (not t.scheduled_date or t.scheduled_date < date.today().isoformat())
    ]

    if not backlog:
        console.print("\n[dim]Backlog is empty.[/dim]\n")
        return

    console.print()
    tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold dim", padding=(0,1))
    tbl.add_column("ID", style="dim", width=8)
    tbl.add_column("Title", min_width=28)
    tbl.add_column("Dim", style="dim", width=12)
    tbl.add_column("Time", justify="right", style="dim", width=5)
    for t in backlog[:30]:
        dim = t.dimension.value if t.dimension else "—"
        tbl.add_row(t.id, t.title, dim, f"{t.estimated_minutes}m")

    console.print(Panel(tbl, title=f"[bold]Backlog[/bold] [dim]({len(backlog)} items)[/dim]", border_style="dim", padding=(0,1)))

    if len(backlog) > 30:
        console.print(f"[dim]  ... and {len(backlog)-30} more[/dim]")

    # Quick actions
    console.print()
    raw = Prompt.ask("Schedule an item? Enter ID (or Enter to exit)", default="")
    if not raw.strip():
        return
    task = storage.get_task_by_id(raw.strip())
    if not task:
        console.print("[red]Not found.[/red]")
        return
    new_date = Prompt.ask("Schedule for", default=date.today().isoformat())
    try:
        date.fromisoformat(new_date)
    except ValueError:
        console.print("[red]Invalid date.[/red]")
        return
    task.scheduled_date = new_date
    task.status = TaskStatus.TODO
    storage.save_task(task)
    console.print(f"[green]Scheduled:[/green] {task.title} → {new_date}")


# ── milestones ─────────────────────────────────────────────────────────────────

def cmd_milestones(args: argparse.Namespace) -> None:
    startup_check()
    config = storage.load_config()

    # Mark a milestone done
    done_id = getattr(args, "done", None)
    if done_id:
        milestones = storage.get_milestones()
        match = next((m for m in milestones if m.id == done_id or m.id.startswith(done_id)), None)
        if not match:
            console.print(f"[red]Milestone not found:[/red] {done_id}")
            return
        match.is_done = True
        storage.save_milestone(match)
        console.print(f"[green]Done:[/green] {match.title}")
        return

    if getattr(args, "add", False):
        title    = Prompt.ask("Milestone title")
        goals    = storage.get_goals()
        goal_id  = None
        if goals:
            console.print("\n[dim]Goals:[/dim]")
            for i, g in enumerate(goals, 1):
                console.print(f"  {i}. {g.title} [dim]({g.dimension.value})[/dim]")
            raw = Prompt.ask("Link to goal? (number or Enter to skip)", default="")
            if raw.strip().isdigit():
                idx = int(raw.strip()) - 1
                if 0 <= idx < len(goals):
                    goal_id = goals[idx].id
        due_date = Prompt.ask("Due date (YYYY-MM-DD or Enter)", default="")
        notes    = Prompt.ask("Notes (optional)", default="")
        m = Milestone(title=title, goal_id=goal_id,
                      due_date=due_date or None, notes=notes or None)
        storage.save_milestone(m)
        console.print(f"[green]Milestone added:[/green] {m.title} [dim](id: {m.id})[/dim]")
        return

    # List milestones grouped by goal
    milestones = storage.get_milestones()
    goals = {g.id: g for g in storage.get_goals(active_only=False)}

    if not milestones:
        console.print("\n[dim]No milestones yet.[/dim]\n"
                      "Add one: [bold]viyugam milestones --add[/bold]\n")
        return

    console.print()
    by_goal: dict[str | None, list] = {}
    for m in milestones:
        by_goal.setdefault(m.goal_id, []).append(m)

    for gid, ms in by_goal.items():
        goal_title = goals[gid].title if gid and gid in goals else "Unlinked"
        console.print(f"  [bold]{goal_title}[/bold]")
        for m in ms:
            done_mark = "[green]done[/green]" if m.is_done else "[dim]o[/dim]"
            due = f" [dim]due {m.due_date}[/dim]" if m.due_date else ""
            console.print(f"  {done_mark} [dim]{m.id}[/dim]  {m.title}{due}")
        console.print()


# ── slow burns ─────────────────────────────────────────────────────────────────

def cmd_slow_burns(args: argparse.Namespace) -> None:
    """Browse and manage the Slow Burns list."""
    startup_check()

    if getattr(args, "add", False):
        from viyugam.models import Dimension as _Dim
        title = Prompt.ask("What's the slow burn?")
        if not title.strip():
            return
        dims = [d.value for d in _Dim]
        dim_raw = Prompt.ask(f"Dimension ({'/'.join(dims)})", default="")
        dimension = _Dim(dim_raw.lower()) if dim_raw.lower() in dims else None
        notes = Prompt.ask("Notes (optional)", default="") or None
        item = SlowBurn(title=title.strip(), dimension=dimension, notes=notes)
        storage.save_slow_burn(item)
        console.print(f"[green]Added:[/green] {item.title} [dim](id: {item.id})[/dim]")
        return

    items = storage.get_slow_burns()
    if not items:
        console.print("\n[dim]No slow burns yet.[/dim]\n"
                      "These are long-horizon aspirations — things worth chipping away at.\n"
                      "Add one: [bold]/slow-burns --add[/bold]\n")
        return

    console.print()
    tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold dim", padding=(0,1))
    tbl.add_column("ID", style="dim", width=10)
    tbl.add_column("Title", min_width=30)
    tbl.add_column("Dimension", style="cyan", width=14)
    tbl.add_column("Last chipped", style="dim", width=13)
    for item in items:
        dim = item.dimension.value if item.dimension else "—"
        last = item.last_chipped or "never"
        tbl.add_row(item.id, item.title, dim, last)
    console.print(tbl)
    console.print()


# ── decisions ──────────────────────────────────────────────────────────────────

def cmd_decisions(args: argparse.Namespace) -> None:
    """Browse past boardroom decisions."""
    startup_check()

    decisions = storage.get_decisions()
    if not decisions:
        console.print("\n[dim]No decisions recorded yet.[/dim]\n"
                      "Run [bold]/think[/bold] to put a proposal through the boardroom.\n")
        return

    console.print()
    for d in sorted(decisions, key=lambda x: x.created_at, reverse=True):
        outcome_style = {
            "approved":    "green",
            "rejected":    "red",
            "conditional": "yellow",
        }.get(d.outcome, "white")
        title = f"[bold]{d.proposal[:60]}[/bold]  [{outcome_style}]{d.outcome.upper()}[/{outcome_style}]"
        if d.actual_outcome:
            body = f"{d.reasoning}\n\n[dim]Actual outcome:[/dim] {d.actual_outcome}"
        else:
            body = d.reasoning
            if d.condition:
                body += f"\n[dim]Condition:[/dim] {d.condition}"
        console.print(Panel(
            body,
            title=title,
            subtitle=f"[dim]{d.created_at[:10]} · {d.id}[/dim]",
            border_style="dim",
            padding=(0, 2),
        ))
    console.print()


# ── finance ────────────────────────────────────────────────────────────────────

def cmd_finance(args: argparse.Namespace) -> None:
    startup_check()
    config = storage.load_config()
    sub = getattr(args, "sub", None)

    if sub == "budget":
        _finance_budget(args)
    elif sub == "log":
        _finance_log(args)
    elif sub == "summary":
        _finance_summary(config)
    else:
        _finance_summary(config)


def _finance_summary(config) -> None:
    summaries = storage.get_budget_summary()
    recent_txns = storage.get_transactions()[-10:]

    console.print()
    if summaries:
        tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold dim", padding=(0,1))
        tbl.add_column("Budget", min_width=18)
        tbl.add_column("Limit", justify="right", style="dim")
        tbl.add_column("Spent", justify="right")
        tbl.add_column("Left", justify="right", style="green")
        tbl.add_column("%", justify="right", style="dim")
        for b in summaries:
            currency = config.currency
            color = "red" if b["pct"] > 90 else "yellow" if b["pct"] > 70 else "green"
            tbl.add_row(
                b["name"],
                f"{currency}{b['total_limit']:,.0f}",
                f"[{color}]{currency}{b['spent']:,.0f}[/{color}]",
                f"{currency}{b['remaining']:,.0f}",
                f"{b['pct']}%",
            )
        console.print(Panel(tbl, title="[bold]Budgets[/bold]", border_style="dim", padding=(0,1)))
    else:
        console.print("[dim]No budgets set up. Run: viyugam finance budget[/dim]")

    if recent_txns:
        console.print("\n[bold dim]Recent transactions:[/bold dim]")
        for t in recent_txns[-5:]:
            console.print(f"  [dim]{t.occurred_at[:10]}[/dim]  {t.description}  [cyan]{config.currency}{t.amount:,.0f}[/cyan]")
    console.print()


def _finance_budget(args) -> None:
    import calendar as _cal
    name    = Prompt.ask("Budget name (e.g. Monthly OpEx)")
    limit   = Prompt.ask("Total limit")
    start   = Prompt.ask("Period start (YYYY-MM-DD)", default=date.today().replace(day=1).isoformat())
    end_raw = Prompt.ask("Period end (YYYY-MM-DD)", default="")
    if not end_raw:
        today = date.today()
        last_day = _cal.monthrange(today.year, today.month)[1]
        end_raw = today.replace(day=last_day).isoformat()
    try:
        b = Budget(name=name, total_limit=float(limit), period_start=start, period_end=end_raw)
        storage.save_budget(b)
        console.print(f"[green]Budget created:[/green] {b.name} [dim](id: {b.id})[/dim]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")


def _finance_log(args) -> None:
    desc    = Prompt.ask("Description")
    amount  = Prompt.ask("Amount")
    cat     = Prompt.ask("Category", default="general")
    budgets = storage.get_budgets()
    budget_id = None
    if budgets:
        console.print("\n[dim]Budgets:[/dim]")
        for i, b in enumerate(budgets, 1):
            console.print(f"  {i}. {b.name} [dim](left: {b.total_limit - b.spent:,.0f})[/dim]")
        raw = Prompt.ask("Link to budget? (number or Enter to skip)", default="")
        if raw.strip().isdigit():
            idx = int(raw.strip()) - 1
            if 0 <= idx < len(budgets):
                budget_id = budgets[idx].id
    try:
        t = Transaction(amount=float(amount), category=cat, description=desc, budget_id=budget_id)
        storage.save_transaction(t)
        console.print(f"[green]Transaction logged:[/green] {t.description}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")


# ── constitution ───────────────────────────────────────────────────────────────

def cmd_constitution(args: argparse.Namespace) -> None:
    startup_check()
    existing = storage.load_constitution()

    if existing:
        console.print()
        console.print(Panel(existing, title="[bold]Your Constitution[/bold]", border_style="cyan", padding=(1,2)))
        if not Confirm.ask("\nEdit it?", default=False):
            return

    console.print(Panel(
        "[bold]Your Constitution[/bold]\n\n"
        "This is your values document. Write:\n"
        "- Core values\n"
        "- Non-negotiables (e.g. 'no work after 9pm')\n"
        "- Life principles\n"
        "- What you're optimising for\n\n"
        "[dim]The AI references this for all decisions.[/dim]",
        border_style="cyan", padding=(1,2)
    ))
    console.print("[dim]Type your constitution (blank line + Enter when done):[/dim]\n")

    lines = []
    try:
        while True:
            line = input()
            lines.append(line)
            if len(lines) >= 2 and lines[-1] == "" and lines[-2] == "":
                break
    except EOFError:
        pass

    content = "\n".join(lines).strip()
    if content:
        storage.save_constitution(content)
        # Mark constitution as existing so agents load it
        try:
            import yaml
            raw = yaml.safe_load(storage.CONFIG_FILE.read_text()) or {}
            raw["constitution_exists"] = True
            storage.CONFIG_FILE.write_text(yaml.dump(raw, allow_unicode=True))
        except Exception:
            pass
        console.print("\n[green]Constitution saved.[/green]")
    else:
        console.print("[yellow]Nothing saved.[/yellow]")


# ── think ───────────────────────────────────────────────────────────────────────

def cmd_think(args: argparse.Namespace) -> None:
    from viyugam.agents.boardroom import run_debate

    state = startup_check()
    config = storage.load_config()
    today = date.today().isoformat()

    proposal_parts = getattr(args, "proposal", None)

    # No args → show someday list
    if not proposal_parts:
        _cmd_someday_review(config, state, today)
        return

    proposal = " ".join(proposal_parts)
    _run_think(proposal, config, state, today, revisit_context=None)


def _run_think(
    proposal: str,
    config,
    state,
    today: str,
    revisit_context: dict | None = None,
) -> None:
    from viyugam.agents.boardroom import run_debate
    from viyugam.models import SomedayItem, Project

    season = config.season.model_dump() if config.season else None
    dimension_scores = storage.get_avg_dimension_scores(days=14)
    projects = storage.get_projects(status="active")
    goals = storage.get_goals()
    actual_season = storage.calculate_actual_season()

    console.print()
    console.print(Panel(
        f"[bold]\"{proposal}\"[/bold]",
        title="[bold cyan]The Boardroom[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    ))

    with console.status("[dim]The board is deliberating...[/dim]"):
        try:
            result = run_debate(
                proposal=proposal,
                season=season,
                dimension_scores=dimension_scores,
                active_projects=[p.model_dump() for p in projects],
                goals=[g.model_dump() for g in goals],
                actual_season=actual_season,
                revisit_context=revisit_context,
                run_premortem=True,
            )
        except Exception as e:
            console.print(f"[red]Boardroom error:[/red] {e}")
            return

    # Render transcript
    console.print()
    voice_colors = {"Vision": "blue", "Resource": "yellow", "Risk": "red"}
    vote_symbols = {"yes": "[green]YES[/green]", "no": "[red]NO[/red]", "conditional": "[yellow]CONDITIONAL[/yellow]"}

    for entry in result.get("transcript", []):
        voice = entry.get("voice", "")
        text = entry.get("text", "")
        vote = entry.get("vote", "").lower()
        color = voice_colors.get(voice, "white")
        vote_display = vote_symbols.get(vote, vote.upper())
        console.print(Panel(
            f"{text}\n\n[dim]Vote: {vote_display}[/dim]",
            title=f"[bold {color}]{voice}[/bold {color}]",
            border_style=color,
            padding=(0, 2),
        ))

    # Consensus
    consensus = result.get("consensus", "")
    summary = result.get("summary", "")
    condition = result.get("condition")

    consensus_color = {"approved": "green", "rejected": "red", "conditional": "yellow"}.get(consensus, "white")
    consensus_display = f"[bold {consensus_color}]{consensus.upper()}[/bold {consensus_color}]"

    console.print()
    console.print(Panel(
        f"{consensus_display}\n\n{summary}"
        + (f"\n\n[dim]Condition: {condition}[/dim]" if condition else ""),
        title="[bold]Consensus[/bold]",
        border_style="dim",
        padding=(1, 2),
    ))

    # Save decision record
    decision_record = Decision(
        proposal=proposal,
        outcome=consensus,
        reasoning=summary,
        voices=result.get("transcript", []),
        condition=condition,
    )
    storage.save_decision(decision_record)

    # Decision
    console.print()
    suggested = result.get("suggested_next", "defer")
    choice = Prompt.ask(
        "What would you like to do?",
        choices=["approve", "someday", "discard"],
        default=suggested if suggested in ("approve", "someday", "discard") else "someday",
    )

    if choice == "approve":
        # Create a project from the proposal
        project = Project(
            title=proposal[:80],
            description=summary,
        )
        storage.save_project(project)
        console.print(f"\n[green]Project created:[/green] {project.title} [dim](id: {project.id})[/dim]")
        console.print("[dim]Run 'viyugam plan' to start scheduling tasks for it.[/dim]")

    elif choice == "someday":
        revisit = Prompt.ask(
            "Revisit after (YYYY-MM-DD, or Enter to leave open)",
            default="",
        )
        item = SomedayItem(
            proposal=proposal,
            debate_transcript=result.get("transcript", []),
            consensus=consensus,
            deferred_reason=summary,
            revisit_after=revisit if revisit else None,
        )
        storage.save_someday(item)
        console.print(f"\n[dim]Saved to someday.[/dim] Run [bold]viyugam think[/bold] to revisit.")

    else:
        console.print("\n[dim]Discarded. Moving on.[/dim]")

    # Update state
    state = storage.touch_active(state)
    state.last_think = today
    storage.save_state(state)
    console.print()


def _cmd_someday_review(config, state, today: str) -> None:
    """Show someday list and optionally revisit an item."""
    items = storage.get_someday()

    if not items:
        console.print("\n[dim]Your someday list is empty.[/dim]")
        console.print("Use [bold]viyugam think \"proposal\"[/bold] to add decisions here.\n")
        return

    console.print()
    console.print(Panel(
        "[bold]Someday List[/bold]",
        border_style="dim",
        padding=(0, 2),
    ))

    # Show items
    for i, item in enumerate(items, 1):
        age_days = (date.today() - date.fromisoformat(item.created_at[:10])).days
        revisit_flag = ""
        if item.revisit_after and item.revisit_after <= today:
            revisit_flag = " [yellow]↻ ready to revisit[/yellow]"
        console.print(
            f"  [dim]{i}.[/dim]  [bold]{item.proposal}[/bold]{revisit_flag}\n"
            f"       [dim]{age_days} days ago · {item.consensus or 'no consensus recorded'}[/dim]"
        )

    console.print()
    choice = Prompt.ask(
        "Pick a number to revisit, or Enter to exit",
        default="",
    )

    if not choice.strip():
        console.print()
        return

    try:
        idx = int(choice.strip()) - 1
        item = items[idx]
    except (ValueError, IndexError):
        console.print("[red]Invalid selection.[/red]")
        return

    # Show original debate if available
    if item.debate_transcript:
        console.print(f"\n[dim]Original debate ({item.created_at[:10]}):[/dim]")
        for entry in item.debate_transcript:
            voice = entry.get("voice", "")
            text = entry.get("text", "")
            console.print(f"  [dim]{voice}:[/dim] {text}")
        console.print()

    action = Prompt.ask(
        "What would you like to do?",
        choices=["re-debate", "approve", "discard", "keep"],
        default="re-debate",
    )

    if action == "re-debate":
        storage.delete_someday(item.id)
        _run_think(item.proposal, config, state, today, revisit_context=item.model_dump())
    elif action == "approve":
        project = Project(title=item.proposal[:80], description=item.deferred_reason)
        storage.save_project(project)
        storage.delete_someday(item.id)
        console.print(f"\n[green]Project created:[/green] {project.title}")
    elif action == "discard":
        storage.delete_someday(item.id)
        console.print("\n[dim]Removed from someday.[/dim]")
    else:
        console.print("\n[dim]Kept.[/dim]")

    console.print()


# ── review ─────────────────────────────────────────────────────────────────────

def cmd_review(args: argparse.Namespace) -> None:
    from viyugam.agents.reviewer import (
        build_review_data, generate_briefing, review_turn,
        generate_review_summary, format_review_markdown,
    )

    state = startup_check()
    config = storage.load_config()
    today = date.today().isoformat()

    # Detect cadence
    cadence = _detect_cadence(state, args)

    cadence_labels = {
        "weekly": "Weekly Review",
        "monthly": "Monthly Review",
        "quarterly": "Quarterly Review",
    }
    days_map = {"weekly": 7, "monthly": 30, "quarterly": 90}
    days = days_map[cadence]
    cutoff = (date.today() - __import__("datetime").timedelta(days=days)).isoformat()

    console.print()
    console.print(Panel(
        f"[bold]{cadence_labels[cadence]} · {today}[/bold]",
        border_style="cyan",
        padding=(0, 2),
    ))
    console.print(f"[dim]  Covering the last {days} days.[/dim]\n")

    # Gather data
    all_tasks = storage.get_tasks()
    tasks_done = [
        t.model_dump() for t in all_tasks
        if t.status.value == "done"
        and t.scheduled_date and t.scheduled_date >= cutoff
    ]
    tasks_backlogged = [
        t.model_dump() for t in all_tasks
        if t.status.value == "backlog"
        and t.scheduled_date and t.scheduled_date >= cutoff
    ]
    habits = [h.model_dump() for h in storage.get_habits()]
    projects = [p.model_dump() for p in storage.get_projects()]
    goals = [g.model_dump() for g in storage.get_goals()]
    someday_items = [s.model_dump() for s in storage.get_someday()]
    dimension_scores = storage.get_avg_dimension_scores(days=days)
    journal_summaries = [
        s.model_dump() for s in storage.get_recent_summaries(days=days)
    ]
    season = config.season.model_dump() if config.season else None
    actual_season = storage.calculate_actual_season()

    review_data = build_review_data(
        cadence=cadence,
        tasks_done=tasks_done,
        tasks_backlogged=tasks_backlogged,
        habits=habits,
        projects=projects,
        goals=goals,
        someday_items=someday_items,
        dimension_scores=dimension_scores,
        journal_summaries=journal_summaries,
        season=season,
        actual_season=actual_season,
        today=today,
    )

    # Generate opening briefing
    with console.status("[dim]Preparing your review...[/dim]"):
        try:
            briefing = generate_briefing(review_data, cadence)
        except Exception as e:
            console.print(f"[red]Error generating briefing:[/red] {e}")
            return

    console.print(f"[bold cyan]Reviewer:[/bold cyan] {briefing}\n")
    console.print("[dim]Type your thoughts. 'done' or 'quit' to finish.[/dim]\n")

    # Conversation loop
    history = [{"role": "assistant", "content": briefing}]
    max_turns = 12

    # Quarterly: handle someday purge first
    if cadence == "quarterly":
        old_someday = [s for s in someday_items if _someday_days_old(s) > 90]
        if old_someday:
            console.print(f"[yellow]  {len(old_someday)} someday item(s) older than 90 days.[/yellow]")
            if Confirm.ask("  Review them now before we start?"):
                for item in old_someday:
                    console.print(f"\n  [dim]({_someday_days_old(item)}d old)[/dim] [bold]{item.get('proposal')}[/bold]")
                    action = Prompt.ask("  keep / discard", choices=["keep", "discard"], default="keep")
                    if action == "discard":
                        storage.delete_someday(item["id"])
                        console.print("  [dim]Removed.[/dim]")
            console.print()

    for _ in range(max_turns):
        try:
            user_input = Prompt.ask("[bold]You[/bold]")
        except (KeyboardInterrupt, EOFError):
            break

        if user_input.lower().strip() in ("done", "quit", "exit", "q"):
            break
        if not user_input.strip():
            continue

        history.append({"role": "user", "content": user_input})

        try:
            with console.status("[dim]...[/dim]"):
                response, complete = review_turn(history, user_input, cadence)
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            break

        history.append({"role": "assistant", "content": response})
        console.print(f"\n[bold cyan]Reviewer:[/bold cyan] {response}\n")

        if complete:
            break

    # Save review
    if len(history) > 1:
        console.print("\n[dim]Saving review...[/dim]")
        try:
            summary = generate_review_summary(history, cadence, today)
            markdown = format_review_markdown(briefing, history, summary, cadence, today)

            filename = f"review-{cadence}-{today}.md"
            path = storage.JOURNALS / filename
            path.write_text(markdown)
            console.print(f"[green]Saved.[/green] [dim]{path}[/dim]")

            if summary.get("next_focus"):
                console.print(
                    f"\n[bold]Next {cadence} focus:[/bold] {summary['next_focus']}"
                )
            if summary.get("coach_note"):
                console.print(f"[dim italic]  {summary['coach_note']}[/dim italic]")

        except Exception as e:
            console.print(f"[yellow]Could not save summary:[/yellow] {e}")

        # Weekly letter (weekly cadence only)
        if cadence == "weekly":
            try:
                from viyugam.agents.reviewer import generate_weekly_letter
                coherence = storage.compute_coherence_score(config, days=7)
                actuals   = [storage.get_plan_vs_actual(
                    (date.today() - __import__("datetime").timedelta(days=i)).isoformat()
                ) for i in range(7)]
                actuals   = [a for a in actuals if a]
                constitution = storage.load_constitution()
                memory_ctx   = storage.get_memory_context()
                letter = generate_weekly_letter(
                    review_data=review_data,
                    coherence=coherence,
                    actuals=actuals,
                    constitution=constitution,
                    memory_context=memory_ctx,
                )
                console.print()
                console.print(Panel(letter, title="[bold cyan]Your Week[/bold cyan]",
                                    border_style="cyan", padding=(1,2)))
            except Exception as e:
                console.print(f"[dim]Weekly letter skipped: {e}[/dim]")

        # Surface decisions due for review
        pending_decisions = storage.get_decisions_for_review(days=90)
        if pending_decisions:
            console.print(f"\n[yellow]{len(pending_decisions)} decision(s) from the past 90 days need outcome recording:[/yellow]")
            for d in pending_decisions[:3]:
                console.print(f"  [dim]{d.created_at[:10]}[/dim] {d.proposal[:60]} → [{d.outcome}]")
                outcome = Prompt.ask("  Actual outcome", default="skip")
                if outcome != "skip":
                    d.actual_outcome = outcome
                    d.revisited_at = date.today().isoformat()
                    storage.save_decision(d)

        # Quarterly: offer season reset
        if cadence == "quarterly" and config.season:
            console.print()
            if Confirm.ask("Update your season for next quarter?"):
                _update_season(config)

        state = storage.touch_active(state)
        state.last_review = today
        storage.save_state(state)

    console.print()


def _detect_cadence(state, args) -> str:
    """Detect review cadence from flags or last review date."""
    if getattr(args, "quarterly", False):
        return "quarterly"
    if getattr(args, "monthly", False):
        return "monthly"
    if getattr(args, "weekly", False):
        return "weekly"

    if not state.last_review:
        return "weekly"  # first review is weekly

    days_since = (date.today() - date.fromisoformat(state.last_review)).days
    if days_since >= 80:
        return "quarterly"
    elif days_since >= 25:
        return "monthly"
    else:
        return "weekly"


def _someday_days_old(item: dict) -> int:
    from datetime import datetime
    created = item.get("created_at", "")
    if not created:
        return 0
    try:
        d = datetime.fromisoformat(created).date()
        return (date.today() - d).days
    except Exception:
        return 0


def _update_season(config) -> None:
    import yaml
    console.print("\n[dim]Dimensions: health, wealth, career, relationships, joy, learning[/dim]")
    new_name = Prompt.ask("New season name", default="Q2 2026")
    new_focus = Prompt.ask("Primary focus", default=config.season.focus.value if config.season else "career")
    new_secondary = Prompt.ask("Secondary focus (optional)", default="")

    config_data = config.model_dump(exclude_none=True)
    config_data["season"] = {"name": new_name, "focus": new_focus}
    if new_secondary:
        config_data["season"]["secondary"] = new_secondary

    with open(storage.CONFIG_FILE, "w") as f:
        yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
    console.print(f"[green]Season updated.[/green] {new_name} — {new_focus}")


# ── goals ──────────────────────────────────────────────────────────────────────

def cmd_goals(args: argparse.Namespace) -> None:
    from viyugam.models import Goal, Dimension

    state = startup_check()
    config = storage.load_config()

    if getattr(args, "add", False):
        from viyugam.agents.boardroom import run_debate

        # Add a new goal
        title = " ".join(args.title) if args.title else Prompt.ask("Goal title")
        console.print("[dim]Dimensions: health, wealth, career, relationships, joy, learning[/dim]")
        dim_str = args.dimension or Prompt.ask("Dimension", default="career")
        try:
            dimension = Dimension(dim_str.lower())
        except ValueError:
            console.print(f"[red]Unknown dimension '{dim_str}'. Choose from: health, wealth, career, relationships, joy, learning[/red]")
            return

        # Gather context for boardroom debate
        season = config.season.model_dump() if config.season else None
        dimension_scores = storage.get_avg_dimension_scores(days=14)
        projects = storage.get_projects(status="active")
        existing_goals = storage.get_goals()
        actual_season = storage.calculate_actual_season()

        console.print()
        console.print(Panel(
            f"[bold]\"{title}\"[/bold]\n[dim]Dimension: {dim_str}[/dim]",
            title="[bold cyan]The Boardroom · Goal Review[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        ))

        with console.status("[dim]The board is deliberating...[/dim]"):
            try:
                result = run_debate(
                    proposal=f"Add long-term goal: {title} ({dim_str})",
                    season=season,
                    dimension_scores=dimension_scores,
                    active_projects=[p.model_dump() for p in projects],
                    goals=[g.model_dump() for g in existing_goals],
                    actual_season=actual_season,
                )
            except Exception as e:
                console.print(f"[red]Boardroom error:[/red] {e}")
                return

        # Render transcript
        console.print()
        voice_colors = {"Vision": "blue", "Resource": "yellow", "Risk": "red"}
        vote_symbols = {"yes": "[green]YES[/green]", "no": "[red]NO[/red]", "conditional": "[yellow]CONDITIONAL[/yellow]"}

        for entry in result.get("transcript", []):
            voice = entry.get("voice", "")
            text = entry.get("text", "")
            vote = entry.get("vote", "").lower()
            color = voice_colors.get(voice, "white")
            vote_display = vote_symbols.get(vote, vote.upper())
            console.print(Panel(
                f"{text}\n\n[dim]Vote: {vote_display}[/dim]",
                title=f"[bold {color}]{voice}[/bold {color}]",
                border_style=color,
                padding=(0, 2),
            ))

        consensus = result.get("consensus", "")
        summary = result.get("summary", "")
        condition = result.get("condition")

        consensus_color = {"approved": "green", "rejected": "red", "conditional": "yellow"}.get(consensus, "white")
        console.print()
        console.print(Panel(
            f"[bold {consensus_color}]{consensus.upper()}[/bold {consensus_color}]\n\n{summary}"
            + (f"\n\n[dim]Condition: {condition}[/dim]" if condition else ""),
            title="[bold]Consensus[/bold]",
            border_style="dim",
            padding=(1, 2),
        ))
        console.print()

        # Outcome handling
        should_save = False
        if consensus == "approved":
            should_save = True
        elif consensus == "conditional":
            if condition:
                console.print(f"[yellow]Condition:[/yellow] {condition}")
            should_save = Confirm.ask("Save goal anyway?", default=True)
        else:  # rejected
            should_save = Confirm.ask("Add goal anyway?", default=False)

        if should_save:
            goal = Goal(title=title, dimension=dimension)
            storage.save_goal(goal)
            console.print(f"[green]Goal added:[/green] {goal.title} [dim]({goal.dimension.value}) id: {goal.id}[/dim]")
        else:
            console.print("[dim]Goal not saved.[/dim]")
        return

    # List goals
    goals = storage.get_goals(active_only=False)
    if not goals:
        console.print(
            "\n[dim]No goals yet.[/dim]\n"
            "Add one: [bold]viyugam goals add \"Financial independence\" --dimension wealth[/bold]\n"
        )
        return

    console.print()
    console.print(Panel("[bold]Goals[/bold]", border_style="dim", padding=(0, 2)))

    by_dim: dict[str, list] = {}
    for g in goals:
        key = g.dimension.value if hasattr(g.dimension, "value") else str(g.dimension)
        by_dim.setdefault(key, []).append(g)

    for dim, dim_goals in sorted(by_dim.items()):
        console.print(f"\n  [bold]{dim.capitalize()}[/bold]")
        for g in dim_goals:
            active_marker = "" if g.is_active else " [dim](inactive)[/dim]"
            console.print(f"  [dim]{g.id}[/dim]  {g.title}{active_marker}")

    console.print()


# ── research ───────────────────────────────────────────────────────────────────

def cmd_research(args: argparse.Namespace) -> None:
    from viyugam.agents.researcher import run_research
    from rich.markdown import Markdown

    state = startup_check()
    topic = " ".join(args.topic)
    if not topic.strip():
        console.print("[red]Usage: viyugam research <topic>[/red]")
        return

    console.print()
    console.print(Panel(
        f"[bold]\"{topic}\"[/bold]",
        title="[bold cyan]Research[/bold cyan]",
        border_style="cyan",
        padding=(0, 2),
    ))

    status_text = ["Researching..."]

    def on_status(msg: str) -> None:
        status_text[0] = msg

    with console.status(f"[dim]{status_text[0]}[/dim]") as s:
        def update_status(msg: str) -> None:
            status_text[0] = msg
            s.update(f"[dim]{msg}[/dim]")

        try:
            content = run_research(topic, on_status=update_status)
        except Exception as e:
            console.print(f"[red]Research error:[/red] {e}")
            return

    if not content:
        console.print("[yellow]No results returned.[/yellow]")
        return

    console.print()
    console.print(Markdown(content))

    path = storage.save_research(topic, content)
    console.print(f"\n[green]Saved.[/green] [dim]{path}[/dim]\n")

    state = storage.touch_active(state)
    storage.save_state(state)


# ── setup ──────────────────────────────────────────────────────────────────────

def cmd_setup(args: argparse.Namespace) -> None:
    """Setup: create or update config.yaml. Existing values are preserved as defaults."""
    import yaml

    storage.ensure_dirs()

    # Load existing config so we never wipe settings the user already has
    existing = storage.load_config()
    is_update = storage.CONFIG_FILE.exists()

    if is_update:
        console.print(Panel(
            "[bold]Update Viyugam config.[/bold]\n\n"
            "Existing values shown as defaults — press Enter to keep them.",
            border_style="cyan",
            padding=(1, 2),
        ))
    else:
        console.print(Panel(
            "[bold]Welcome to Viyugam.[/bold]\n\n"
            "A personal Life OS. Let's get you set up.",
            border_style="cyan",
            padding=(1, 2),
        ))

    name      = Prompt.ask("\nWhat should I call you?", default=existing.user_name)
    hours     = Prompt.ask("Max work hours per day?", default=str(existing.work_hours_cap))
    day_start = Prompt.ask("Day start hour (24h, for mid-day detection)", default=str(existing.day_start))
    currency  = Prompt.ask("Currency symbol?", default=existing.currency)
    timezone  = Prompt.ask("Timezone?", default=existing.timezone)

    console.print("\n[bold]Current season[/bold] — what are you focused on this quarter?")
    console.print("[dim]Dimensions: health, wealth, career, relationships, joy, learning[/dim]")
    default_season_name = existing.season.name if existing.season else "Q1 2026"
    default_season_focus = existing.season.focus.value if existing.season else "career"
    default_season_secondary = existing.season.secondary.value if (existing.season and existing.season.secondary) else ""
    season_name      = Prompt.ask("Season name", default=default_season_name)
    season_focus     = Prompt.ask("Primary focus", default=default_season_focus)
    season_secondary = Prompt.ask("Secondary focus (optional)", default=default_season_secondary)

    console.print("\n[bold]Work schedule[/bold] — for planning awareness:")
    console.print("[dim]Affects how Claude schedules tasks during office vs WFH days.[/dim]")
    existing_ws = existing.work_schedule
    work_start  = Prompt.ask("Work start?", default=existing_ws.start if existing_ws else "09:00")
    work_end    = Prompt.ask("Work end?",   default=existing_ws.end   if existing_ws else "17:30")
    office_raw  = Prompt.ask("Office days? (e.g. mon,tue,thu)", default=",".join(existing_ws.office_days) if existing_ws else "mon,tue,thu")
    wfh_raw     = Prompt.ask("WFH days? (e.g. wed,fri)",        default=",".join(existing_ws.wfh_days)   if existing_ws else "wed,fri")
    office_days = [d.strip().lower() for d in office_raw.split(",") if d.strip()]
    wfh_days    = [d.strip().lower() for d in wfh_raw.split(",")    if d.strip()]

    # Build config — preserve api_key if it was already set
    config_data = {
        "user_name":      name,
        "work_hours_cap": int(hours),
        "day_start":      int(day_start),
        "currency":       currency,
        "timezone":       timezone,
        "season": {
            "name":  season_name,
            "focus": season_focus,
        },
    }
    if season_secondary:
        config_data["season"]["secondary"] = season_secondary
    if office_days or wfh_days:
        config_data["work_schedule"] = {
            "start": work_start, "end": work_end,
            "office_days": office_days, "wfh_days": wfh_days,
        }
    elif existing_ws:
        config_data["work_schedule"] = existing_ws.model_dump()
    if existing.api_key:
        config_data["api_key"] = existing.api_key  # always preserve

    with open(storage.CONFIG_FILE, "w") as f:
        yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

    verb = "Updated" if is_update else "Saved"
    console.print(f"\n[green]{verb}.[/green] Config at [dim]{storage.CONFIG_FILE}[/dim]")
    if not is_update:
        console.print("\nTry [bold]viyugam capture \"your first thought\"[/bold] to get started.\n")


# ── CLI wiring ─────────────────────────────────────────────────────────────────

def main() -> None:
    # Eagerly try to load API key from config (before argparse, so it's available everywhere)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        try:
            cfg = storage.load_config()
            if cfg.api_key:
                os.environ["ANTHROPIC_API_KEY"] = cfg.api_key
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        prog="viyugam",
        description="A personal Life OS — text-only, Claude-powered",
    )
    sub = parser.add_subparsers(dest="command", required=False)

    # capture
    p_capture = sub.add_parser("capture", help="Capture a thought to your inbox (deprecated: use log)")
    p_capture.add_argument("text", nargs="+", help="The thought to capture")

    # plan
    p_plan = sub.add_parser("plan", help="Build today's schedule")
    p_plan.add_argument("--replan", action="store_true", help="Replan from current time")

    # done
    p_done = sub.add_parser("done", help="Mark a task complete")
    p_done.add_argument("task_id", nargs="?", help="Task ID (or partial) — omit for picker")

    # status
    p_status = sub.add_parser("status", help="Quick overview of today")

    # log (replaces capture)
    p_log_new = sub.add_parser("log", help="Universal input — routes anything to the right place")
    p_log_new.add_argument("text", nargs="*", help="What to log (omit for journal session)")
    p_log_new.add_argument("--force", action="store_true", help="Force new journal session even if logged today")

    # edit
    p_edit = sub.add_parser("edit", help="Edit a task")
    p_edit.add_argument("task_id", help="Task ID")

    # reschedule
    p_reschedule = sub.add_parser("reschedule", help="Move a task to another date")
    p_reschedule.add_argument("task_id", help="Task ID")
    p_reschedule.add_argument("new_date", nargs="?", help="YYYY-MM-DD, 'tomorrow', or 'next-week'")

    # snooze
    p_snooze = sub.add_parser("snooze", help="Push a task to tomorrow")
    p_snooze.add_argument("task_id", help="Task ID")

    # backlog
    p_backlog = sub.add_parser("backlog", help="Browse and schedule from backlog")

    # milestones
    p_milestones = sub.add_parser("milestones", help="View and add milestones")
    p_milestones.add_argument("--add", action="store_true", help="Add a new milestone")
    p_milestones.add_argument("--done", metavar="ID", help="Mark a milestone done")

    # finance
    p_finance = sub.add_parser("finance", help="Budget and spending overview")
    p_finance_sub = p_finance.add_subparsers(dest="sub")
    p_finance_sub.add_parser("budget", help="Create a budget")
    p_finance_sub.add_parser("log", help="Log a transaction")
    p_finance_sub.add_parser("summary", help="Show summary")

    # constitution
    p_constitution = sub.add_parser("constitution", help="View and edit your values document")

    # think
    p_think = sub.add_parser("think", help="Decision gateway. No args = review someday list")
    p_think.add_argument("proposal", nargs="*", help="The proposal to debate")

    # review
    p_review = sub.add_parser("review", help="Weekly / monthly / quarterly review")
    p_review.add_argument("--weekly",    action="store_true", help="Force weekly mode")
    p_review.add_argument("--monthly",   action="store_true", help="Force monthly mode")
    p_review.add_argument("--quarterly", action="store_true", help="Force quarterly mode")

    # goals
    p_goals = sub.add_parser("goals", help="View and manage long-term goals")
    p_goals.add_argument("--add", action="store_true", help="Add a new goal")
    p_goals.add_argument("title", nargs="*", help="Goal title (when using --add)")
    p_goals.add_argument("--dimension", "-d", help="Dimension for the goal")

    # research
    p_research = sub.add_parser("research", help="Research a topic using web search")
    p_research.add_argument("topic", nargs="+", help="The topic to research")

    # calendar
    p_calendar = sub.add_parser("calendar", help="View and add calendar events/blocks")
    p_calendar.add_argument("--add", action="store_true", help="Add a new calendar entry")
    p_calendar.add_argument("--delete", action="store_true", help="Delete a calendar entry")

    # slow-burns
    p_slow_burns = sub.add_parser("slow-burns", help="Browse long-horizon aspirations")
    p_slow_burns.add_argument("--add", action="store_true", help="Add a new slow burn")

    # decisions
    p_decisions = sub.add_parser("decisions", help="Browse past boardroom decisions")

    # setup
    p_setup = sub.add_parser("setup", help="First-run configuration")

    args = parser.parse_args()

    # No subcommand → open interactive REPL
    if not args.command:
        from viyugam.repl import run_repl
        run_repl()
        return

    # Commands that require the API key
    ai_commands = {"plan", "log", "think", "review", "research"}
    if args.command in ai_commands:
        if not _check_api_key():
            sys.exit(1)

    _dispatch = {
        "capture":     cmd_capture,
        "plan":        cmd_plan,
        "done":        cmd_done,
        "status":      cmd_status,
        "calendar":    cmd_calendar,
        "log":         cmd_log,
        "edit":        cmd_edit,
        "reschedule":  cmd_reschedule,
        "snooze":      cmd_snooze,
        "backlog":     cmd_backlog,
        "milestones":  cmd_milestones,
        "slow-burns":  cmd_slow_burns,
        "decisions":   cmd_decisions,
        "finance":     cmd_finance,
        "constitution": cmd_constitution,
        "think":       cmd_think,
        "review":      cmd_review,
        "goals":       cmd_goals,
        "research":    cmd_research,
        "setup":       cmd_setup,
    }
    _dispatch[args.command](args)


if __name__ == "__main__":
    main()
