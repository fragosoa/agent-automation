# 🤖 Agent Automation

Personal system to orchestrate AI agents (Claude and others) that work 24/7 on software projects — so you only touch the keyboard to review Pull Requests.

---

## How it works

1. You send an instruction via Telegram: `/task my-api Implement JWT authentication`
2. The system queues the task and assigns the right AI agent
3. The agent clones the repo, creates a branch, writes the code, runs tests, and opens a PR
4. You get a Telegram notification with a direct link to the PR
5. You review, approve, and merge — that's it
6. The task status updates to DONE automatically via GitHub webhook

```
You (Telegram)
    │
    ▼
Telegram Bot ──► Task Queue (Celery + Redis)
                      │
                      ▼
               Agent Router
                    │
               Claude API (claude-opus-4-6)
                    │
                    ▼
         Your GitHub Repo
         - Reads project context
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
| Primary agent | Claude API (`claude-opus-4-6`) with tool use |
| Instruction channel | Telegram Bot |
| Git operations | GitHub API + GitPython |
| Containers | Docker + Docker Compose |
| Infrastructure | Railway |

---

## Project Structure

```
agent-automation/
├── core/
│   ├── api/           # FastAPI routes (tasks, projects, webhooks)
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
│   └── telegram_bot.py# Receives instructions
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
TELEGRAM_CHAT_ID=...
GITHUB_TOKEN=ghp_...
SECRET_KEY=...          # generate: python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Run with Docker

```bash
docker compose up --build
```

This starts 4 services: `api`, `worker`, `bot`, `redis`.

### 3. Register your first project

```bash
curl -X POST http://localhost:8000/projects/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-api",
    "repo_url": "https://github.com/your-username/my-api",
    "default_agent": "claude-opus-4-6",
    "fallback_agent": "claude-sonnet-4-6",
    "test_command": "pytest"
  }'
```

### 4. Add project context (recommended)

Create `projects/my-api/context.md` with a description of the project — stack, conventions, sensitive areas, etc. The agent reads this before starting any task.

### 5. Send your first task

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
| `/task <project> <description> --agent claude-sonnet-4-6` | Override the agent |
| `/fix <task_id> <correction>` | Fix an existing PR (works on same branch) |
| `/cancel <task_id>` | Cancel a queued task and close its PR |
| `/retry <task_id>` | Retry a failed or cancelled task |
| `/status` | View last 10 tasks and their status |
| `/projects` | List active projects |
| `/help` | Show available commands |

---

## GitHub Webhook (auto-close tasks)

Configure a webhook on each GitHub repo to automatically update task status when a PR is merged:

1. Go to your repo → **Settings → Webhooks → Add webhook**
2. **Payload URL:** `https://your-api.up.railway.app/webhooks/github`
3. **Content type:** `application/json`
4. **Secret:** value of `GITHUB_WEBHOOK_SECRET` env var
5. **Events:** Pull requests only

When you merge a PR, the task automatically moves to `DONE`.

---

## Adding a New Project

**1. Register via API:**
```bash
curl -X POST https://your-api.up.railway.app/projects/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-project",
    "repo_url": "https://github.com/your-username/my-project",
    "default_agent": "claude-opus-4-6",
    "fallback_agent": "claude-sonnet-4-6",
    "test_command": "pytest",
    "lint_command": "ruff check ."
  }'
```

**2. Create project context:**

Create `projects/my-project/context.md`:
```markdown
# Project Context: my-project

## Description
What this project does.

## Stack
- Python 3.12 + FastAPI
- PostgreSQL

## Conventions
- Tests in tests/ with pytest
- Commits in English, Conventional Commits format

## Things to keep in mind
- Don't touch the auth module without asking
- External API keys are in .env
```

---

## Agent Rules

Every AI agent working in this system follows these rules:

- **Never push directly to `main`** — always works on a dedicated branch
- **Branch naming:** `feat/task-{id}-{short-description}`
- **Atomic commits** with Conventional Commits format
- **Runs tests** before pushing (if configured)
- **Never hardcodes secrets** — environment variables only
- **Never runs `env` or `printenv`** — environment variables may contain secrets
- Opens a PR with a clean description of what was done

See [`CLAUDE.md`](./CLAUDE.md) for the complete ruleset.

---

## Development Roadmap

- **Phase 1 — MVP** ✅ Single Claude agent, Telegram bot, GitHub PR automation
- **Phase 2** ✅ Persistent project context, /fix, /cancel, /retry, GitHub webhook
- **Phase 3** — Multi-agent (GPT-4o via LiteLLM), intelligent routing
- **Phase 4** — Web dashboard, retry logic, cost & performance metrics

---

## License

MIT
