# 🤖 Agent Automation

Personal system to orchestrate AI agents (Claude, GPT, Gemini) that work 24/7 on software projects — so you only touch the keyboard to review Pull Requests.

---

## How it works

1. You send an instruction via Telegram: `/task my-api Implement JWT authentication`
2. The system queues the task and assigns the right AI agent
3. The agent clones the repo, creates a branch, writes the code, runs tests, and opens a PR
4. You get a Telegram notification with a direct link to the PR
5. You review, approve, and merge — that's it

```
You (Telegram)
    │
    ▼
Telegram Bot ──► Task Queue (Celery + Redis)
                      │
                      ▼
               Agent Router
               ┌─────┴──────┐
               │             │
          Claude API      LiteLLM (GPT, Gemini...)
               │
               ▼
         Your GitHub Repo
         - Creates branch
         - Writes code
         - Runs tests
         - Opens PR
               │
               ▼
       Telegram notification → you review the PR
```

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 + FastAPI |
| Task queue | Celery + Redis |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Primary agent | Claude API (`claude-opus-4`) with tool use |
| Multi-LLM | LiteLLM (GPT-4, Gemini, etc.) |
| Instruction channel | Telegram Bot |
| Git operations | GitHub API + GitPython |
| Containers | Docker + Docker Compose |
| Infrastructure | Railway |

---

## Project Structure

```
agent-automation/
├── core/
│   ├── api/           # FastAPI routes (tasks, projects)
│   ├── models/        # SQLAlchemy models (Task, Project)
│   ├── queue/         # Celery worker + agent router
│   └── config.py      # Global config via env vars
├── agents/
│   ├── base_agent.py  # Abstract interface for all agents
│   └── claude_agent.py# Claude implementation with tool use
├── tools/
│   ├── file_tools.py  # Read/write repo files
│   ├── bash_tool.py   # Run shell commands
│   ├── git_tools.py   # Branch, commit, push, open PR
│   └── search_tool.py # Search codebase
├── channels/
│   └── telegram_bot.py# Receives /task instructions
├── notifier/
│   └── telegram_notifier.py  # Sends PR links & alerts
├── projects/
│   └── {project-name}/
│       ├── config.yml # Per-project agent config
│       └── context.md # Project context for the agent
├── context/           # Memory files for AI sessions
├── docker-compose.yml
└── CLAUDE.md          # Rules for AI agents working here
```

---

## Getting Started

### 1. Clone and configure

```bash
git clone https://github.com/your-username/agent-automation
cd agent-automation
cp .env.example .env
```

Fill in `.env` with your keys:

```bash
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...       # Your personal chat ID
GITHUB_TOKEN=ghp_...
```

### 2. Run with Docker

```bash
docker compose up --build
```

This starts 4 services: `api`, `worker`, `bot`, `redis`.

### 3. Register your first project

```bash
curl -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-api",
    "repo_url": "https://github.com/your-username/my-api",
    "test_command": "pytest",
    "lint_command": "ruff check ."
  }'
```

### 4. Send your first task

Open Telegram and message your bot:

```
/task my-api Add input validation to the POST /users endpoint
```

The agent will get to work. You'll receive a Telegram notification when the PR is ready.

---

## Telegram Commands

| Command | Description |
|---|---|
| `/task <project> <description>` | Queue a new task |
| `/task <project> <description> --priority high` | High priority task |
| `/task <project> <description> --agent claude-sonnet-4` | Override the agent |
| `/status` | View recent tasks and their status |
| `/projects` | List active projects |

---

## Adding a New Project

Create a config file at `projects/{name}/config.yml`:

```yaml
name: my-api
repo_url: https://github.com/your-username/my-api
base_branch: main
default_agent: claude-opus-4
fallback_agent: claude-sonnet-4
test_command: pytest
lint_command: ruff check .
```

Create `projects/{name}/context.md` with a description of the project so the agent has context before starting work.

---

## Agent Rules

Every AI agent working in this system follows these rules:

- **Never push directly to `main`** — always works on a dedicated branch
- **Branch naming:** `feat/task-{id}-{short-description}`
- **Atomic commits** with Conventional Commits format
- **Runs tests** before pushing (if configured)
- **Never hardcodes secrets** — environment variables only
- Opens a PR with a full description of what was done and how to test it

See [`CLAUDE.md`](./CLAUDE.md) for the complete ruleset.

---

## Development Roadmap

- **Phase 1 — MVP** ✅ Single Claude agent, Telegram bot, GitHub PR automation
- **Phase 2** — Celery queue, multiple parallel projects, persistent context
- **Phase 3** — Multi-agent (GPT-4, Gemini via LiteLLM), intelligent routing
- **Phase 4** — Web dashboard, retry logic, cost & performance metrics

---

## License

MIT
