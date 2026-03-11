"""
TermTalk File Transfer API
"""
import os
import uuid
import mimetypes
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Header
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from server.database.db import get_db, User, FileUpload, Message, Room, RoomMember, MessageType
from server.auth.auth import get_current_user
from server.config import settings
from server.websocket.manager import manager

import json
from datetime import datetime

router = APIRouter()

CHUNK_SIZE = 1024 * 1024  # 1MB chunks


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    room: str = None,
    recipient: str = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a file and optionally send to room/user."""
    # Validate file
    ext = Path(file.filename).suffix.lower().lstrip(".")
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type '.{ext}' not allowed")

    # Read and validate size
    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 100MB)")

    # Save file
    safe_name = f"{uuid.uuid4().hex}.{ext}"
    file_path = Path(settings.UPLOAD_DIR) / safe_name

    with open(file_path, "wb") as f:
        f.write(content)

    mime_type = mimetypes.guess_type(file.filename)[0] or "application/octet-stream"

    db_file = FileUpload(
        filename=safe_name,
        original_filename=file.filename,
        file_size=len(content),
        mime_type=mime_type,
        storage_path=str(file_path),
        uploader_id=current_user.id,
        upload_complete=True,
    )
    db.add(db_file)
    await db.flush()

    # Send to room if specified
    target_room_name = None
    if room:
        result = await db.execute(
            select(Room).join(RoomMember).where(
                and_(Room.name == room.lower(), RoomMember.user_id == current_user.id)
            )
        )
        target_room = result.scalar_one_or_none()
        if target_room:
            target_room_name = target_room.name
            message = Message(
                room_id=target_room.id,
                sender_id=current_user.id,
                content=f"📎 {file.filename} ({_format_size(len(content))})",
                message_type=MessageType.FILE,
                file_id=db_file.id,
            )
            db.add(message)

    # Send DM if recipient specified
    elif recipient:
        result = await db.execute(select(User).where(User.username == recipient.lower()))
        other_user = result.scalar_one_or_none()
        if other_user:
            dm_name = _get_dm_room_name(current_user.username, other_user.username)
            result = await db.execute(select(Room).where(Room.name == dm_name))
            dm_room = result.scalar_one_or_none()

            if not dm_room:
                dm_room = Room(name=dm_name, is_direct=True)
                db.add(dm_room)
                await db.flush()
                db.add(RoomMember(room_id=dm_room.id, user_id=current_user.id))
                db.add(RoomMember(room_id=dm_room.id, user_id=other_user.id))

            target_room_name = dm_name
            message = Message(
                room_id=dm_room.id,
                sender_id=current_user.id,
                content=f"📎 {file.filename} ({_format_size(len(content))})",
                message_type=MessageType.FILE,
                file_id=db_file.id,
            )
            db.add(message)

    await db.commit()
    await db.refresh(db_file)

    # Broadcast file message
    if target_room_name:
        await manager.broadcast_room(target_room_name, {
            "type": "message",
            "room": target_room_name,
            "sender": current_user.username,
            "content": f"📎 {file.filename} ({_format_size(len(content))})",
            "message_type": "file",
            "file": {
                "id": db_file.id,
                "filename": file.filename,
                "size": len(content),
                "mime_type": mime_type,
            },
            "timestamp": datetime.utcnow().isoformat(),
        })

    return {
        "file_id": db_file.id,
        "filename": file.filename,
        "size": len(content),
        "mime_type": mime_type,
        "download_url": f"/api/v1/files/{db_file.id}/download",
    }


@router.get("/{file_id}/download")
async def download_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download a file with streaming."""
    result = await db.execute(select(FileUpload).where(FileUpload.id == file_id))
    db_file = result.scalar_one_or_none()

    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    if not os.path.exists(db_file.storage_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    def file_iterator():
        with open(db_file.storage_path, "rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                yield chunk

    return StreamingResponse(
        file_iterator(),
        media_type=db_file.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{db_file.original_filename}"',
            "Content-Length": str(db_file.file_size),
        },
    )


def _format_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _get_dm_room_name(user1: str, user2: str) -> str:
    return "dm_" + "_".join(sorted([user1, user2]))
