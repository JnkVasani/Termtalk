# TermTalk 🖥️💬

> **Terminal-based communication platform — chat globally from your CLI**

TermTalk is a production-ready, open-source CLI messaging platform. Think WhatsApp or Discord, but entirely in your terminal. Real-time messaging, group chats, file sharing, friend systems — all from the command line.

```
  ______                  ______      ____  
 /_  __/__  _________ _  /_  __/___ _/ / /__
  / / / _ \/ ___/ __ `/   / / / __ `/ / //_/
 / / /  __/ /  / /_/ /   / / / /_/ / / ,<   
/_/  \___/_/   \__,_/   /_/  \__,_/_/_/|_|  
```

## ✨ Features

- **Real-time messaging** via WebSockets
- **User authentication** with JWT tokens & bcrypt
- **Friend system** — requests, accept/reject, online status
- **Group chats / channels** — create, join, leave rooms
- **Direct messages** — private 1:1 conversations
- **File sharing** — images, PDFs, videos, code files (up to 100MB)
- **Message history** — persistent storage, delivered on reconnect
- **Offline messaging** — messages queued and delivered when reconnected
- **Emoji support** — full Unicode emoji in messages
- **Online presence** — see who's online in real time
- **Notifications** — new messages, friend requests, file transfers
- **Markdown support** — `**bold**`, `*italic*`, `` `code` `` in messages
- **Modern TUI** — Rich-powered terminal interface with colors & layout
- **End-to-end encryption** ready — public key exchange support
- **Docker support** — one command deployment
- **PyPI installable** — `pip install termtalk`

---

## 🚀 Quick Start

### Install the CLI

```bash
pip install termtalk
```

### Register & start chatting

```bash
termtalk register          # Create an account
termtalk login             # Login
termtalk chat              # Open the chat interface
```

That's it! You're in the `#general` room.

---

## 📦 Installation

### Option 1: PyPI (Recommended)

```bash
pip install termtalk                    # CLI client only
pip install "termtalk[server]"          # CLI + server dependencies
```

### Option 2: From Source

```bash
git clone https://github.com/termtalk/termtalk.git
cd termtalk
pip install -e ".[server,dev]"
```

---

## 🖥️ Running the Server

### Development (SQLite)

```bash
# Set environment (optional — defaults work out of the box)
export SECRET_KEY="your-secret-key"

# Start server
termtalk-server
# OR
python -m server.main
```

Server starts at `http://localhost:8000`

### Production (Docker + PostgreSQL)

```bash
# Clone the repo
git clone https://github.com/termtalk/termtalk.git
cd termtalk

# Configure environment
cp .env.example .env
# Edit .env: set SECRET_KEY, etc.

# Start everything
docker-compose up -d

# Server is now at http://localhost:8000
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `DATABASE_URL` | `sqlite+aiosqlite:///./termtalk.db` | Database connection string |
| `SECRET_KEY` | `change-me-in-production` | JWT secret key |
| `UPLOAD_DIR` | `./uploads` | File storage directory |
| `MAX_FILE_SIZE` | `104857600` | Max file size (100MB) |
| `DEBUG` | `false` | Enable debug mode |

### Deploy to Render

