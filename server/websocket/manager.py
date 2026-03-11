"""
TermTalk WebSocket Manager
"""
import json
import asyncio
from datetime import datetime
from typing import Dict, Set, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from server.database.db import (
    AsyncSessionLocal, User, Message, Room, RoomMember,
    MessageType, Notification
)
from server.auth.auth import get_user_from_token

router = APIRouter()


class ConnectionManager:
    """Manages all WebSocket connections."""

    def __init__(self):
        # user_id -> WebSocket
        self.active_connections: Dict[int, WebSocket] = {}
        # room_name -> set of user_ids
        self.room_subscriptions: Dict[str, Set[int]] = {}
        # user_id -> set of room_names
        self.user_rooms: Dict[int, Set[str]] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        if user_id not in self.user_rooms:
            self.user_rooms[user_id] = set()

        # Mark user as online
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user:
                user.is_online = True
                user.last_seen = datetime.utcnow()
                await db.commit()

                # Notify friends that user came online
                await self.broadcast_presence(user.username, True, db)

    async def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

        # Remove from all rooms
        if user_id in self.user_rooms:
            for room in list(self.user_rooms[user_id]):
                if room in self.room_subscriptions:
                    self.room_subscriptions[room].discard(user_id)
            del self.user_rooms[user_id]

        # Mark user as offline
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user:
                user.is_online = False
                user.last_seen = datetime.utcnow()
                await db.commit()

                await self.broadcast_presence(user.username, False, db)

    def subscribe_room(self, user_id: int, room_name: str):
        if room_name not in self.room_subscriptions:
            self.room_subscriptions[room_name] = set()
        self.room_subscriptions[room_name].add(user_id)
        if user_id not in self.user_rooms:
            self.user_rooms[user_id] = set()
        self.user_rooms[user_id].add(room_name)

    def unsubscribe_room(self, user_id: int, room_name: str):
        if room_name in self.room_subscriptions:
            self.room_subscriptions[room_name].discard(user_id)
        if user_id in self.user_rooms:
            self.user_rooms[user_id].discard(room_name)

    async def send_personal(self, user_id: int, message: dict):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_text(json.dumps(message))
            except Exception:
                pass

    async def broadcast_room(self, room_name: str, message: dict, exclude_user_id: Optional[int] = None):
        if room_name in self.room_subscriptions:
            for user_id in list(self.room_subscriptions[room_name]):
                if user_id != exclude_user_id:
                    await self.send_personal(user_id, message)

    async def broadcast_presence(self, username: str, is_online: bool, db: AsyncSession):
        """Notify all friends about presence change."""
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if not user:
            return

        message = {
            "type": "presence",
            "username": username,
            "is_online": is_online,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Broadcast to all online users (simple approach)
        for uid in list(self.active_connections.keys()):
            if uid != user.id:
                await self.send_personal(uid, message)

    def is_online(self, user_id: int) -> bool:
        return user_id in self.active_connections

    def online_count(self) -> int:
        return len(self.active_connections)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    """Main WebSocket endpoint."""
    async with AsyncSessionLocal() as db:
        user = await get_user_from_token(token, db)
        if not user:
            await websocket.close(code=4001, reason="Unauthorized")
            return

        user_id = user.id
        username = user.username

    await manager.connect(user_id, websocket)

    # Auto-subscribe to user's rooms
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Room).join(RoomMember).where(RoomMember.user_id == user_id)
        )
        rooms = result.scalars().all()
        for room in rooms:
            manager.subscribe_room(user_id, room.name)

        # Deliver offline messages
        await deliver_offline_messages(user_id, db)

    # Send welcome
    await manager.send_personal(user_id, {
        "type": "connected",
        "message": f"Welcome back, {username}!",
        "timestamp": datetime.utcnow().isoformat(),
    })

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                await handle_message(user_id, username, msg)
            except json.JSONDecodeError:
                await manager.send_personal(user_id, {
                    "type": "error",
                    "message": "Invalid JSON",
                })
    except WebSocketDisconnect:
        await manager.disconnect(user_id)


