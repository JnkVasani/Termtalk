"""
TermTalk Friends API
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from pydantic import BaseModel

from server.database.db import get_db, User, Friendship, FriendStatus, Room, RoomMember
from server.auth.auth import get_current_user
from server.websocket.manager import manager

router = APIRouter()


@router.post("/add/{username}")
async def send_friend_request(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a friend request."""
    if username.lower() == current_user.username:
        raise HTTPException(status_code=400, detail="Cannot add yourself")

    result = await db.execute(select(User).where(User.username == username.lower()))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Check existing friendship
    result = await db.execute(
        select(Friendship).where(
            or_(
                and_(Friendship.requester_id == current_user.id, Friendship.addressee_id == target.id),
                and_(Friendship.requester_id == target.id, Friendship.addressee_id == current_user.id),
            )
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        if existing.status == FriendStatus.ACCEPTED:
            raise HTTPException(status_code=400, detail="Already friends")
        elif existing.status == FriendStatus.PENDING:
            raise HTTPException(status_code=400, detail="Friend request already pending")
        elif existing.status == FriendStatus.BLOCKED:
            raise HTTPException(status_code=400, detail="Unable to send request")

    friendship = Friendship(
        requester_id=current_user.id,
        addressee_id=target.id,
        status=FriendStatus.PENDING,
    )
    db.add(friendship)
    await db.commit()

    # Notify target if online
    await manager.send_personal(target.id, {
        "type": "friend_request",
        "from": current_user.username,
        "display_name": current_user.display_name,
        "timestamp": datetime.utcnow().isoformat(),
    })

    return {"message": f"Friend request sent to {username}"}


@router.post("/accept/{username}")
async def accept_friend_request(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Accept a friend request."""
    result = await db.execute(select(User).where(User.username == username.lower()))
    requester = result.scalar_one_or_none()
    if not requester:
        raise HTTPException(status_code=404, detail="User not found")

    result = await db.execute(
        select(Friendship).where(
            and_(
                Friendship.requester_id == requester.id,
                Friendship.addressee_id == current_user.id,
                Friendship.status == FriendStatus.PENDING,
            )
        )
    )
    friendship = result.scalar_one_or_none()
    if not friendship:
        raise HTTPException(status_code=404, detail="No pending friend request from this user")

    friendship.status = FriendStatus.ACCEPTED
    friendship.updated_at = datetime.utcnow()

    # Create DM room
    dm_name = "dm_" + "_".join(sorted([current_user.username, requester.username]))
    result = await db.execute(select(Room).where(Room.name == dm_name))
    if not result.scalar_one_or_none():
        dm_room = Room(name=dm_name, is_direct=True)
        db.add(dm_room)
        await db.flush()
        db.add(RoomMember(room_id=dm_room.id, user_id=current_user.id))
        db.add(RoomMember(room_id=dm_room.id, user_id=requester.id))

    await db.commit()

    # Notify requester
    await manager.send_personal(requester.id, {
        "type": "friend_accepted",
        "by": current_user.username,
        "timestamp": datetime.utcnow().isoformat(),
    })

    return {"message": f"Now friends with {username}"}


@router.post("/reject/{username}")
async def reject_friend_request(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reject a friend request."""
    result = await db.execute(select(User).where(User.username == username.lower()))
    requester = result.scalar_one_or_none()
    if not requester:
        raise HTTPException(status_code=404, detail="User not found")

    result = await db.execute(
        select(Friendship).where(
            and_(
                Friendship.requester_id == requester.id,
                Friendship.addressee_id == current_user.id,
                Friendship.status == FriendStatus.PENDING,
            )
        )
    )
    friendship = result.scalar_one_or_none()
    if not friendship:
        raise HTTPException(status_code=404, detail="No pending request")

    friendship.status = FriendStatus.REJECTED
    await db.commit()
    return {"message": f"Request from {username} rejected"}


@router.get("/list")
async def list_friends(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get friends list."""
    result = await db.execute(
        select(Friendship).where(
            and_(
                or_(
                    Friendship.requester_id == current_user.id,
                    Friendship.addressee_id == current_user.id,
                ),
                Friendship.status == FriendStatus.ACCEPTED,
            )
        )
    )
    friendships = result.scalars().all()

    friends = []
    for f in friendships:
        friend_id = f.addressee_id if f.requester_id == current_user.id else f.requester_id
        user_result = await db.execute(select(User).where(User.id == friend_id))
        friend = user_result.scalar_one_or_none()
        if friend:
            friends.append({
                "username": friend.username,
                "display_name": friend.display_name,
                "is_online": manager.is_online(friend.id),
                "last_seen": friend.last_seen.isoformat() if friend.last_seen else None,
            })

    return {"friends": friends}


@router.get("/requests")
async def pending_requests(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get pending friend requests."""
    result = await db.execute(
        select(Friendship).where(
            and_(
                Friendship.addressee_id == current_user.id,
                Friendship.status == FriendStatus.PENDING,
            )
        )
    )
    requests = result.scalars().all()

    pending = []
    for req in requests:
        user_result = await db.execute(select(User).where(User.id == req.requester_id))
        requester = user_result.scalar_one_or_none()
        if requester:
            pending.append({
                "username": requester.username,
                "display_name": requester.display_name,
                "sent_at": req.created_at.isoformat(),
            })

    return {"requests": pending}
