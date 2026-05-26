# Estado Actual del Proyecto

> Este archivo se actualiza al final de cada sesión de trabajo.
> Es la primera fuente de verdad sobre qué está hecho y qué sigue.

---

## Fase Actual

**Fase 2 — completa** · Deploy en Railway funcionando end-to-end

---

## Qué está hecho

| Fecha | Qué se hizo |
|---|---|
| 2026-04-30 | Definición completa de arquitectura en CLAUDE.md |
| 2026-04-30 | Repositorio git inicializado, .gitignore, archivos de contexto |
| 2026-04-30 | `pyproject.toml` con todas las dependencias |
| 2026-04-30 | `.env.example` con todas las variables documentadas |
| 2026-04-30 | Estructura completa de directorios (core/, agents/, tools/, channels/, notifier/) |
| 2026-04-30 | `core/config.py`, `core/database.py`, modelos Task y Project |
| 2026-04-30 | FastAPI REST API — endpoints tasks, projects, webhooks |
| 2026-04-30 | `core/queue/worker.py` — Celery worker con retry y dependency graph |
| 2026-04-30 | `core/queue/router.py` — router de agentes con fallback |
| 2026-04-30 | `tools/` — file, bash, git (con token injection), search |
| 2026-04-30 | `agents/base_agent.py` + `agents/claude_agent.py` — tool use completo |
| 2026-04-30 | `channels/telegram_bot.py` — bot Telegram |
| 2026-04-30 | `notifier/telegram_notifier.py` — notificaciones HTML |
| 2026-04-30 | `Dockerfile` + `docker-compose.yml` |
| 2026-05-26 | Deploy en Railway — 3 servicios (api, worker, bot) + Redis + PostgreSQL |
| 2026-05-26 | Prueba end-to-end completa: Telegram → agente → PR → notificación → merge |
| 2026-05-26 | Fix: GITHUB_TOKEN inyectado en remote URL para autenticación en push |
| 2026-05-26 | Fix: modelos Claude actualizados a `claude-opus-4-6` y `claude-sonnet-4-6` |
| 2026-05-26 | Fix: PR body usa summary limpio, logs sanitizados (no expone secrets) |
| 2026-05-26 | Fix: bot migrado a parse_mode HTML para evitar errores de Markdown |
| 2026-05-26 | Webhook de GitHub — PR mergeado → tarea cambia a DONE automáticamente |
| 2026-05-26 | Contexto persistente por proyecto — agente lee `context.md` antes de cada tarea |
| 2026-05-26 | Comando `/fix <task_id> <corrección>` — corrige PR existente en mismo branch |
| 2026-05-26 | Comando `/cancel <task_id>` — cancela tarea y cierra PR en GitHub |
| 2026-05-26 | Comando `/retry <task_id>` — reintenta tarea fallida o cancelada |
| 2026-05-26 | Fix: `/fix` reutiliza PR existente en lugar de crear duplicado |
| 2026-05-26 | `core/api/webhooks.py` — endpoint POST /webhooks/github |
| 2026-05-26 | `agent_log` expuesto en GET /tasks/{id} para debugging |

---

## Qué sigue

- [ ] Fase 3: Multi-agente via LiteLLM (GPT-4o, Gemini) — en hold
  - `agents/litellm_agent.py` ya creado pero no deployado
  - Requiere `OPENAI_API_KEY` en Railway
- [ ] Prioridades reales en cola de Celery (Fase 2 pendiente menor)
- [ ] Fase 4: Web dashboard, métricas de costo y tiempo por tarea

---

## Comandos disponibles en el bot

| Comando | Descripción |
|---|---|
| `/task <proyecto> <descripción>` | Encola una tarea nueva |
| `/task <proyecto> <descripción> --priority high` | Tarea con alta prioridad |
| `/task <proyecto> <descripción> --agent claude-sonnet-4-6` | Override del agente |
| `/fix <task_id> <corrección>` | Corrige el PR de una tarea existente |
| `/cancel <task_id>` | Cancela tarea y cierra PR en GitHub |
| `/retry <task_id>` | Reintenta tarea fallida o cancelada |
| `/status` | Ver las últimas 10 tareas |
| `/projects` | Ver proyectos activos |
| `/help` | Lista de comandos |

---

## Infra en Railway

- **URL API:** https://api-production-6afb.up.railway.app
- **Servicios:** api, worker, bot (mismo repo, distinto start command)
- **Databases:** PostgreSQL + Redis (Railway managed)
- **Variables clave:** `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GITHUB_TOKEN`, `GITHUB_WEBHOOK_SECRET`, `SECRET_KEY`, `PYTHONPATH=/app`

---

## Decisiones tomadas

- Stack principal: Python 3.12 + FastAPI + Celery + Redis
- Canal: Telegram Bot (no Slack, no Discord)
- Agente principal: Claude API con tool use (`claude-opus-4-6`)
- Multi-LLM: LiteLLM para abstracción de otros providers (Fase 3, en hold)
- Infra: Railway (Adolfo maneja configuración interna: watch paths, PR envs, secrets)
- Git: branches por tarea, PR automático al terminar
- Parse mode Telegram: HTML (más robusto que Markdown)

---

## Contexto importante para retomar trabajo

- El dueño del sistema es Adolfo Fragoso (fragosoadolfo1@gmail.com)
- El objetivo es que Adolfo **solo revise PRs**, todo lo demás automatizado
- Los agentes deben trabajar 24/7 sin intervención manual
- Ver CLAUDE.md para reglas completas de agentes y arquitectura
- Para agregar un proyecto: POST /projects/ + crear `projects/{name}/context.md`
