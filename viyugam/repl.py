"""
repl.py — Interactive REPL for Viyugam.
Launched when `viyugam` is called with no arguments.
"""
from __future__ import annotations
import argparse
import shlex
import shutil

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.table import Table

import viyugam.storage as storage

console = Console()


# ── Greeting ──────────────────────────────────────────────────────────────────

_ART_LINES = [
    "",
    "[bold cyan]                                 ____       _      __  __ [/bold cyan]",
    "[bold cyan] __   __  ___  __   __  _   _   / ___|   / \\   |  \\/  |[/bold cyan]",
    "[bold cyan] \\ \\ / / |_ _| \\ \\ / / | | | | | |  _   / _ \\  | |\\/| |[/bold cyan]",
    "[bold cyan]  \\ V /   | |   \\ V /  | |_| | | |_| | / ___ \\ | |  | |[/bold cyan]",
    "[bold cyan]   \\_/   |___|   |_|    \\___/   \\____/ /_/   \\_\\|_|  |_|[/bold cyan]",
    "",
    "[dim]               வியூகம்  ·  personal life OS[/dim]",
    "",
]


def _show_greeting() -> None:
    for line in _ART_LINES:
        console.print(line, justify="center")


# ── Commands ──────────────────────────────────────────────────────────────────

COMMANDS: dict[str, str] = {
    "plan":    "Build today's schedule",
    "log":     "Universal input — routes task/journal/habit/goal/event  /log <text>",
    "done":    "Mark a task complete            /done <id>",
    "edit":    "Edit a task                              /edit <id>",
    "reschedule": "Move task to another date                /reschedule <id> [date]",
    "snooze":  "Push task to tomorrow                    /snooze <id>",
    "backlog":  "Browse and schedule from backlog",
    "milestones": "View and add milestones          /milestones [--add] [--done <id>]",
    "slow-burns": "Long-horizon aspirations          /slow-burns [--add]",
    "decisions": "Browse past boardroom decisions",
    "finance":  "Budget and spending overview",
    "constitution": "View/edit your values document",
    "think":   "Boardroom debate                /think <proposal>  (no args = someday list)",
    "review":   "Weekly / monthly / quarterly review",
    "goals":    "View and manage goals",
    "research": "Research a topic using web search   /research <topic>",
    "status":   "Quick overview of today",
    "calendar": "View/add/delete calendar events    /calendar [--add|--delete]",
    "okrs":    "View OKRs by quarter",
    "horizon": "4-12 week forward view",
    "find":    "Semantic search  /find <query>",
    "setup":    "Update configuration",
    "help":     "Show this help",
    "exit":     "Exit Viyugam",
    "capture":  "[dim]Deprecated — use /log[/dim]",
}

# All completions including flags — shown when user types /
_COMPLETIONS = [
    "/plan", "/plan --replan",
    "/capture ",
    "/done ",
    "/log ", "/log",
    "/edit ",
    "/reschedule ", "/reschedule ",
    "/snooze ",
    "/backlog",
    "/milestones", "/milestones --add", "/milestones --done ",
    "/finance", "/finance budget", "/finance log", "/finance summary",
    "/finance history", "/finance recurring", "/finance insights",
    "/constitution",
    "/think", "/think ",
    "/review", "/review --weekly", "/review --monthly", "/review --quarterly",
    "/goals", "/goals --add ",
    "/research ",
    "/status",
    "/calendar", "/calendar --add", "/calendar --delete",
    "/slow-burns", "/slow-burns --add",
    "/decisions",
    "/okrs",
    "/horizon",
    "/find ",
    "/setup",
    "/help",
    "/exit",
]


# ── Completer ─────────────────────────────────────────────────────────────────

class _SlashCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith("/"):
            return
        for candidate in _COMPLETIONS:
            if candidate.lower().startswith(text.lower()):
                yield Completion(
                    candidate[len(text):],
                    start_position=0,
                    display=candidate.rstrip(),
                )


# ── Help ──────────────────────────────────────────────────────────────────────

