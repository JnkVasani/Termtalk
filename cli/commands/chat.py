"""
TermTalk Chat Command - Full Terminal UI
"""
import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.columns import Columns
from rich.style import Style
from rich.prompt import Prompt
from rich import print as rprint
import click

from cli.config import config
from cli.network.client import APIClient, WSClient, APIError
from cli.ui.theme import (
    print_banner, print_error, print_info, print_success,
    format_message, format_timestamp, THEME
)
from cli.ui.chat_ui import ChatUI

console = Console()


def require_auth():
    """Check authentication, prompt login if needed."""
    if not config.is_authenticated():
        print_error("Not logged in. Run [bold]termtalk login[/bold] first.")
        raise SystemExit(1)


async def chat_command(target_username: Optional[str] = None):
    """Main chat interface."""
    require_auth()

    ui = ChatUI(
        username=config.username,
        target=target_username,
    )
    await ui.run()


async def handle_command(
    cmd: str,
    current_room: str,
    ws: WSClient,
    api: APIClient,
    ui: "ChatUI",
) -> Optional[str]:
    """
    Handle slash commands.
    Returns new room name if room changed, else None.
    """
    parts = cmd.strip().split(maxsplit=2)
    command = parts[0].lower()

    # /msg username message
    if command == "/msg":
        if len(parts) < 3:
            ui.add_system("Usage: /msg <username> <message>")
            return None
        target = parts[1]
        content = parts[2]
        dm_room = "dm_" + "_".join(sorted([config.username, target]))

        # Ensure DM room exists
        try:
            await api.post(f"/api/v1/friends/accept/{target}")
        except APIError:
            pass

        await ws.join_room(dm_room)
        await ws.send_message(dm_room, content)
        return dm_room

    # /create-room name
    elif command in ("/create-room", "/create"):
        if len(parts) < 2:
            ui.add_system("Usage: /create-room <name>")
            return None
        name = parts[1].lower()
        try:
            result = await api.post("/api/v1/rooms/", {"name": name})
            ui.add_system(f"✅ Room '{name}' created! Joining now...")
            await ws.join_room(name)
            return name
        except APIError as e:
            ui.add_system(f"❌ {e.message}")

    # /join room
    elif command == "/join":
        if len(parts) < 2:
            ui.add_system("Usage: /join <room>")
            return None
        name = parts[1].lower()
        try:
            await api.post(f"/api/v1/rooms/{name}/join")
            await ws.join_room(name)
            ui.add_system(f"✅ Joined #{name}")
            return name
        except APIError as e:
            ui.add_system(f"❌ {e.message}")

    # /leave
    elif command == "/leave":
        if current_room:
            try:
                await api.post(f"/api/v1/rooms/{current_room}/leave")
                await ws.leave_room(current_room)
                ui.add_system(f"Left #{current_room}")
                return "general"
            except APIError as e:
                ui.add_system(f"❌ {e.message}")

    # /history [room]
    elif command == "/history":
        room = parts[1] if len(parts) > 1 else current_room
        try:
            result = await api.get(f"/api/v1/messages/history/{room}")
            ui.add_system(f"--- History for #{room} ---")
            for msg in result.get("messages", []):
                ts = format_timestamp(msg["timestamp"])
                ui.add_message(
                    sender=msg["sender"],
                    content=msg["content"],
                    timestamp=ts,
                    is_history=True,
                )
        except APIError as e:
            ui.add_system(f"❌ {e.message}")

    # /sendfile username filepath or /sendfile filepath (to current room)
    elif command in ("/sendfile", "/file"):
        if len(parts) < 2:
            ui.add_system("Usage: /sendfile <filepath> OR /sendfile <username> <filepath>")
            return None

        # Determine if second arg is a username or path
        if len(parts) >= 3:
            recipient = parts[1]
            filepath = parts[2]
        else:
            recipient = None
            filepath = parts[1]

        path = Path(filepath).expanduser()
        if not path.exists():
            ui.add_system(f"❌ File not found: {filepath}")
            return None

        ui.add_system(f"📤 Uploading {path.name}...")
        try:
            result = await api.upload_file(
                path,
                room=None if recipient else current_room,
                recipient=recipient,
            )
            ui.add_system(f"✅ File sent: {result['filename']} ({_fmt_size(result['size'])})")
        except APIError as e:
            ui.add_system(f"❌ Upload failed: {e.message}")

    # /download file_id [path]
    elif command == "/download":
        if len(parts) < 2:
            ui.add_system("Usage: /download <file_id> [destination]")
            return None
        try:
            file_id = int(parts[1])
            dest_name = parts[2] if len(parts) > 2 else f"file_{file_id}"
            save_path = config.download_dir / dest_name

            ui.add_system(f"📥 Downloading file {file_id}...")

            def progress(downloaded, total):
                pct = int(downloaded / total * 100)
                ui.add_system(f"  Progress: {pct}%", replace_last=True)

            await api.download_file(file_id, save_path)
            ui.add_system(f"✅ Saved to: {save_path}")
        except (ValueError, APIError) as e:
            ui.add_system(f"❌ {e}")

    # /users
    elif command == "/users":
        try:
            result = await api.get("/api/v1/users/online")
            users = result.get("users", [])
            ui.add_system(f"🟢 Online users ({len(users)}):")
            for u in users:
                ui.add_system(f"  • {u['username']} ({u.get('display_name', '')})")
        except APIError as e:
            ui.add_system(f"❌ {e.message}")

    # /rooms
    elif command == "/rooms":
        try:
            result = await api.get("/api/v1/rooms/")
            rooms = result.get("rooms", [])
            ui.add_system(f"📢 Public rooms ({len(rooms)}):")
            for r in rooms:
                online = r.get("online_members", 0)
                ui.add_system(f"  • #{r['name']} — {r.get('description', '')} [{online} online]")
        except APIError as e:
            ui.add_system(f"❌ {e.message}")

    # /friends
    elif command == "/friends":
        try:
            result = await api.get("/api/v1/friends/list")
            friends = result.get("friends", [])
            if not friends:
                ui.add_system("No friends yet. Use /add <username> to add someone!")
            else:
                ui.add_system(f"👥 Friends ({len(friends)}):")
                for f in friends:
                    status = "🟢" if f["is_online"] else "⚫"
                    ui.add_system(f"  {status} {f['username']} ({f.get('display_name', '')})")
        except APIError as e:
            ui.add_system(f"❌ {e.message}")

    # /add username
    elif command == "/add":
        if len(parts) < 2:
            ui.add_system("Usage: /add <username>")
            return None
        try:
            await api.post(f"/api/v1/friends/add/{parts[1]}")
            ui.add_system(f"✅ Friend request sent to {parts[1]}")
        except APIError as e:
            ui.add_system(f"❌ {e.message}")

    # /accept username
    elif command == "/accept":
        if len(parts) < 2:
            ui.add_system("Usage: /accept <username>")
            return None
        try:
            await api.post(f"/api/v1/friends/accept/{parts[1]}")
            ui.add_system(f"✅ Now friends with {parts[1]}!")
        except APIError as e:
            ui.add_system(f"❌ {e.message}")

    # /help
    elif command in ("/help", "/h", "/?"):
        ui.add_system(_help_text())

    # /clear
    elif command == "/clear":
        ui.clear_messages()

    else:
        ui.add_system(f"Unknown command: {command}. Type /help for commands.")

    return None


def _help_text() -> str:
    return """
[bold cyan]TermTalk Commands[/bold cyan]
  /msg <user> <text>        Send a direct message
  /create-room <name>       Create a new room
  /join <room>              Join a room
  /leave                    Leave current room
  /rooms                    List public rooms
  /history [room]           View message history
  /sendfile <path>          Send file to current room
  /sendfile <user> <path>   Send file to a user
  /download <id> [path]     Download a file
  /users                    Show online users
  /friends                  Show friends list
  /add <user>               Send friend request
  /accept <user>            Accept friend request
  /clear                    Clear chat window
  /help                     Show this help
  Ctrl+C / /quit            Exit
""".strip()


def _fmt_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
