"""
TermTalk API Client
"""
import asyncio
import json
import httpx
import websockets
from typing import Optional, Callable, AsyncIterator
from pathlib import Path

from cli.config import config


class APIError(Exception):
    def __init__(self, message: str, status_code: int = 0):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class APIClient:
    """HTTP client for TermTalk API."""

    def __init__(self):
        self.base_url = config.server_url
        self._client: Optional[httpx.AsyncClient] = None

    def _get_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if config.token:
            headers["Authorization"] = f"Bearer {config.token}"
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._get_headers(),
                timeout=30.0,
            )
        return self._client

    async def get(self, path: str) -> dict:
        client = await self._get_client()
        resp = await client.get(path, headers=self._get_headers())
        return self._handle(resp)

    async def post(self, path: str, data: dict = None) -> dict:
        client = await self._get_client()
        resp = await client.post(path, json=data or {}, headers=self._get_headers())
        return self._handle(resp)

    async def patch(self, path: str, data: dict = None) -> dict:
        client = await self._get_client()
        resp = await client.patch(path, json=data or {}, headers=self._get_headers())
        return self._handle(resp)

    async def upload_file(
        self,
        file_path: Path,
        room: Optional[str] = None,
        recipient: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
    ) -> dict:
        """Upload a file with progress tracking."""
        client = await self._get_client()
        headers = {"Authorization": f"Bearer {config.token}"}

        params = {}
        if room:
            params["room"] = room
        if recipient:
            params["recipient"] = recipient

        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "application/octet-stream")}
            resp = await client.post(
                "/api/v1/files/upload",
                files=files,
                params=params,
                headers=headers,
            )

        return self._handle(resp)

    async def download_file(
        self,
        file_id: int,
        save_path: Path,
        progress_callback: Optional[Callable] = None,
    ) -> Path:
        """Download a file with streaming."""
        client = await self._get_client()
        headers = {"Authorization": f"Bearer {config.token}"}

        async with client.stream("GET", f"/api/v1/files/{file_id}/download", headers=headers) as resp:
            if resp.status_code != 200:
                raise APIError(f"Download failed: {resp.status_code}")

            total = int(resp.headers.get("content-length", 0))
            downloaded = 0

            with open(save_path, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total:
                        progress_callback(downloaded, total)

        return save_path

    def _handle(self, resp: httpx.Response) -> dict:
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise APIError(detail, resp.status_code)
        try:
            return resp.json()
        except Exception:
            return {"message": resp.text}

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class WSClient:
    """WebSocket client for real-time messaging."""

    def __init__(self, on_message: Callable):
        self.on_message = on_message
        self._ws = None
        self._running = False

    async def connect(self):
        """Connect to WebSocket server."""
        token = config.token
        if not token:
            raise APIError("Not authenticated")

        ws_url = f"{config.ws_url}/ws?token={token}"
        self._running = True
        self._ws = await websockets.connect(
            ws_url,
            ping_interval=30,
            ping_timeout=10,
        )

    async def send(self, data: dict):
        """Send a message."""
        if self._ws:
            await self._ws.send(json.dumps(data))

    async def listen(self):
        """Listen for messages."""
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                    await self.on_message(msg)
                except json.JSONDecodeError:
                    pass
        except websockets.ConnectionClosed:
            self._running = False

    async def disconnect(self):
        """Disconnect from server."""
        self._running = False
        if self._ws:
            await self._ws.close()

    async def join_room(self, room_name: str):
        await self.send({"type": "join_room", "room": room_name})

    async def leave_room(self, room_name: str):
        await self.send({"type": "leave_room", "room": room_name})

    async def send_message(self, room: str, content: str, encrypted: bool = False):
        await self.send({
            "type": "chat",
            "room": room,
            "content": content,
            "encrypted": encrypted,
        })

    async def send_typing(self, room: str, is_typing: bool = True):
        await self.send({
            "type": "typing",
            "room": room,
            "is_typing": is_typing,
        })