def _show_help() -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="cyan", no_wrap=True)
    table.add_column(style="dim")
    for cmd, desc in COMMANDS.items():
        table.add_row(f"/{cmd}", desc)
    console.print()
    console.print(table)
    console.print()


# ── Task picker ───────────────────────────────────────────────────────────────

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
            # Filter by title/id
            filtered = [
                t for t in active
                if raw.lower() in t.title.lower() or raw.lower() in t.id.lower()
            ]
            if not filtered:
                console.print("[yellow]No match.[/yellow] Try again or Enter to cancel.")
            else:
                current = filtered
                _render(current)


# ── Dispatcher ────────────────────────────────────────────────────────────────

def _dispatch(line: str) -> None:
    """Parse a slash command line and call the appropriate cmd_* function."""
    from viyugam.main import (
        cmd_capture, cmd_plan, cmd_done, cmd_log, cmd_edit,
        cmd_reschedule, cmd_snooze, cmd_backlog, cmd_milestones,
        cmd_slow_burns, cmd_decisions,
        cmd_finance, cmd_constitution,
        cmd_think, cmd_review, cmd_goals, cmd_status, cmd_setup,
        cmd_research, cmd_calendar, _check_api_key,
        cmd_okrs, cmd_horizon, cmd_find,
    )

    # Strip leading slash
    if line.startswith("/"):
        line = line[1:]

    try:
        parts = shlex.split(line)
    except ValueError as e:
        console.print(f"[red]Parse error:[/red] {e}")
        return

    if not parts:
        return

    cmd = parts[0].lower()
    rest = parts[1:]
    flags = set(rest)

    AI_COMMANDS = {"plan", "log", "think", "review", "research"}

    if cmd in AI_COMMANDS and not _check_api_key():
        return

    if cmd == "plan":
        cmd_plan(argparse.Namespace(replan="--replan" in flags))

    elif cmd in ("capture", "c"):
        if not rest:
            console.print("[yellow]Usage:[/yellow] /capture <text>")
            return
        cmd_capture(argparse.Namespace(text=rest))

    elif cmd == "done":
        task_id = rest[0] if rest else None
        cmd_done(argparse.Namespace(task_id=task_id))

    elif cmd == "log":
        if not _check_api_key():
            return
        cmd_log(argparse.Namespace(text=rest if rest else None, force="--force" in flags))

    elif cmd == "edit":
        if not rest:
            console.print("[yellow]Usage:[/yellow] /edit <task-id>")
            return
        cmd_edit(argparse.Namespace(task_id=rest[0]))

    elif cmd == "reschedule":
        if not rest:
            console.print("[yellow]Usage:[/yellow] /reschedule <task-id> [date]")
            return
        cmd_reschedule(argparse.Namespace(
            task_id=rest[0],
            new_date=rest[1] if len(rest) > 1 else None,
        ))

    elif cmd == "snooze":
        if not rest:
            console.print("[yellow]Usage:[/yellow] /snooze <task-id>")
            return
        cmd_snooze(argparse.Namespace(task_id=rest[0]))

    elif cmd == "backlog":
        cmd_backlog(argparse.Namespace())

    elif cmd == "finance":
        sub = rest[0] if rest and rest[0] in (
            "budget", "log", "summary", "history", "recurring", "insights"
        ) else "summary"
        cmd_finance(argparse.Namespace(sub=sub))

    elif cmd == "constitution":
        cmd_constitution(argparse.Namespace())

    elif cmd == "think":
        if not rest:
            task = _pick_task()
            if task is not None:
                context = task.notes or (task.dimension.value if task.dimension else "")
                proposal = f'"{task.title}"\n\nContext: {context}'
                cmd_think(argparse.Namespace(proposal=[proposal]))
                return
        cmd_think(argparse.Namespace(proposal=rest))

    elif cmd == "review":
        cmd_review(argparse.Namespace(
            weekly="--weekly" in flags,
            monthly="--monthly" in flags,
            quarterly="--quarterly" in flags,
        ))

    elif cmd == "goals":
        # /goals --add title words --dimension career
        add = "--add" in flags
        dimension = None
        title_parts = []
        i = 0
        while i < len(rest):
            if rest[i] in ("--dimension", "-d") and i + 1 < len(rest):
                dimension = rest[i + 1]
                i += 2
            elif rest[i] == "--add":
                i += 1
            else:
                title_parts.append(rest[i])
                i += 1
        cmd_goals(argparse.Namespace(add=add, title=title_parts, dimension=dimension))

    elif cmd == "research":
        if not rest:
            task = _pick_task()
            if task is None:
                return
            topic = f"{task.title} {task.notes or ''}".strip()
            cmd_research(argparse.Namespace(topic=[topic]))
            return
        cmd_research(argparse.Namespace(topic=rest))

    elif cmd == "status":
        cmd_status(argparse.Namespace())

    elif cmd == "calendar":
        add = "--add" in flags
        delete = "--delete" in flags
        cmd_calendar(argparse.Namespace(add=add, delete=delete))

    elif cmd in ("slow-burns", "slowburns"):
        cmd_slow_burns(argparse.Namespace(add="--add" in flags))

    elif cmd == "decisions":
        cmd_decisions(argparse.Namespace())

    elif cmd == "milestones":
        done_id = None
        add = "--add" in flags
        if "--done" in rest:
            idx = rest.index("--done")
            if idx + 1 < len(rest):
                done_id = rest[idx + 1]
        cmd_milestones(argparse.Namespace(add=add, done=done_id))

    elif cmd == "okrs":
        cmd_okrs(argparse.Namespace())

    elif cmd == "horizon":
        cmd_horizon(argparse.Namespace())

    elif cmd == "find":
        cmd_find(argparse.Namespace(query=rest))

    elif cmd == "setup":
        cmd_setup(argparse.Namespace())

    elif cmd in ("help", "?"):
        _show_help()

    elif cmd in ("exit", "quit", "q"):
        raise SystemExit(0)

    else:
        console.print(f"[red]Unknown command:[/red] /{cmd}   (type /help for commands)")


