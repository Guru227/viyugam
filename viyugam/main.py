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
    Task, Project, TaskStatus, ResilienceState, SystemState
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
    state = startup_check()
    text = " ".join(args.text)
    if not text.strip():
        console.print("[red]Nothing to capture.[/red]")
        return

    item = storage.append_inbox(text)
    console.print(f"[green]Captured.[/green] [dim](id: {item.id})[/dim]")

    inbox_count = len(storage.get_inbox(unprocessed_only=True))
    if inbox_count >= 5:
        console.print(
            f"[dim]{inbox_count} items in inbox — run [bold]viyugam plan[/bold] to process them.[/dim]"
        )

    state = storage.touch_active(state)
    storage.save_state(state)


# ── plan ───────────────────────────────────────────────────────────────────────

def cmd_plan(args: argparse.Namespace) -> None:
    from viyugam.agents.chairman import triage_inbox, plan_day

    state = startup_check()
    config = storage.load_config()
    today = date.today().isoformat()

    # 1. Auto-process inbox
    inbox_items = storage.get_inbox(unprocessed_only=True)
    if inbox_items:
        console.print(f"[dim]Processing {len(inbox_items)} inbox item(s)...[/dim]")
        _process_inbox_items(inbox_items, config)

    # 2. Gather context
    tasks_today = storage.get_tasks(scheduled_date=today)
    overdue = [
        t for t in storage.get_tasks(status="todo")
        if t.scheduled_date and t.scheduled_date < today and not t.is_habit
    ]
    all_tasks = tasks_today + [t for t in overdue if t not in tasks_today]
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

    # 3. Generate schedule
    with console.status("[dim]Building your schedule...[/dim]"):
        plan = plan_day(
            tasks=[t.model_dump() for t in all_tasks],
            habits=[h.model_dump() for h in habits],
            projects=[p.model_dump() for p in projects],
            goals=[g.model_dump() for g in goals],
            recent_journals=recent_journals,
            config=config.model_dump(),
            today=today,
            nudges=nudges,
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
    _render_plan(plan, today, config.user_name)

    state = storage.touch_active(state)
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
    human_territory_items = []

    for result in results:
        if result.get("human_territory") or result.get("type") == "human_territory":
            human_territory_items.append(result)
            processed_ids.append(_find_inbox_id(inbox_items, result.get("original", "")))
            continue

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
            console.print(f"  [green]+[/green] Task: [bold]{task.title}[/bold]")

        elif result.get("type") == "project":
            project = Project(
                title=result.get("title", result.get("original", "Untitled")),
                description=result.get("notes"),
            )
            storage.save_project(project)
            console.print(f"  [blue]+[/blue] Project: [bold]{project.title}[/bold]")

        elif result.get("type") == "note":
            console.print(f"  [dim]  Note kept: {result.get('title', result.get('original', ''))}[/dim]")

        processed_ids.append(_find_inbox_id(inbox_items, result.get("original", "")))

    # Handle human territory items
    if human_territory_items:
        console.print()
        for item in human_territory_items:
            console.print(Panel(
                f"[bold]\"{item.get('original', '')}\"[/bold]\n\n"
                "I could turn this into a task — but this might be one of those things "
                "that's better lived than tracked.\n\n"
                "The effort of remembering, or getting it delightfully wrong, "
                "is part of what makes it meaningful.\n\n"
                "[dim]Want to let this one stay human?[/dim]",
                border_style="yellow",
                padding=(1, 2),
            ))
            choice = Prompt.ask(
                "What would you like to do?",
                choices=["keep human", "add as task", "discard"],
                default="keep human",
            )
            if choice == "add as task":
                task = Task(
                    title=item.get("title", item.get("original", "Untitled")),
                    dimension=item.get("dimension"),
                    energy_cost=item.get("energy_cost", 3),
                    estimated_minutes=item.get("estimated_minutes", 30),
                )
                storage.save_task(task)
                console.print(f"  [green]+[/green] Added: [bold]{task.title}[/bold]")
            else:
                console.print("  [dim]Kept human. Good call.[/dim]")

    storage.mark_inbox_processed([pid for pid in processed_ids if pid])
    console.print()


def _find_inbox_id(inbox_items, original_text: str) -> str | None:
    for item in inbox_items:
        if item.content.strip() == original_text.strip():
            return item.id
    if inbox_items:
        return inbox_items[0].id
    return None


def _render_plan(plan: dict, today: str, user_name: str) -> None:
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

    # Schedule table
    if schedule:
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
        table.add_column("Time", style="cyan", width=7)
        table.add_column("", width=2)
        table.add_column("Task", min_width=30)
        table.add_column("Duration", justify="right", style="dim", width=9)
        table.add_column("Energy", justify="center", width=8)

        for item in schedule:
            time_str = item.get("time", "")
            duration = item.get("duration_mins", 0)
            title = item.get("title", "")
            energy = item.get("energy_cost", 0)
            item_type = item.get("type", "task")

            if item_type == "break":
                table.add_row(
                    time_str, "·",
                    Text("Break", style="dim italic"),
                    f"{duration}m", ""
                )
            elif item_type == "habit":
                table.add_row(
                    time_str, "◎",
                    Text(title, style="green"),
                    f"{duration}m",
                    _energy_bar(energy) if energy else "",
                )
            else:
                table.add_row(
                    time_str, "▸",
                    title,
                    f"{duration}m",
                    _energy_bar(energy) if energy else "",
                )

        console.print(table)

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
    task_id = args.task_id

    task = storage.get_task_by_id(task_id)
    if not task:
        # Maybe it's something unscheduled — offer to log it
        console.print(f"[yellow]No task found with id '{task_id}'.[/yellow]")
        if Confirm.ask("Did you complete something that wasn't on your list?"):
            title = Prompt.ask("What did you get done?")
            task = Task(
                title=title,
                status=TaskStatus.DONE,
                scheduled_date=date.today().isoformat(),
            )
            storage.save_task(task)
            console.print(f"[green]Logged:[/green] {task.title}")
            _handle_unscheduled_completion(task)
        return

    task.status = TaskStatus.DONE

    # Streak logic for habits
    if task.is_habit:
        today = date.today().isoformat()
        if task.last_done != today:
            task.streak += 1
            task.last_done = today
            console.print(
                f"[green]Done:[/green] {task.title} "
                f"[dim]· streak {task.streak} {'🔥' if task.streak >= 7 else ''}[/dim]"
            )
    else:
        console.print(f"[green]Done:[/green] {task.title}")

    storage.save_task(task)

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


# ── log ────────────────────────────────────────────────────────────────────────

def cmd_log(args: argparse.Namespace) -> None:
    from viyugam.agents.coach import get_opener, chat_turn, generate_summary, format_journal_markdown

    state = startup_check()
    config = storage.load_config()
    today = date.today().isoformat()

    # Check if already logged today
    existing = storage.load_journal(today)
    if existing and not getattr(args, "force", False):
        if not Confirm.ask(f"You already logged today ({today}). Start a new session?"):
            return

    # Build context for opener
    tasks_today = storage.get_tasks(scheduled_date=today)
    season_context = ""
    if config.season:
        season_context = f"Season: {config.season.name}, focus: {config.season.focus.value}"

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
            )
    except Exception as e:
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
            summary = generate_summary(history, today)
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
        # Add a new goal
        title = " ".join(args.title) if args.title else Prompt.ask("Goal title")
        console.print("[dim]Dimensions: health, wealth, career, relationships, joy, learning[/dim]")
        dim_str = args.dimension or Prompt.ask("Dimension", default="career")
        try:
            dimension = Dimension(dim_str.lower())
        except ValueError:
            console.print(f"[red]Unknown dimension '{dim_str}'. Choose from: health, wealth, career, relationships, joy, learning[/red]")
            return
        goal = Goal(title=title, dimension=dimension)
        storage.save_goal(goal)
        console.print(f"[green]Goal added:[/green] {goal.title} [dim]({goal.dimension.value}) id: {goal.id}[/dim]")
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