1. Fork this repo
2. Create a new Web Service on [Render](https://render.com)
3. Set build command: `pip install ".[server]"`
4. Set start command: `termtalk-server`
5. Add environment variables

### Deploy to Railway

```bash
railway login
railway new
railway up
```

---

## ⌨️ CLI Commands

### Account Management

```bash
termtalk register          # Create new account
termtalk login             # Login
termtalk logout            # Logout
termtalk status            # View your profile
termtalk config            # Configure server URL
```

### Chat

```bash
termtalk chat              # Open chat (general room)
termtalk chat alice        # Open DM with alice
```

### Friends

```bash
termtalk add alice         # Send friend request to alice
termtalk friends           # List your friends
termtalk requests          # View pending friend requests
termtalk users             # See who's online
```

---

## 💬 In-Chat Commands

Once inside the chat interface, use these slash commands:

| Command | Description |
|---|---|
| `/msg <user> <text>` | Send a direct message |
| `/create-room <name>` | Create a new room |
| `/join <room>` | Join an existing room |
| `/leave` | Leave current room |
| `/rooms` | List all public rooms |
| `/history [room]` | View message history |
| `/sendfile <path>` | Send a file to current room |
| `/sendfile <user> <path>` | Send a file to a user |
| `/download <id> [path]` | Download a file |
| `/users` | Show online users |
| `/friends` | Show friends list |
| `/add <user>` | Send friend request |
| `/accept <user>` | Accept friend request |
| `/clear` | Clear chat window |
| `/help` | Show all commands |
| `Ctrl+C` or `/quit` | Exit |

### Markdown in Messages

```
**bold text**
*italic text*
`inline code`
https://links-are-highlighted.com
```

---

## 🏗️ Architecture

```
termtalk/
├── server/                    # FastAPI backend
│   ├── main.py                # Application entry point
│   ├── config.py              # Settings management
│   ├── database/
│   │   └── db.py              # SQLAlchemy models + async engine
│   ├── auth/
│   │   └── auth.py            # JWT + bcrypt authentication
│   ├── websocket/
│   │   └── manager.py         # WebSocket connection manager
│   └── api/
│       ├── routes.py           # Router aggregation
│       ├── users.py            # User registration, login, profile
│       ├── rooms.py            # Room CRUD + membership
│       ├── messages.py         # Message history
│       ├── files.py            # File upload/download
│       └── friends.py          # Friend system
│
├── cli/                       # Python CLI client
│   ├── main.py                # Click CLI entry point
│   ├── config.py              # Config + token storage (~/.termtalk/)
│   ├── commands/
│   │   ├── auth.py            # register / login / logout
│   │   ├── chat.py            # chat command + slash commands
│   │   ├── friends.py         # friend management
│   │   ├── users.py           # online users / status
│   │   └── config_cmd.py      # configure server URL
│   ├── network/
│   │   └── client.py          # HTTP (httpx) + WebSocket client
│   └── ui/
│       ├── chat_ui.py         # Full Rich TUI chat interface
│       └── theme.py           # Colors, markdown, formatting
│
├── tests/
│   ├── server/
│   │   └── test_api.py        # API endpoint tests
│   └── cli/
│       └── test_cli.py        # CLI unit tests
│
├── docker-compose.yml         # Docker Compose (server + PostgreSQL)
├── Dockerfile.server          # Server Docker image
├── pyproject.toml             # Package configuration
└── README.md                  # This file
```

### Data Flow

```
CLI Client                    Server
──────────                    ──────
termtalk chat
    │
    ├─► HTTP POST /login ────► JWT token
    │
    ├─► WS connect /ws ──────► ConnectionManager
    │       │                       │
    │       ├─ send message ────────► broadcast to room members
    │       │                       │
    │       └─ receive msgs ◄───────┤
    │                               │
    └─► HTTP GET /history ──────────► SQLite/PostgreSQL
```

---

## 🧪 Testing

```bash
# Install dev dependencies
pip install ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/server/test_api.py -v
pytest tests/cli/test_cli.py -v
```

---

## 🔒 Security

- Passwords hashed with **bcrypt** (cost factor 12)
- Authentication via **JWT tokens** (7-day expiry by default)
- Token stored in `~/.termtalk/token` with `600` permissions
- Public key exchange support for **end-to-end encryption** (client-side implementation pluggable)
- File type allowlist prevents executable uploads
- 100MB file size limit

---

## 🔌 Plugin System

Extend TermTalk by adding custom commands in `~/.termtalk/plugins/`:

```python
# ~/.termtalk/plugins/my_plugin.py
def register_commands(command_handler):
    async def my_command(args, room, ws, api, ui):
        ui.add_system("Hello from my plugin!")
    
    command_handler.register("/mycommand", my_command)
```

---

## 🗺️ Roadmap

- [ ] Voice messages (WebRTC)
- [ ] Message reactions / emoji reactions
- [ ] Message editing and deletion
- [ ] Read receipts
- [ ] User avatars (image rendering in terminal)
- [ ] Bot API
- [ ] Threads / reply chains
- [ ] S3 cloud storage backend
- [ ] Mobile push notifications via ntfy.sh

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) — Modern Python web framework
- [Rich](https://github.com/Textualize/rich) — Beautiful terminal output
- [SQLAlchemy](https://sqlalchemy.org/) — Python SQL toolkit
- [websockets](https://websockets.readthedocs.io/) — WebSocket library
- [Click](https://click.palletsprojects.com/) — CLI framework

---

*Made with ❤️ for developers who live in the terminal.*
