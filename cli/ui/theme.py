"""
TermTalk UI Theme
"""
import re
from datetime import datetime
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.align import Align
from rich import print as rprint

console = Console()

THEME = {
    "primary": "bright_green",
    "secondary": "cyan",
    "accent": "bright_yellow",
    "error": "bold red",
    "warning": "yellow",
    "success": "bold green",
    "system": "dim italic",
    "self_msg": "white",
    "other_msg": "bright_white",
    "timestamp": "dim",
}

# Color pool for user names
USER_COLORS = [
    "bright_cyan", "bright_magenta", "bright_yellow",
    "bright_blue", "bright_red", "cyan", "magenta",
    "yellow", "blue", "green", "bright_green",
]


def get_user_color(username: str) -> str:
    """Get a consistent color for a username."""
    idx = sum(ord(c) for c in username) % len(USER_COLORS)
    return USER_COLORS[idx]


BANNER = r"""
  ______                  ______      ____  
 /_  __/__  _________ _  /_  __/___ _/ / /__
  / / / _ \/ ___/ __ `/   / / / __ `/ / //_/
 / / /  __/ /  / /_/ /   / / / /_/ / / ,<   
/_/  \___/_/   \__,_/   /_/  \__,_/_/_/|_|  
"""


def print_banner():
    """Print the TermTalk ASCII banner."""
    console.print(f"[bold bright_green]{BANNER}[/bold bright_green]")
    console.print(
        "[dim]  Terminal Communication Platform — Chat globally from your CLI[/dim]\n"
    )


def print_error(msg: str):
    console.print(f"[bold red]✗ {msg}[/bold red]")


def print_success(msg: str):
    console.print(f"[bold green]✓ {msg}[/bold green]")


def print_info(msg: str):
    console.print(f"[dim cyan]ℹ {msg}[/dim cyan]")


def print_warning(msg: str):
    console.print(f"[yellow]⚠ {msg}[/yellow]")


def format_timestamp(ts: str) -> str:
    """Format an ISO timestamp to human-readable."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        now = datetime.utcnow()
        if dt.date() == now.date():
            return dt.strftime("%H:%M")
        return dt.strftime("%m/%d %H:%M")
    except Exception:
        return ts[:16] if ts else ""


def format_message(sender: str, content: str, timestamp: str, is_self: bool = False) -> Text:
    """Format a chat message for display."""
    color = "bold bright_white" if is_self else f"bold {get_user_color(sender)}"
    text = Text()
    text.append(f"{timestamp} ", style="dim")
    text.append(f"{sender}: ", style=color)
    text.append(render_markdown_inline(content))
    return text


def render_markdown_inline(text: str) -> str:
    """Apply basic inline markdown rendering."""
    # Bold **text**
    text = re.sub(r'\*\*(.+?)\*\*', r'[bold]\1[/bold]', text)
    # Italic *text*
    text = re.sub(r'\*(.+?)\*', r'[italic]\1[/italic]', text)
    # Code `text`
    text = re.sub(r'`([^`]+)`', r'[bold bright_yellow on black] \1 [/bold bright_yellow on black]', text)
    # URLs
    text = re.sub(r'(https?://\S+)', r'[underline cyan]\1[/underline cyan]', text)
    return text
