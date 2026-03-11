"""
TermTalk Config Command
"""
from rich.console import Console
from rich.prompt import Prompt

from cli.config import config
from cli.ui.theme import print_success, print_info

console = Console()


def configure():
    """Interactive configuration."""
    console.print("[bold cyan]TermTalk Configuration[/bold cyan]\n")

    server = Prompt.ask(
        "[cyan]Server URL[/cyan]",
        default=config.server_url,
    )
    config.server_url = server.rstrip("/")

    download_dir = Prompt.ask(
        "[cyan]Download directory[/cyan]",
        default=str(config.download_dir),
    )
    config.download_dir = download_dir

    print_success("Configuration saved!")
    console.print(f"  Server:    [dim]{config.server_url}[/dim]")
    console.print(f"  Downloads: [dim]{config.download_dir}[/dim]")
