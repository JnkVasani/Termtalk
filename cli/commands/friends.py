"""
TermTalk Friends Commands
"""
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from cli.config import config
from cli.network.client import APIClient, APIError
from cli.ui.theme import print_error, print_success, print_info, print_banner

console = Console()


def require_auth():
    if not config.is_authenticated():
        print_error("Not logged in. Run [bold]termtalk login[/bold] first.")
        raise SystemExit(1)


async def add_friend(username: str):
    require_auth()
    api = APIClient()
    try:
        with console.status(f"[green]Sending friend request to {username}...[/green]"):
            await api.post(f"/api/v1/friends/add/{username}")
        print_success(f"Friend request sent to [bold]{username}[/bold]! 📨")
    except APIError as e:
        print_error(f"Failed: {e.message}")
    finally:
        await api.close()


async def list_friends():
    require_auth()
    api = APIClient()
    try:
        with console.status("[green]Loading friends...[/green]"):
            result = await api.get("/api/v1/friends/list")
        friends = result.get("friends", [])

        if not friends:
            print_info("No friends yet. Use [bold]termtalk add <username>[/bold] to add someone!")
            return

        table = Table(title="👥 Your Friends", border_style="bright_black")
        table.add_column("Status", width=6)
        table.add_column("Username", style="cyan")
        table.add_column("Display Name", style="white")
        table.add_column("Last Seen", style="dim")

        for f in friends:
            status = "🟢" if f.get("is_online") else "⚫"
            last_seen = f.get("last_seen", "")[:16] if f.get("last_seen") else "—"
            table.add_row(status, f["username"], f.get("display_name", ""), last_seen)

        console.print(table)
    except APIError as e:
        print_error(f"Failed: {e.message}")
    finally:
        await api.close()


async def show_requests():
    require_auth()
    api = APIClient()
    try:
        with console.status("[green]Loading requests...[/green]"):
            result = await api.get("/api/v1/friends/requests")
        requests = result.get("requests", [])

        if not requests:
            print_info("No pending friend requests.")
            return

        table = Table(title="📨 Pending Friend Requests", border_style="bright_black")
        table.add_column("Username", style="cyan")
        table.add_column("Display Name", style="white")
        table.add_column("Sent", style="dim")

        for r in requests:
            table.add_row(
                r["username"],
                r.get("display_name", ""),
                r.get("sent_at", "")[:16],
            )

        console.print(table)
        console.print("\n[dim]Use [bold]termtalk chat[/bold] then [bold]/accept <username>[/bold] to accept[/dim]")
    except APIError as e:
        print_error(f"Failed: {e.message}")
    finally:
        await api.close()