async def handle_message(user_id: int, username: str, msg: dict):
    """Route incoming WebSocket messages."""
    msg_type = msg.get("type")

    if msg_type == "chat":
        await handle_chat(user_id, username, msg)
    elif msg_type == "join_room":
        await handle_join_room(user_id, msg)
    elif msg_type == "leave_room":
        await handle_leave_room(user_id, msg)
    elif msg_type == "typing":
        await handle_typing(user_id, username, msg)
    elif msg_type == "ping":
        await manager.send_personal(user_id, {"type": "pong"})
    else:
        await manager.send_personal(user_id, {
            "type": "error",
            "message": f"Unknown message type: {msg_type}",
        })


async def handle_chat(user_id: int, username: str, msg: dict):
    """Handle a chat message."""
    room_name = msg.get("room")
    content = msg.get("content", "").strip()

    if not room_name or not content:
        return

    async with AsyncSessionLocal() as db:
        # Verify user is member of room
        result = await db.execute(
            select(Room).join(RoomMember).where(
                and_(Room.name == room_name, RoomMember.user_id == user_id)
            )
        )
        room = result.scalar_one_or_none()
        if not room:
            await manager.send_personal(user_id, {
                "type": "error",
                "message": f"You are not a member of room '{room_name}'",
            })
            return

        # Save message
        message = Message(
            room_id=room.id,
            sender_id=user_id,
            content=content,
            message_type=MessageType.TEXT,
            is_encrypted=msg.get("encrypted", False),
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)

        # Get room members for offline message storage
        members_result = await db.execute(
            select(RoomMember).where(RoomMember.room_id == room.id)
        )
        members = members_result.scalars().all()

        # Create notifications for offline members
        for member in members:
            if member.user_id != user_id and not manager.is_online(member.user_id):
                notif = Notification(
                    user_id=member.user_id,
                    type="message",
                    content=json.dumps({
                        "room": room_name,
                        "sender": username,
                        "preview": content[:100],
                        "message_id": message.id,
                    }),
                )
                db.add(notif)
        await db.commit()

    # Broadcast to room
    broadcast_msg = {
        "type": "message",
        "id": message.id,
        "room": room_name,
        "sender": username,
        "content": content,
        "message_type": "text",
        "encrypted": msg.get("encrypted", False),
        "timestamp": message.created_at.isoformat(),
    }

    await manager.broadcast_room(room_name, broadcast_msg)


async def handle_join_room(user_id: int, msg: dict):
    """Subscribe user to room updates."""
    room_name = msg.get("room")
    if room_name:
        manager.subscribe_room(user_id, room_name)
        await manager.send_personal(user_id, {
            "type": "joined_room",
            "room": room_name,
        })


async def handle_leave_room(user_id: int, msg: dict):
    """Unsubscribe user from room updates."""
    room_name = msg.get("room")
    if room_name:
        manager.unsubscribe_room(user_id, room_name)


async def handle_typing(user_id: int, username: str, msg: dict):
    """Broadcast typing indicator."""
    room_name = msg.get("room")
    if room_name:
        await manager.broadcast_room(room_name, {
            "type": "typing",
            "room": room_name,
            "username": username,
            "is_typing": msg.get("is_typing", True),
        }, exclude_user_id=user_id)


async def deliver_offline_messages(user_id: int, db: AsyncSession):
    """Deliver queued notifications to reconnected user."""
    result = await db.execute(
        select(Notification).where(
            and_(Notification.user_id == user_id, Notification.is_read == False)
        )
    )
    notifications = result.scalars().all()

    for notif in notifications:
        await manager.send_personal(user_id, {
            "type": "notification",
            "notification_type": notif.type,
            "content": json.loads(notif.content),
            "timestamp": notif.created_at.isoformat(),
        })
        notif.is_read = True

    if notifications:
        await db.commit()