# ── Visual style ─────────────────────────────────────────────────────────────

_STYLE = Style.from_dict({
    "prompt":         "#ffffff bold",
    "border":         "#555555",
    "bottom-toolbar": "bg:#1a1a1a #555555",
})


def _cols() -> int:
    return shutil.get_terminal_size().columns


def _bottom_toolbar() -> HTML:
    inner = _cols() - 2
    hints = "  /help · Tab · Ctrl-D to exit  "
    side = (inner - len(hints)) // 2
    return HTML(
        f'<bottom-toolbar>╰{"─" * side}{hints}{"─" * (inner - side - len(hints))}╯</bottom-toolbar>'
    )


def _prompt_message() -> HTML:
    """Top border + prompt rendered as one atomic prompt_toolkit message."""
    inner = _cols() - 2
    top = f'╭{"─" * inner}╮\n'
    return HTML(f'<border>{top}│</border> <prompt>›</prompt> ')


# ── REPL entry ────────────────────────────────────────────────────────────────

def run_repl() -> None:
    """Start the interactive Viyugam session."""
    import os
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
        completer=_SlashCompleter(),
        complete_while_typing=True,
        bottom_toolbar=_bottom_toolbar,
        style=_STYLE,
    )

    _show_greeting()

    while True:
        try:
            text = session.prompt(_prompt_message)
        except KeyboardInterrupt:
            console.print()
            continue
        except EOFError:
            console.print("\n[dim]Goodbye.[/dim]\n")
            break

        text = text.strip()
        if not text:
            continue

        # Bare exit/quit without slash
        if text.lower() in ("exit", "quit", "q"):
            console.print("\n[dim]Goodbye.[/dim]\n")
            break

        # Non-slash input: hint
        if not text.startswith("/"):
            console.print(
                "[dim]  Use /capture to add to inbox, or /help for all commands.[/dim]\n"
            )
            continue

        try:
            _dispatch(text)
        except SystemExit as e:
            if e.code == 0:
                console.print("\n[dim]Goodbye.[/dim]\n")
                break
            raise
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")

        console.print()  # breathing room between responses
