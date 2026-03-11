"""
TermTalk User API
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, validator

from server.database.db import get_db, User
from server.auth.auth import hash_password, verify_password, create_access_token, get_current_user
from server.websocket.manager import manager

router = APIRouter()


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    display_name: Optional[str] = None

    @validator("username")
    def username_alphanumeric(cls, v):
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username must be alphanumeric (underscores/hyphens allowed)")
        if len(v) < 3 or len(v) > 50:
            raise ValueError("Username must be 3-50 characters")
        return v.lower()

    @validator("password")
    def password_min_length(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None
    public_key: Optional[str] = None


@router.post("/register", status_code=201)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user."""
    # Check username availability
    result = await db.execute(select(User).where(User.username == request.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")

    # Check email availability
    if request.email:
        result = await db.execute(select(User).where(User.email == request.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        username=request.username,
        email=request.email,
        hashed_password=hash_password(request.password),
        display_name=request.display_name or request.username,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token({"sub": user.username})

    return {
        "message": "Registration successful",
        "username": user.username,
        "token": token,
    }


@router.post("/login")
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login and get access token."""
    result = await db.execute(select(User).where(User.username == request.username.lower()))
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    token = create_access_token({"sub": user.username})

    return {
        "message": "Login successful",
        "username": user.username,
        "display_name": user.display_name,
        "token": token,
    }


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "display_name": current_user.display_name,
        "email": current_user.email,
        "bio": current_user.bio,
        "is_online": current_user.is_online,
        "created_at": current_user.created_at.isoformat(),
        "public_key": current_user.public_key,
    }


@router.patch("/me")
async def update_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user profile."""
    if request.display_name is not None:
        current_user.display_name = request.display_name
    if request.bio is not None:
        current_user.bio = request.bio
    if request.public_key is not None:
        current_user.public_key = request.public_key

    await db.commit()
    return {"message": "Profile updated"}


@router.get("/online")
async def get_online_users(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get list of online users."""
    result = await db.execute(select(User).where(User.is_online == True))
    users = result.scalars().all()
    return {
        "users": [
            {
                "username": u.username,
                "display_name": u.display_name,
                "last_seen": u.last_seen.isoformat() if u.last_seen else None,
            }
            for u in users
        ],
        "count": len(users),
    }


@router.get("/{username}")
async def get_user(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a user's public profile."""
    result = await db.execute(select(User).where(User.username == username.lower()))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "username": user.username,
        "display_name": user.display_name,
        "bio": user.bio,
        "is_online": manager.is_online(user.id),
        "last_seen": user.last_seen.isoformat() if user.last_seen else None,
    }
