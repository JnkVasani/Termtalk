"""
TermTalk API Routes
"""
from fastapi import APIRouter
from server.api import users, rooms, messages, files, friends

router = APIRouter()

router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(rooms.router, prefix="/rooms", tags=["rooms"])
router.include_router(messages.router, prefix="/messages", tags=["messages"])
router.include_router(files.router, prefix="/files", tags=["files"])
router.include_router(friends.router, prefix="/friends", tags=["friends"])
