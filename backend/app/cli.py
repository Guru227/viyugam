import typer
import requests
import json
import os
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

app = typer.Typer()
console = Console()

API_URL = "http://localhost:8000/api/v1"
TOKEN_FILE = ".token"

def get_token():
    if not os.path.exists(TOKEN_FILE):
        return None
    with open(TOKEN_FILE, "r") as f:
        return f.read().strip()

def get_headers():
    token = get_token()
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {"Authorization": "Bearer mock_token"}

@app.command()
def login(token: str):
    """Save the JWT token for future requests."""
    with open(TOKEN_FILE, "w") as f:
        f.write(token)
    console.print("[green]Logged in successfully (Token saved).[/green]")

@app.command()
def capture(text: str):
    """Send raw text to the Inbox/Agent for processing."""
    url = f"{API_URL}/agents/process-inbox"
    payload = {"items": [text]}
    try:
        response = requests.post(url, json=payload, headers=get_headers())
        if response.status_code == 200:
            console.print("[bold green]Captured![/bold green]")
            console.print_json(json.dumps(response.json()))
        else:
            console.print(f"[red]Error: {response.status_code}[/red]")
    except Exception as e:
        console.print(f"[red]Failed to connect: {e}[/red]")

@app.command()
def list():
    """List all tasks."""
    url = f"{API_URL}/tasks/"
    try:
        response = requests.get(url, headers=get_headers())
        if response.status_code == 200:
            tasks = response.json()
            table = Table(title="Daily Tasks")
            table.add_column("Status", justify="center", style="cyan", no_wrap=True)
            table.add_column("Title", style="white")
            table.add_column("Energy", justify="right", style="magenta")

            for t in tasks:
                status_icon = "✓" if t.get('status') == 'done' else "○"
                table.add_row(status_icon, t.get('title'), str(t.get('energy_cost')))
            
            console.print(table)
        else:
            console.print(f"[red]Error: {response.status_code}[/red]")
    except Exception as e:
        console.print(f"[red]Failed to connect: {e}[/red]")

@app.command()
def strategy(project_id: str):
    """Convene the Boardroom for a specific project."""
    console.print(f"[bold blue]Convening Boardroom for Project {project_id}...[/bold blue]")
    url = f"{API_URL}/agents/boardroom-meeting"
    payload = {"project_id": project_id}
    
    try:
        response = requests.post(url, json=payload, headers=get_headers())
        if response.status_code == 200:
            data = response.json()
            debate = data.get('debate')
            if not debate:
                console.print("[yellow]No debate returned.[/yellow]")
                return

            # Print Transcript
            console.print(Panel(f"[bold]Boardroom Session: {data.get('boardroom_id')}[/bold]", style="white on blue"))
            
            for turn in debate.get('transcript', []):
                speaker = turn.get('speaker')
                color = "cyan" if "Director" in speaker else "green"
                console.print(f"\n[{color} bold]{speaker}[/{color} bold]:")
                console.print(f"{turn.get('text')}")

            # Print Verdict
            verdict = debate.get('verdict')
            v_color = "green" if verdict == "APPROVED" else "red"
            console.print(Panel(f"[bold {v_color}]VERDICT: {verdict}[/bold {v_color}]\n{debate.get('summary')}", title="Final Decision"))
            
        else:
            console.print(f"[red]Error: {response.status_code} - {response.text}[/red]")
    except Exception as e:
        console.print(f"[red]Failed to connect: {e}[/red]")

@app.command()
def finance():
    """Get Financial Overview."""
    url = f"{API_URL}/finance/overview"
    try:
        response = requests.get(url, headers=get_headers())
        if response.status_code == 200:
            data = response.json()
            
            safe = data.get('safe_to_spend_daily', 0)
            color = "green" if safe > 0 else "red"
            
            console.print(Panel(
                f"[bold {color}]${safe:.2f}[/bold {color}]", 
                title="Safe To Spend (Daily)",
                subtitle=f"{data.get('days_remaining')} days remaining"
            ))
            
            table = Table(show_header=False, box=None)
            table.add_row("Total Budget", f"${data.get('total_budget')}")
            table.add_row("Total Spent", f"${data.get('total_spent')}")
            table.add_row("Remaining", f"${data.get('remaining')}")
            console.print(table)
            
        else:
             console.print(f"[red]Error: {response.status_code}[/red]")
    except Exception as e:
        console.print(f"[red]Failed to connect: {e}[/red]")


if __name__ == "__main__":
    app()
