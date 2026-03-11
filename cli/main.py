"""
TermTalk CLI - Main Entry Point
"""
import click
import asyncio
import sys
from pathlib import Path

from cli.config import CLIConfig
from cli.network.client import APIClient


@click.group()
@click.version_option(version="1.0.0", prog_name="TermTalk")
def cli():
    """
    TermTalk - Terminal Communication Platform

    Chat with friends globally from your terminal.
    """
    pass


@cli.command()
def register():
    """Create a new TermTalk account."""
    from cli.commands.auth import register_command
    asyncio.run(register_command())


@cli.command()
def login():
    """Login to your TermTalk account."""
    from cli.commands.auth import login_command
    asyncio.run(login_command())


@cli.command()
def logout():
    """Logout from your TermTalk account."""
    from cli.commands.auth import logout_command
    logout_command()


@cli.command()
@click.argument("username", required=False)
def chat(username):
    """Start chatting. Optionally specify a username for DMs."""
    from cli.commands.chat import chat_command
    asyncio.run(chat_command(username))


@cli.command()
@click.argument("username")
def add(username):
    """Send a friend request to a user."""
    from cli.commands.friends import add_friend
    asyncio.run(add_friend(username))


@cli.command()
def friends():
    """Show your friends list."""
    from cli.commands.friends import list_friends
    asyncio.run(list_friends())


@cli.command()
def requests():
    """Show pending friend requests."""
    from cli.commands.friends import show_requests
    asyncio.run(show_requests())


@cli.command()
def users():
    """Show online users."""
    from cli.commands.users import show_online
    asyncio.run(show_online())


@cli.command()
def config():
    """Configure TermTalk settings."""
    from cli.commands.config_cmd import configure
    configure()


@cli.command()
def status():
    """Show your account status."""
    from cli.commands.users import show_status
    asyncio.run(show_status())


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
