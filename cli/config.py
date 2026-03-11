"""
TermTalk CLI Configuration
"""
import json
import os
from pathlib import Path
from typing import Optional


class CLIConfig:
    """Manages CLI configuration and credentials."""

    CONFIG_DIR = Path.home() / ".termtalk"
    CONFIG_FILE = CONFIG_DIR / "config.json"
    TOKEN_FILE = CONFIG_DIR / "token"

    def __init__(self):
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        if self.CONFIG_FILE.exists():
            try:
                return json.loads(self.CONFIG_FILE.read_text())
            except Exception:
                return {}
        return {}

    def _save(self):
        self.CONFIG_FILE.write_text(json.dumps(self._data, indent=2))

    @property
    def server_url(self) -> str:
        return self._data.get("server_url", "http://localhost:8000")

    @server_url.setter
    def server_url(self, value: str):
        self._data["server_url"] = value.rstrip("/")
        self._save()

    @property
    def ws_url(self) -> str:
        url = self.server_url
        return url.replace("http://", "ws://").replace("https://", "wss://")

    @property
    def username(self) -> Optional[str]:
        return self._data.get("username")

    @username.setter
    def username(self, value: str):
        self._data["username"] = value
        self._save()

    @property
    def token(self) -> Optional[str]:
        if self.TOKEN_FILE.exists():
            return self.TOKEN_FILE.read_text().strip()
        return None

    @token.setter
    def token(self, value: Optional[str]):
        if value:
            self.TOKEN_FILE.write_text(value)
            self.TOKEN_FILE.chmod(0o600)
        else:
            if self.TOKEN_FILE.exists():
                self.TOKEN_FILE.unlink()

    def is_authenticated(self) -> bool:
        return self.token is not None and self.username is not None

    def clear_auth(self):
        self.token = None
        self._data.pop("username", None)
        self._save()

    @property
    def download_dir(self) -> Path:
        path = Path(self._data.get("download_dir", str(Path.home() / "Downloads" / "TermTalk")))
        path.mkdir(parents=True, exist_ok=True)
        return path

    @download_dir.setter
    def download_dir(self, value: str):
        self._data["download_dir"] = value
        self._save()


# Global config instance
config = CLIConfig()
