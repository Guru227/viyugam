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

# ── Commands ──────────────────────────────────────────────────────────────────

COMMANDS: dict[str, str] = {
    "plan":    "Build today's schedule",
    "capture": "Add a thought to inbox          /capture <text>",
    "done":    "Mark a task complete            /done <id>",
    "log":     "Evening journal session",
    "think":   "Boardroom debate                /think <proposal>  (no args = someday list)",
    "review":  "Weekly / monthly / quarterly review",
    "goals":   "View and manage goals",
    "status":  "Quick overview of today",
    "setup":   "Update configuration",
    "help":    "Show this help",
    "exit":    "Exit Viyugam",
}

# All completions including flags — shown when user types /
_COMPLETIONS = [
    "/plan", "/plan --replan",
    "/capture ",
    "/done ",
    "/log", "/log --force",
    "/think", "/think ",
    "/review", "/review --weekly", "/review --monthly", "/review --quarterly",
    "/goals", "/goals --add ",
    "/status",
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


# ── Dispatcher ────────────────────────────────────────────────────────────────

def _dispatch(line: str) -> None:
    """Parse a slash command line and call the appropriate cmd_* function."""
    from viyugam.main import (
        cmd_capture, cmd_plan, cmd_done, cmd_log,
        cmd_think, cmd_review, cmd_goals, cmd_status, cmd_setup,
        _check_api_key,
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

    AI_COMMANDS = {"plan", "log", "think", "review"}

    if cmd in AI_COMMANDS and not _check_api_key():
        return

    if cmd == "plan":
        cmd_plan(argparse.Namespace(replan="--replan" in flags))

    elif cmd == "capture":
        if not rest:
            console.print("[yellow]Usage:[/yellow] /capture <text>")
            return
        cmd_capture(argparse.Namespace(text=rest))

    elif cmd == "done":
        if not rest:
            console.print("[yellow]Usage:[/yellow] /done <task-id>")
            return
        cmd_done(argparse.Namespace(task_id=rest[0]))

    elif cmd == "log":
        cmd_log(argparse.Namespace(force="--force" in flags))

    elif cmd == "think":
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

    elif cmd == "status":
        cmd_status(argparse.Namespace())

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

    console.print(
        "\n[bold]வியூகம்[/bold]  "
        "[dim]· personal life OS[/dim]\n"
    )

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
