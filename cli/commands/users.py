"""
TermTalk Users Commands
"""
from rich.console import Console
from rich.table import Table

from cli.config import config
from cli.network.client import APIClient, APIError
from cli.ui.theme import print_error, print_info

console = Console()


def require_auth():
    if not config.is_authenticated():
        print_error("Not logged in. Run [bold]termtalk login[/bold] first.")
        raise SystemExit(1)


async def show_online():
    require_auth()
    api = APIClient()
    try:
        with console.status("[green]Fetching online users...[/green]"):
            result = await api.get("/api/v1/users/online")
        users = result.get("users", [])

        if not users:
            print_info("No users online right now.")
            return

        table = Table(title=f"🟢 Online Users ({result.get('count', 0)})", border_style="green")
        table.add_column("Username", style="bright_cyan")
        table.add_column("Display Name", style="white")

        for u in users:
            table.add_row(u["username"], u.get("display_name", ""))

        console.print(table)
    except APIError as e:
        print_error(f"Failed: {e.message}")
    finally:
        await api.close()


async def show_status():
    require_auth()
    api = APIClient()
    try:
        with console.status("[green]Loading profile...[/green]"):
            result = await api.get("/api/v1/users/me")

        console.print(f"\n[bold cyan]Profile[/bold cyan]")
        console.print(f"  Username:     [bold]{result['username']}[/bold]")
        console.print(f"  Display Name: {result.get('display_name', '—')}")
        console.print(f"  Email:        {result.get('email', '—')}")
        console.print(f"  Bio:          {result.get('bio', '—')}")
        console.print(f"  Member since: {result.get('created_at', '')[:10]}")
        console.print(f"  Server:       {config.server_url}")
        console.print()
    except APIError as e:
        print_error(f"Failed: {e.message}")
    finally:
        await api.close()
