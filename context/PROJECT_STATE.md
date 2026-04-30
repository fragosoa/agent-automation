# Estado Actual del Proyecto

> Este archivo se actualiza al final de cada sesión de trabajo.
> Es la primera fuente de verdad sobre qué está hecho y qué sigue.

---

## Fase Actual

**Fase 1 — MVP** (código base completo, pendiente prueba end-to-end)

---

## Qué está hecho

| Fecha | Qué se hizo |
|---|---|
| 2026-04-30 | Definición completa de arquitectura en CLAUDE.md |
| 2026-04-30 | Repositorio git inicializado |
| 2026-04-30 | .gitignore configurado para Python |
| 2026-04-30 | Archivos de contexto creados (carpeta context/) |
| 2026-04-30 | `pyproject.toml` con todas las dependencias |
| 2026-04-30 | `.env.example` con todas las variables documentadas |
| 2026-04-30 | Estructura completa de directorios (core/, agents/, tools/, channels/, notifier/) |
| 2026-04-30 | `core/config.py` — configuración con pydantic-settings |
| 2026-04-30 | `core/database.py` — SQLAlchemy + SQLite/PostgreSQL |
| 2026-04-30 | `core/models/task.py` y `core/models/project.py` |
| 2026-04-30 | `core/api/main.py`, `tasks.py`, `projects.py` — FastAPI REST API |
| 2026-04-30 | `core/queue/worker.py` — Celery worker completo |
| 2026-04-30 | `core/queue/router.py` — router de agentes con fallback |
| 2026-04-30 | `tools/file_tools.py` — leer/escribir/listar archivos |
| 2026-04-30 | `tools/bash_tool.py` — ejecutar comandos shell |
| 2026-04-30 | `tools/git_tools.py` — clone, branch, commit, push, PR |
| 2026-04-30 | `tools/search_tool.py` — buscar en codebase (ripgrep/grep) |
| 2026-04-30 | `agents/base_agent.py` — interfaz abstracta |
| 2026-04-30 | `agents/claude_agent.py` — agente Claude con tool use completo |
| 2026-04-30 | `channels/telegram_bot.py` — bot con /task, /status, /projects |
| 2026-04-30 | `notifier/telegram_notifier.py` — notificaciones de PR y errores |
| 2026-04-30 | `Dockerfile` + `docker-compose.yml` — 4 servicios: api, worker, bot, redis |
| 2026-04-30 | `projects/example-project/` — config.yml y context.md de ejemplo |

---

## Qué sigue

- [ ] Crear `.env` real con las claves (ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, GITHUB_TOKEN, etc.)
- [ ] Registrar el primer proyecto real en la DB via API o bot
- [ ] Prueba end-to-end: enviar `/task` por Telegram → agente trabaja → PR abierto → notificación
- [ ] Deploy en Railway (Adolfo configura watch paths y variables de entorno)
- [ ] Fase 2: Celery + múltiples proyectos simultáneos + /status mejorado

---

## Decisiones tomadas en sesiones anteriores

- Stack principal: Python 3.12 + FastAPI + Celery + Redis
- Canal: Telegram Bot (no Slack, no Discord)
- Agente principal: Claude API con tool use
- Multi-LLM: LiteLLM para abstracción de otros providers (Fase 3)
- Infra: Railway (Adolfo maneja configuración interna: watch paths, PR envs, secrets)
- Git: branches por tarea, PR automático al terminar

---

## Contexto importante para retomar trabajo

- El dueño del sistema es Adolfo Fragoso (fragosoadolfo1@gmail.com)
- El objetivo es que Adolfo **solo revise PRs**, todo lo demás automatizado
- Los agentes deben trabajar 24/7 sin intervención manual
- Ver CLAUDE.md para reglas completas de agentes y arquitectura
