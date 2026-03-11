"""
TermTalk CLI Tests
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile
import os


class TestCLIConfig:
    def test_config_defaults(self):
        from cli.config import CLIConfig
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(CLIConfig, 'CONFIG_DIR', Path(tmpdir)):
                with patch.object(CLIConfig, 'CONFIG_FILE', Path(tmpdir) / "config.json"):
                    with patch.object(CLIConfig, 'TOKEN_FILE', Path(tmpdir) / "token"):
                        cfg = CLIConfig()
                        assert "localhost" in cfg.server_url or "8000" in cfg.server_url

    def test_config_server_url(self):
        from cli.config import CLIConfig
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(CLIConfig, 'CONFIG_DIR', Path(tmpdir)):
                with patch.object(CLIConfig, 'CONFIG_FILE', Path(tmpdir) / "config.json"):
                    with patch.object(CLIConfig, 'TOKEN_FILE', Path(tmpdir) / "token"):
                        cfg = CLIConfig()
                        cfg.server_url = "https://myserver.com"
                        assert cfg.server_url == "https://myserver.com"

    def test_ws_url_conversion(self):
        from cli.config import CLIConfig
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(CLIConfig, 'CONFIG_DIR', Path(tmpdir)):
                with patch.object(CLIConfig, 'CONFIG_FILE', Path(tmpdir) / "config.json"):
                    with patch.object(CLIConfig, 'TOKEN_FILE', Path(tmpdir) / "token"):
                        cfg = CLIConfig()
                        cfg.server_url = "https://myserver.com"
                        assert cfg.ws_url == "wss://myserver.com"
                        cfg.server_url = "http://localhost:8000"
                        assert cfg.ws_url == "ws://localhost:8000"

    def test_token_storage(self):
        from cli.config import CLIConfig
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(CLIConfig, 'CONFIG_DIR', Path(tmpdir)):
                with patch.object(CLIConfig, 'CONFIG_FILE', Path(tmpdir) / "config.json"):
                    with patch.object(CLIConfig, 'TOKEN_FILE', Path(tmpdir) / "token"):
                        cfg = CLIConfig()
                        assert cfg.token is None
                        cfg.token = "test-token-abc"
                        assert cfg.token == "test-token-abc"
                        cfg.token = None
                        assert cfg.token is None

    def test_is_authenticated(self):
        from cli.config import CLIConfig
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(CLIConfig, 'CONFIG_DIR', Path(tmpdir)):
                with patch.object(CLIConfig, 'CONFIG_FILE', Path(tmpdir) / "config.json"):
                    with patch.object(CLIConfig, 'TOKEN_FILE', Path(tmpdir) / "token"):
                        cfg = CLIConfig()
                        assert not cfg.is_authenticated()
                        cfg.token = "tok"
                        cfg.username = "user"
                        assert cfg.is_authenticated()
                        cfg.clear_auth()
                        assert not cfg.is_authenticated()


class TestTheme:
    def test_format_timestamp_today(self):
        from cli.ui.theme import format_timestamp
        from datetime import datetime, timezone
        ts = datetime.utcnow().isoformat()
        result = format_timestamp(ts)
        # Should be HH:MM format for today
        assert ":" in result
        assert len(result) <= 5  # HH:MM

    def test_format_timestamp_invalid(self):
        from cli.ui.theme import format_timestamp
        result = format_timestamp("invalid")
        assert result == "invalid"[:16] or result == ""

    def test_get_user_color_consistent(self):
        from cli.ui.theme import get_user_color
        color1 = get_user_color("alice")
        color2 = get_user_color("alice")
        assert color1 == color2

    def test_get_user_color_different_users(self):
        from cli.ui.theme import get_user_color, USER_COLORS
        # Should return valid colors
        color = get_user_color("bob")
        assert color in USER_COLORS

    def test_render_markdown_bold(self):
        from cli.ui.theme import render_markdown_inline
        result = render_markdown_inline("Hello **world**!")
        assert "[bold]world[/bold]" in result

    def test_render_markdown_code(self):
        from cli.ui.theme import render_markdown_inline
        result = render_markdown_inline("Run `pip install termtalk`")
        assert "pip install termtalk" in result
        assert "bright_yellow" in result or "black" in result

    def test_render_markdown_url(self):
        from cli.ui.theme import render_markdown_inline
        result = render_markdown_inline("Visit https://example.com for more")
        assert "https://example.com" in result
        assert "cyan" in result


class TestAPIClient:
    async def test_api_error_raised(self):
        from cli.network.client import APIClient, APIError
        import httpx

        with patch('cli.network.client.config') as mock_config:
            mock_config.server_url = "http://localhost:9999"
            mock_config.token = "fake-token"
            api = APIClient()

            # Should raise on connection error
            with pytest.raises(Exception):
                await api.get("/nonexistent")

            await api.close()

    def test_api_error_message(self):
        from cli.network.client import APIError
        err = APIError("test error", 404)
        assert err.message == "test error"
        assert err.status_code == 404
        assert str(err) == "test error"