# ── setup ──────────────────────────────────────────────────────────────────────

def cmd_setup(args: argparse.Namespace) -> None:
    """First-run setup: create config.yaml with user preferences."""
    from viyugam.models import ViyugamConfig, SeasonConfig, Dimension
    import yaml

    console.print(Panel(
        "[bold]Welcome to Viyugam.[/bold]\n\n"
        "A personal Life OS. Let's get you set up.",
        border_style="cyan",
        padding=(1, 2),
    ))

    name = Prompt.ask("\nWhat should I call you?", default="friend")
    hours = Prompt.ask("Max work hours per day?", default="8")
    currency = Prompt.ask("Currency symbol?", default="₹")
    timezone = Prompt.ask("Timezone?", default="Asia/Kolkata")

    console.print("\n[bold]Current season[/bold] — what are you focused on this quarter?")
    console.print("[dim]Dimensions: health, wealth, career, relationships, joy, learning[/dim]")
    season_name = Prompt.ask("Season name", default="Q1 2026")
    season_focus = Prompt.ask("Primary focus", default="career")
    season_secondary = Prompt.ask("Secondary focus (optional)", default="")

    config_data = {
        "user_name": name,
        "work_hours_cap": int(hours),
        "currency": currency,
        "timezone": timezone,
        "season": {
            "name": season_name,
            "focus": season_focus,
        }
    }
    if season_secondary:
        config_data["season"]["secondary"] = season_secondary

    storage.ensure_dirs()
    with open(storage.CONFIG_FILE, "w") as f:
        yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

    console.print(f"\n[green]All set.[/green] Config saved to [dim]{storage.CONFIG_FILE}[/dim]")
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
    sub = parser.add_subparsers(dest="command", required=True)

    # capture
    p_capture = sub.add_parser("capture", help="Capture a thought to your inbox")
    p_capture.add_argument("text", nargs="+", help="The thought to capture")

    # plan
    p_plan = sub.add_parser("plan", help="Build today's schedule")

    # done
    p_done = sub.add_parser("done", help="Mark a task complete")
    p_done.add_argument("task_id", help="Task ID (or partial)")

    # status
    p_status = sub.add_parser("status", help="Quick overview of today")

    # log
    p_log = sub.add_parser("log", help="Evening journaling session")
    p_log.add_argument("--force", action="store_true", help="Start new session even if already logged today")

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

    # setup
    p_setup = sub.add_parser("setup", help="First-run configuration")

    args = parser.parse_args()

    # Commands that require the API key
    ai_commands = {"plan", "log", "think", "review"}
    if args.command in ai_commands:
        if not _check_api_key():
            sys.exit(1)

    dispatch = {
        "capture": cmd_capture,
        "plan":    cmd_plan,
        "done":    cmd_done,
        "status":  cmd_status,
        "log":     cmd_log,
        "think":   cmd_think,
        "review":  cmd_review,
        "goals":   cmd_goals,
        "setup":   cmd_setup,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
