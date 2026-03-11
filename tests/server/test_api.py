"""
TermTalk Server Tests
"""
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from server.main import app
from server.database.db import Base, get_db
from server.config import settings

# Use in-memory SQLite for tests
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def auth_client(client):
    """Client with registered & logged in user."""
    await client.post("/api/v1/users/register", json={
        "username": "testuser",
        "password": "testpass123",
    })
    resp = await client.post("/api/v1/users/login", json={
        "username": "testuser",
        "password": "testpass123",
    })
    token = resp.json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


# ─── AUTH TESTS ───────────────────────────────────────────────────

class TestAuth:
    async def test_register_success(self, client):
        resp = await client.post("/api/v1/users/register", json={
            "username": "newuser",
            "password": "password123",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "newuser"
        assert "token" in data

    async def test_register_duplicate(self, client):
        await client.post("/api/v1/users/register", json={
            "username": "dupuser",
            "password": "password123",
        })
        resp = await client.post("/api/v1/users/register", json={
            "username": "dupuser",
            "password": "password123",
        })
        assert resp.status_code == 400
        assert "already taken" in resp.json()["detail"]

    async def test_register_short_password(self, client):
        resp = await client.post("/api/v1/users/register", json={
            "username": "validuser",
            "password": "short",
        })
        assert resp.status_code == 422

    async def test_login_success(self, client):
        await client.post("/api/v1/users/register", json={
            "username": "logintest",
            "password": "testpass123",
        })
        resp = await client.post("/api/v1/users/login", json={
            "username": "logintest",
            "password": "testpass123",
        })
        assert resp.status_code == 200
        assert "token" in resp.json()

    async def test_login_wrong_password(self, client):
        await client.post("/api/v1/users/register", json={
            "username": "logintest2",
            "password": "testpass123",
        })
        resp = await client.post("/api/v1/users/login", json={
            "username": "logintest2",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    async def test_get_me_authenticated(self, auth_client):
        resp = await auth_client.get("/api/v1/users/me")
        assert resp.status_code == 200
        assert resp.json()["username"] == "testuser"

    async def test_get_me_unauthenticated(self, client):
        resp = await client.get("/api/v1/users/me")
        assert resp.status_code == 403


# ─── ROOM TESTS ───────────────────────────────────────────────────

class TestRooms:
    async def test_create_room(self, auth_client):
        resp = await auth_client.post("/api/v1/rooms/", json={
            "name": "testroom",
            "description": "Test room",
        })
        assert resp.status_code == 201
        assert resp.json()["name"] == "testroom"

    async def test_create_duplicate_room(self, auth_client):
        await auth_client.post("/api/v1/rooms/", json={"name": "duperoom"})
        resp = await auth_client.post("/api/v1/rooms/", json={"name": "duperoom"})
        assert resp.status_code == 400

    async def test_join_room(self, auth_client):
        await auth_client.post("/api/v1/rooms/", json={"name": "jointest"})
        # Register second user and join
        await auth_client.post("/api/v1/users/register", json={
            "username": "user2",
            "password": "testpass123",
        })
        resp2 = await auth_client.post("/api/v1/users/login", json={
            "username": "user2",
            "password": "testpass123",
        })
        token2 = resp2.json()["token"]

        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c2:
            c2.headers.update({"Authorization": f"Bearer {token2}"})
            resp = await c2.post("/api/v1/rooms/jointest/join")
            assert resp.status_code == 200

    async def test_list_rooms(self, auth_client):
        await auth_client.post("/api/v1/rooms/", json={"name": "publicroom"})
        resp = await auth_client.get("/api/v1/rooms/")
        assert resp.status_code == 200
        rooms = resp.json()["rooms"]
        assert any(r["name"] == "publicroom" for r in rooms)


# ─── FRIENDS TESTS ────────────────────────────────────────────────

class TestFriends:
    async def setup_second_user(self, client):
        await client.post("/api/v1/users/register", json={
            "username": "friend1",
            "password": "testpass123",
        })

    async def test_send_friend_request(self, auth_client):
        await auth_client.post("/api/v1/users/register", json={
            "username": "target1",
            "password": "testpass123",
        })
        resp = await auth_client.post("/api/v1/friends/add/target1")
        assert resp.status_code == 200

    async def test_cannot_add_self(self, auth_client):
        resp = await auth_client.post("/api/v1/friends/add/testuser")
        assert resp.status_code == 400

    async def test_list_empty_friends(self, auth_client):
        resp = await auth_client.get("/api/v1/friends/list")
        assert resp.status_code == 200
        assert resp.json()["friends"] == []


# ─── MESSAGE TESTS ────────────────────────────────────────────────

class TestMessages:
    async def test_history_empty_room(self, auth_client):
        await auth_client.post("/api/v1/rooms/", json={"name": "histroom"})
        resp = await auth_client.get("/api/v1/messages/history/histroom")
        assert resp.status_code == 200
        assert resp.json()["messages"] == []

    async def test_history_unauthorized_room(self, auth_client):
        # Create room with another user
        resp = await auth_client.get("/api/v1/messages/history/nonexistent")
        assert resp.status_code == 403


# ─── HEALTH TESTS ─────────────────────────────────────────────────

class TestHealth:
    async def test_health_check(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert resp.json()["service"] == "TermTalk Server"
