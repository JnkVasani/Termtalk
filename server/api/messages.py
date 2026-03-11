"""
TermTalk Messages API
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from server.database.db import get_db, User, Message, Room, RoomMember, FileUpload
from server.auth.auth import get_current_user

router = APIRouter()


@router.get("/history/{room_name}")
async def get_history(
    room_name: str,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get message history for a room."""
    # Verify room membership
    result = await db.execute(
        select(Room).join(RoomMember).where(
            and_(Room.name == room_name.lower(), RoomMember.user_id == current_user.id)
        )
    )
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=403, detail="Not a member of this room")

    result = await db.execute(
        select(Message, User.username, User.display_name)
        .join(User, Message.sender_id == User.id)
        .where(and_(Message.room_id == room.id, Message.is_deleted == False))
        .order_by(desc(Message.created_at))
        .limit(limit)
        .offset(offset)
    )
    rows = result.all()

    messages = []
    for msg, username, display_name in reversed(rows):
        m = {
            "id": msg.id,
            "sender": username,
            "display_name": display_name,
            "content": msg.content,
            "message_type": msg.message_type.value,
            "timestamp": msg.created_at.isoformat(),
            "encrypted": msg.is_encrypted,
        }
        if msg.file_id:
            file_result = await db.execute(select(FileUpload).where(FileUpload.id == msg.file_id))
            file = file_result.scalar_one_or_none()
            if file:
                m["file"] = {
                    "id": file.id,
                    "filename": file.original_filename,
                    "size": file.file_size,
                    "mime_type": file.mime_type,
                }
        messages.append(m)

    return {"room": room_name, "messages": messages, "total": len(messages)}


@router.get("/dm/{username}")
async def get_dm_history(
    username: str,
    limit: int = Query(50, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get direct message history with a user."""
    # Find or verify DM room
    result = await db.execute(select(User).where(User.username == username.lower()))
    other_user = result.scalar_one_or_none()
    if not other_user:
        raise HTTPException(status_code=404, detail="User not found")

    # DM rooms are named: dm_user1_user2 (alphabetical)
    dm_name = _get_dm_room_name(current_user.username, other_user.username)

    result = await db.execute(select(Room).where(Room.name == dm_name))
    room = result.scalar_one_or_none()

    if not room:
        return {"room": dm_name, "messages": []}

    result = await db.execute(
        select(Message, User.username)
        .join(User, Message.sender_id == User.id)
        .where(and_(Message.room_id == room.id, Message.is_deleted == False))
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    rows = result.all()

    return {
        "room": dm_name,
        "messages": [
            {
                "id": msg.id,
                "sender": uname,
                "content": msg.content,
                "message_type": msg.message_type.value,
                "timestamp": msg.created_at.isoformat(),
            }
            for msg, uname in reversed(rows)
        ],
    }


def _get_dm_room_name(user1: str, user2: str) -> str:
    """Get deterministic DM room name."""
    return "dm_" + "_".join(sorted([user1, user2]))
