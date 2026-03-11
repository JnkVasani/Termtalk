"""
TermTalk Chat UI - Rich Terminal Interface
"""
import asyncio
import sys
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from collections import deque

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.table import Table
from rich.align import Align
from rich.style import Style
from rich.rule import Rule
from rich.columns import Columns
from rich.markup import escape
import re

from cli.config import config
from cli.network.client import APIClient, WSClient, APIError
from cli.ui.theme import THEME, format_timestamp, render_markdown_inline, get_user_color


class Message:
    def __init__(self, sender: str, content: str, timestamp: str,
                 is_self: bool = False, is_system: bool = False,
                 is_history: bool = False, msg_type: str = "text"):
        self.sender = sender
        self.content = content
        self.timestamp = timestamp
        self.is_self = is_self
        self.is_system = is_system
        self.is_history = is_history
        self.msg_type = msg_type


class ChatUI:
    """Full-featured terminal chat interface."""

    MAX_MESSAGES = 200
    PROMPT_SYMBOL = "❯ "

    def __init__(self, username: str, target: Optional[str] = None):
        self.username = username
        self.target = target
        self.current_room = "general"
        self.messages: deque = deque(maxlen=self.MAX_MESSAGES)
        self.notifications: deque = deque(maxlen=10)
        self.online_users: List[str] = []
        self.typing_users: set = set()
        self.friends: List[Dict] = []
        self.ws: Optional[WSClient] = None
        self.api: Optional[APIClient] = None
        self.console = Console()
        self._input_buffer = ""
        self._running = False
        self._last_sender = None
        self._reconnect_count = 0

    async def run(self):
        """Main run loop."""
        self.api = APIClient()
        self._running = True

        # Determine initial room
        if self.target:
            self.current_room = "dm_" + "_".join(sorted([self.username, self.target]))
        else:
            self.current_room = "general"
            # Ensure general room exists
            try:
                await self.api.post("/api/v1/rooms/", {"name": "general", "description": "General chat"})
            except APIError:
                pass
            try:
                await self.api.post("/api/v1/rooms/general/join")
            except APIError:
                pass

        # Load history
        try:
            hist = await self.api.get(f"/api/v1/messages/history/{self.current_room}")
            for m in hist.get("messages", []):
                self.messages.append(Message(
                    sender=m["sender"],
                    content=m["content"],
                    timestamp=format_timestamp(m["timestamp"]),
                    is_self=(m["sender"] == self.username),
                    is_history=True,
                    msg_type=m.get("message_type", "text"),
                ))
        except APIError:
            pass

        # Load friends & online users
        await self._refresh_friends()
        await self._refresh_online_users()

        # Connect WebSocket
        self.ws = WSClient(on_message=self._on_ws_message)
        try:
            await self.ws.connect()
        except Exception as e:
            self._print_error(f"Cannot connect to server: {e}")
            self._print_info("Make sure the TermTalk server is running.")
            return

        await self.ws.join_room(self.current_room)

        # Run UI loop
        try:
            await self._ui_loop()
        finally:
            await self.ws.disconnect()
            await self.api.close()

    async def _ui_loop(self):
        """Main UI loop - render and handle input."""
        # Start background tasks
        ws_task = asyncio.create_task(self.ws.listen())
        refresh_task = asyncio.create_task(self._periodic_refresh())

        self._render_full()

        try:
            while self._running:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, self._read_input
                )
                if line is None:
                    break

                await self._handle_input(line.strip())
                self._render_full()
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            ws_task.cancel()
            refresh_task.cancel()
            self.console.print("\n[dim]Disconnected from TermTalk. Goodbye! 👋[/dim]")

    def _read_input(self) -> Optional[str]:
        """Read a line of input from terminal."""
        try:
            room_display = f"#{self.current_room}" if not self.current_room.startswith("dm_") else f"@{self._get_dm_partner()}"
            typing_hint = f" [{', '.join(self.typing_users)} typing...]" if self.typing_users else ""
            prompt = f"\n[{room_display}]{typing_hint} {self.PROMPT_SYMBOL}"
            self.console.print(prompt, end="", highlight=False)
            return input()
        except (EOFError, KeyboardInterrupt):
            return None

    async def _handle_input(self, text: str):
        """Handle user input."""
        if not text:
            return

        if text.lower() in ("/quit", "/exit", "/q"):
            self._running = False
            return

        if text.startswith("/"):
            # Import here to avoid circular
            from cli.commands.chat import handle_command
            new_room = await handle_command(text, self.current_room, self.ws, self.api, self)
            if new_room:
                self.current_room = new_room
                await self.ws.join_room(new_room)
                # Load history for new room
                try:
                    hist = await self.api.get(f"/api/v1/messages/history/{new_room}")
                    self.messages.clear()
                    for m in hist.get("messages", []):
                        self.messages.append(Message(
                            sender=m["sender"],
                            content=m["content"],
                            timestamp=format_timestamp(m["timestamp"]),
                            is_self=(m["sender"] == self.username),
                            is_history=True,
                        ))
                except APIError:
                    pass
        else:
            # Send message
            await self.ws.send_message(self.current_room, text)
            # Optimistic local display
            self.messages.append(Message(
                sender=self.username,
                content=text,
                timestamp=format_timestamp(datetime.utcnow().isoformat()),
                is_self=True,
            ))

    async def _on_ws_message(self, msg: dict):
        """Handle incoming WebSocket message."""
        msg_type = msg.get("type")

        if msg_type == "message":
            if msg.get("sender") != self.username:  # Don't double-display own messages
                self.messages.append(Message(
                    sender=msg["sender"],
                    content=msg.get("content", ""),
                    timestamp=format_timestamp(msg.get("timestamp", "")),
                    is_self=False,
                    msg_type=msg.get("message_type", "text"),
                ))
                self._add_notification(f"💬 {msg['sender']} in #{msg.get('room', '?')}")

        elif msg_type == "system":
            self.messages.append(Message(
                sender="system",
                content=msg.get("content", ""),
                timestamp=format_timestamp(msg.get("timestamp", "")),
                is_system=True,
            ))

        elif msg_type == "typing":
            username = msg.get("username")
            is_typing = msg.get("is_typing", True)
            if is_typing:
                self.typing_users.add(username)
            else:
                self.typing_users.discard(username)

        elif msg_type == "presence":
            username = msg.get("username")
            is_online = msg.get("is_online", False)
            if is_online:
                self._add_notification(f"🟢 {username} came online")
                if username not in self.online_users:
                    self.online_users.append(username)
            else:
                self._add_notification(f"⚫ {username} went offline")
                if username in self.online_users:
                    self.online_users.remove(username)

        elif msg_type == "friend_request":
            self._add_notification(f"👥 Friend request from {msg.get('from')}")

        elif msg_type == "friend_accepted":
            self._add_notification(f"✅ {msg.get('by')} accepted your friend request!")

        elif msg_type == "notification":
            content = msg.get("content", {})
            if isinstance(content, dict):
                sender = content.get("sender", "?")
                room = content.get("room", "?")
                preview = content.get("preview", "")
                self._add_notification(f"📩 {sender} in #{room}: {preview[:40]}")

    def _add_notification(self, text: str):
        self.notifications.append({"text": text, "time": datetime.now().strftime("%H:%M")})

    def add_message(self, sender: str, content: str, timestamp: str,
                    is_history: bool = False, msg_type: str = "text"):
        """Add a message to the chat."""
        self.messages.append(Message(
            sender=sender,
            content=content,
            timestamp=timestamp,
            is_self=(sender == self.username),
            is_history=is_history,
            msg_type=msg_type,
        ))

    def add_system(self, text: str, replace_last: bool = False):
        """Add a system message."""
        if replace_last and self.messages:
            last = self.messages[-1]
            if last.is_system:
                self.messages.pop()
        self.messages.append(Message(
            sender="system",
            content=text,
            timestamp=datetime.now().strftime("%H:%M"),
            is_system=True,
        ))

    def clear_messages(self):
        self.messages.clear()

    def _render_full(self):
        """Render the full chat UI."""
        os.system("clear" if os.name != "nt" else "cls")

        # Header
        self._render_header()

        # Notifications (recent 3)
        if self.notifications:
            recent = list(self.notifications)[-3:]
            notif_parts = " │ ".join(f"[dim]{n['time']}[/dim] {n['text']}" for n in recent)
            self.console.print(f"[dim on black] {notif_parts} [/dim on black]")

        self.console.print()

        # Main content: chat + sidebar
        self._render_chat_area()

        # Footer
        self._render_footer()

    def _render_header(self):
        """Render the header bar."""
        room_display = f"#{self.current_room}" if not self.current_room.startswith("dm_") else f"@{self._get_dm_partner()}"

        header = Table.grid(expand=True)
        header.add_column(ratio=1)
        header.add_column(justify="center", ratio=2)
        header.add_column(justify="right", ratio=1)

        header.add_row(
            f"[bold green]TermTalk[/bold green] [dim]v1.0[/dim]",
            f"[bold white]{room_display}[/bold white]",
            f"[green]●[/green] [cyan]{self.username}[/cyan]  [dim]{len(self.online_users)} online[/dim]",
        )

        self.console.print(Panel(header, style="on black", border_style="bright_black", padding=(0, 1)))

    def _render_chat_area(self):
        """Render messages + sidebar."""
        # Build message lines
        lines = []
        prev_sender = None

        for msg in list(self.messages)[-40:]:  # Last 40 messages
            if msg.is_system:
                lines.append(Text(f"  ─ {msg.content}", style="dim italic"))
                prev_sender = None
            else:
                # Group consecutive messages from same sender
                show_header = (msg.sender != prev_sender)
                prev_sender = msg.sender

                if show_header:
                    color = get_user_color(msg.sender)
                    name = f"[bold {color}]{escape(msg.sender)}[/bold {color}]"
                    if msg.is_self:
                        name = f"[bold bright_white]{escape(msg.sender)}[/bold bright_white]"
                    header_text = Text.from_markup(f"\n  {name}  [dim]{msg.timestamp}[/dim]")
                    lines.append(header_text)

                # Message content
                content = render_markdown_inline(msg.content)
                prefix = "    " if msg.is_self else "    "
                msg_style = "white" if msg.is_self else "bright_white"

                if msg.msg_type == "file":
                    content_text = Text(f"    {content}", style="cyan")
                else:
                    content_text = Text(f"    {content}", style=msg_style)
                lines.append(content_text)

        # Sidebar
        sidebar = self._build_sidebar()

        # Render two-column layout
        chat_content = "\n".join(str(l) for l in lines)

        # Print messages
        chat_panel = Panel(
            "\n".join([l if isinstance(l, str) else l.markup if hasattr(l, 'markup') else str(l) for l in lines]),
            title=f"[dim]Messages[/dim]",
            border_style="bright_black",
            height=25,
        )

        layout = Table.grid(expand=True)
        layout.add_column(ratio=4)
        layout.add_column(ratio=1, min_width=22)
        layout.add_row(chat_panel, sidebar)
        self.console.print(layout)

    def _build_sidebar(self) -> Panel:
        """Build the sidebar with friends/online users."""
        lines = []

        # Friends
        if self.friends:
            lines.append(Text("Friends", style="bold cyan"))
            for f in self.friends[:8]:
                dot = "🟢" if f.get("is_online") else "⚫"
                name = f.get("username", "?")[:14]
                lines.append(Text(f"  {dot} {name}", style="white"))
            lines.append(Text(""))

        # Online
        lines.append(Text("Online", style="bold green"))
        shown = set(f.get("username") for f in self.friends)
        others = [u for u in self.online_users if u not in shown and u != self.username]
        for u in others[:6]:
            lines.append(Text(f"  🟢 {u[:14]}", style="dim"))

        if not lines:
            lines.append(Text("No one online", style="dim italic"))

        content = "\n".join(str(l) if isinstance(l, str) else l.plain for l in lines)
        rich_lines = []
        for l in lines:
            if hasattr(l, 'markup'):
                rich_lines.append(l.markup)
            else:
                rich_lines.append(str(l))

        return Panel(
            "\n".join(rich_lines),
            title="[dim]People[/dim]",
            border_style="bright_black",
            style="on black",
        )

    def _render_footer(self):
        """Render command hints footer."""
        hints = [
            "[dim]/help[/dim] commands",
            "[dim]/join[/dim] room",
            "[dim]/msg[/dim] DM",
            "[dim]/sendfile[/dim] files",
            "[dim]/users[/dim] online",
            "[dim]Ctrl+C[/dim] quit",
        ]
        self.console.print(Panel(
            " │ ".join(hints),
            border_style="bright_black",
            padding=(0, 1),
        ))

    def _get_dm_partner(self) -> str:
        """Extract DM partner name from room name."""
        if self.current_room.startswith("dm_"):
            parts = self.current_room[3:].split("_")
            for p in parts:
                if p != self.username:
                    return p
        return self.current_room

    def _print_error(self, msg: str):
        self.console.print(f"[bold red]✗ {msg}[/bold red]")

    def _print_info(self, msg: str):
        self.console.print(f"[dim]{msg}[/dim]")

    async def _refresh_friends(self):
        try:
            result = await self.api.get("/api/v1/friends/list")
            self.friends = result.get("friends", [])
        except APIError:
            pass

    async def _refresh_online_users(self):
        try:
            result = await self.api.get("/api/v1/users/online")
            self.online_users = [u["username"] for u in result.get("users", [])]
        except APIError:
            pass

    async def _periodic_refresh(self):
        """Periodically refresh friends and online users."""
        while self._running:
            await asyncio.sleep(30)
            await self._refresh_friends()
            await self._refresh_online_users()
