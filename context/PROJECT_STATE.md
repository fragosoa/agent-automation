# Estado Actual del Proyecto

> Este archivo se actualiza al final de cada sesión de trabajo.
> Es la primera fuente de verdad sobre qué está hecho y qué sigue.

---

## Fase Actual

**Fase 1 — MVP** (en progreso)

---

## Qué está hecho

| Fecha | Qué se hizo |
|---|---|
| 2026-04-30 | Definición completa de arquitectura en CLAUDE.md |
| 2026-04-30 | Repositorio git inicializado |
| 2026-04-30 | .gitignore configurado para Python |
| 2026-04-30 | Archivos de contexto creados (esta carpeta) |

---

## Qué sigue (Fase 1)

- [ ] Estructura base de directorios del proyecto (`core/`, `agents/`, `tools/`, etc.)
- [ ] `core/config.py` — configuración global con variables de entorno
- [ ] `core/models/task.py` y `project.py` — modelos de base de datos
- [ ] `agents/base_agent.py` — interfaz común para todos los agentes
- [ ] `agents/claude_agent.py` — agente Claude con tool use
- [ ] `tools/` — file_tools, bash_tool, git_tools, search_tool
- [ ] `channels/telegram_bot.py` — bot que recibe /task
- [ ] `notifier/telegram_notifier.py` — envía link al PR
- [ ] `.env.example` — variables de entorno documentadas
- [ ] `docker-compose.yml` — levanta todos los servicios
- [ ] Prueba end-to-end con un proyecto real

---

## Decisiones tomadas en sesiones anteriores

- Stack principal: Python 3.12 + FastAPI + Celery + Redis
- Canal: Telegram Bot (no Slack, no Discord)
- Agente principal: Claude API con tool use
- Multi-LLM: LiteLLM para abstracción de otros providers
- Infra: Hetzner VPS o Railway
- Git: branches por tarea, PR automático al terminar

---

## Contexto importante para retomar trabajo

- El dueño del sistema es Adolfo Fragoso (fragosoadolfo1@gmail.com)
- El objetivo es que Adolfo **solo revise PRs**, todo lo demás automatizado
- Los agentes deben trabajar 24/7 sin intervención manual
- Ver CLAUDE.md para reglas completas de agentes y arquitectura
