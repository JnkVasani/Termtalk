"""
TermTalk Rooms API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel
from typing import Optional

from server.database.db import get_db, User, Room, RoomMember
from server.auth.auth import get_current_user
from server.websocket.manager import manager

router = APIRouter()


class CreateRoomRequest(BaseModel):
    name: str
    description: Optional[str] = None
    is_private: bool = False


@router.post("/", status_code=201)
async def create_room(
    request: CreateRoomRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new room."""
    name = request.name.lower().replace(" ", "-")

    result = await db.execute(select(Room).where(Room.name == name))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Room '{name}' already exists")

    room = Room(
        name=name,
        description=request.description,
        is_private=request.is_private,
        owner_id=current_user.id,
    )
    db.add(room)
    await db.flush()

    # Add creator as admin member
    member = RoomMember(room_id=room.id, user_id=current_user.id, is_admin=True)
    db.add(member)
    await db.commit()

    manager.subscribe_room(current_user.id, name)

    return {
        "message": f"Room '{name}' created",
        "name": name,
        "description": room.description,
    }


@router.post("/{room_name}/join")
async def join_room(
    room_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Join a room."""
    result = await db.execute(select(Room).where(Room.name == room_name.lower()))
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail=f"Room '{room_name}' not found")

    if room.is_private:
        raise HTTPException(status_code=403, detail="This is a private room")

    # Check if already a member
    result = await db.execute(
        select(RoomMember).where(
            and_(RoomMember.room_id == room.id, RoomMember.user_id == current_user.id)
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already a member of this room")

    member = RoomMember(room_id=room.id, user_id=current_user.id)
    db.add(member)
    await db.commit()

    manager.subscribe_room(current_user.id, room.name)

    # Notify room
    await manager.broadcast_room(room.name, {
        "type": "system",
        "room": room.name,
        "content": f"{current_user.username} joined the room",
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
    })

    return {"message": f"Joined room '{room_name}'"}


@router.post("/{room_name}/leave")
async def leave_room(
    room_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Leave a room."""
    result = await db.execute(
        select(RoomMember).join(Room).where(
            and_(Room.name == room_name.lower(), RoomMember.user_id == current_user.id)
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=400, detail="Not a member of this room")

    await db.delete(member)
    await db.commit()

    manager.unsubscribe_room(current_user.id, room_name.lower())

    await manager.broadcast_room(room_name.lower(), {
        "type": "system",
        "room": room_name.lower(),
        "content": f"{current_user.username} left the room",
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
    })

    return {"message": f"Left room '{room_name}'"}


@router.get("/")
async def list_rooms(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all public rooms."""
    result = await db.execute(select(Room).where(Room.is_private == False, Room.is_direct == False))
    rooms = result.scalars().all()
    return {
        "rooms": [
            {
                "name": r.name,
                "description": r.description,
                "online_members": len([
                    uid for uid in (manager.room_subscriptions.get(r.name) or set())
                ]),
            }
            for r in rooms
        ]
    }


@router.get("/my")
async def my_rooms(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get rooms current user is a member of."""
    result = await db.execute(
        select(Room).join(RoomMember).where(
            and_(RoomMember.user_id == current_user.id, Room.is_direct == False)
        )
    )
    rooms = result.scalars().all()
    return {
        "rooms": [{"name": r.name, "description": r.description} for r in rooms]
    }


@router.get("/{room_name}/members")
async def room_members(
    room_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get members of a room."""
    result = await db.execute(
        select(User).join(RoomMember).join(Room).where(Room.name == room_name.lower())
    )
    users = result.scalars().all()
    return {
        "members": [
            {
                "username": u.username,
                "display_name": u.display_name,
                "is_online": manager.is_online(u.id),
            }
            for u in users
        ]
    }
