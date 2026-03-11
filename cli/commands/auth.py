"""
TermTalk Auth Commands
"""
import asyncio
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.text import Text
from rich import print as rprint

from cli.config import config
from cli.network.client import APIClient, APIError
from cli.ui.theme import print_banner, print_success, print_error, print_info

console = Console()


async def register_command():
    """Interactive registration."""
    print_banner()
    console.print(Panel.fit(
        "[bold green]Create New Account[/bold green]",
        border_style="green",
    ))

    api = APIClient()

    try:
        username = Prompt.ask("[cyan]Username[/cyan]").strip()
        password = Prompt.ask("[cyan]Password[/cyan]", password=True).strip()
        confirm = Prompt.ask("[cyan]Confirm password[/cyan]", password=True).strip()

        if password != confirm:
            print_error("Passwords do not match!")
            return

        email = Prompt.ask("[cyan]Email (optional)[/cyan]", default="").strip() or None
        display_name = Prompt.ask("[cyan]Display name (optional)[/cyan]", default=username).strip()

        with console.status("[green]Creating account...[/green]"):
            result = await api.post("/api/v1/users/register", {
                "username": username,
                "password": password,
                "email": email,
                "display_name": display_name or username,
            })

        config.token = result["token"]
        config.username = result["username"]

        print_success(f"Welcome to TermTalk, [bold]{result['username']}[/bold]! 🎉")
        print_info("Run [bold]termtalk chat[/bold] to start chatting!")

    except APIError as e:
        print_error(f"Registration failed: {e.message}")
    finally:
        await api.close()


async def login_command():
    """Interactive login."""
    print_banner()
    console.print(Panel.fit(
        "[bold green]Login to TermTalk[/bold green]",
        border_style="green",
    ))

    if config.is_authenticated():
        print_info(f"Already logged in as [bold]{config.username}[/bold]")
        if not Confirm.ask("Login as different user?"):
            return

    api = APIClient()

    try:
        username = Prompt.ask("[cyan]Username[/cyan]").strip()
        password = Prompt.ask("[cyan]Password[/cyan]", password=True).strip()

        with console.status("[green]Logging in...[/green]"):
            result = await api.post("/api/v1/users/login", {
                "username": username,
                "password": password,
            })

        config.token = result["token"]
        config.username = result["username"]

        print_success(f"Welcome back, [bold]{result.get('display_name', username)}[/bold]! ✨")
        print_info("Run [bold]termtalk chat[/bold] to start chatting!")

    except APIError as e:
        print_error(f"Login failed: {e.message}")
    finally:
        await api.close()


def logout_command():
    """Logout current user."""
    if not config.is_authenticated():
        print_info("Not logged in.")
        return

    username = config.username
    config.clear_auth()
    print_success(f"Logged out [bold]{username}[/bold]. See you soon! 👋")
