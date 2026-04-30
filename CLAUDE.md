# CLAUDE.md — AI Agent Automation System

> Documento de referencia para agentes de IA que trabajen en este proyecto.
> Todo agente que opere aquí debe leer este archivo antes de hacer cualquier cambio.

---

## Visión del Proyecto

Sistema personal para orquestar agentes de IA (Claude, GPT, Gemini y otros) que trabajan **24/7** en proyectos de software. El dueño del sistema (Adolfo) envía instrucciones a través de un canal (Telegram), los agentes ejecutan el trabajo de forma autónoma, y Adolfo revisa y aprueba Pull Requests durante el día.

**Objetivo principal:** Adolfo solo toca el teclado para revisar PRs y dar nuevas instrucciones. Todo lo demás es automatizado.

---

## Arquitectura General

```
Adolfo (Telegram)
    │
    ▼
[Canal de Instrucciones]  ←── Telegram Bot / Web UI
    │
    ▼
[Orquestador Central]     ←── FastAPI + Celery + Redis
    │  - Recibe instrucción
    │  - Identifica proyecto
    │  - Encola tarea con prioridad
    │  - Asigna al agente correcto
    ▼
[Agent Workers]           ←── Un worker por proyecto
    │  - Claude API (claude-opus-4 / claude-sonnet-4)
    │  - OpenAI Assistants (GPT-4o)
    │  - Gemini (via LiteLLM)
    ▼
[Repositorios GitHub]     ←── Trabaja en branches propios
    │  - Commits atómicos y descriptivos
    │  - Abre PR automático al terminar
    ▼
Adolfo recibe notificación en Telegram con link al PR
```

---

## Stack Tecnológico

| Capa | Tecnología | Notas |
|---|---|---|
| Backend principal | Python 3.12 + FastAPI | API REST + WebSockets |
| Cola de tareas | Celery + Redis | Cola por prioridad |
| Base de datos | PostgreSQL (prod) / SQLite (dev) | Estado de tareas y contexto |
| Agente principal | Claude API (`claude-opus-4`) | Tareas complejas |
| Agente secundario | Claude API (`claude-sonnet-4`) | Tareas simples / rápidas |
| Multi-LLM | LiteLLM | Abstracción para GPT, Gemini, etc. |
| Canal instrucciones | Telegram Bot (`python-telegram-bot`) | Canal principal |
| Git operations | GitHub API + `gh` CLI + GitPython | PRs automáticos |
| Containerización | Docker + Docker Compose | Un container por servicio |
| Infra | Hetzner VPS (CX21) o Railway | 24/7 uptime |
| Secrets | `.env` por entorno + Vault en prod | Nunca hardcodear keys |

---

## Estructura de Directorios

```
agent-automation/
├── CLAUDE.md                    ← Este archivo
├── docker-compose.yml           ← Levanta todos los servicios
├── .env.example                 ← Variables de entorno requeridas
│
├── core/                        ← Orquestador central
│   ├── api/                     ← FastAPI routes
│   │   ├── instructions.py      ← Recibe instrucciones
│   │   ├── tasks.py             ← CRUD de tareas
│   │   └── projects.py         ← Gestión de proyectos
│   ├── queue/                   ← Celery tasks
│   │   ├── worker.py            ← Worker principal
│   │   └── router.py            ← Enruta tarea → agente correcto
│   ├── models/                  ← Modelos de DB
│   │   ├── task.py
│   │   └── project.py
│   └── config.py                ← Configuración global
│
├── agents/                      ← Implementaciones de agentes
│   ├── base_agent.py            ← Interfaz común para todos los agentes
│   ├── claude_agent.py          ← Agente Claude (Anthropic API)
│   ├── openai_agent.py          ← Agente GPT (OpenAI Assistants)
│   └── litellm_agent.py         ← Agente genérico via LiteLLM
│
├── tools/                       ← Tools que usan los agentes
│   ├── file_tools.py            ← Leer/escribir archivos del repo
│   ├── bash_tool.py             ← Ejecutar comandos
│   ├── git_tools.py             ← Commits, branches, PRs
│   └── search_tool.py          ← Buscar en el codebase
│
├── channels/                    ← Canales de instrucciones
│   ├── telegram_bot.py          ← Bot de Telegram
│   └── webhook.py               ← Webhook genérico (GitHub Issues, etc.)
│
├── notifier/                    ← Notificaciones al usuario
│   └── telegram_notifier.py     ← Envía updates y link al PR
│
├── projects/                    ← Configuración por proyecto
│   └── {nombre-proyecto}/
│       ├── config.yml           ← Repo URL, agente preferido, reglas
│       └── context.md           ← Contexto del proyecto para el agente
│
└── tests/
    ├── unit/
    └── integration/
```

---

## Reglas para Agentes

Estas reglas aplican a **cualquier agente de IA** que trabaje en este repositorio o en cualquier proyecto gestionado por este sistema.

### Git & Branching

- **NUNCA hacer push directo a `main` o `master`**. Siempre crear un branch.
- Naming de branches: `feat/task-{id}-{descripcion-corta}` o `fix/task-{id}-{descripcion-corta}`
- Commits atómicos: un commit por cambio lógico, no un commit gigante al final
- Mensaje de commit en inglés, formato: `type(scope): descripción` (Conventional Commits)
- Al terminar la tarea, abrir un PR con título y descripción completa (qué se hizo, por qué, cómo probarlo)

### Código

- No romper tests existentes. Si hay que cambiar tests, explicar por qué en el PR
- No introducir dependencias nuevas sin mencionarlo explícitamente en el PR
- Seguir el estilo de código existente en el proyecto (linters/formatters configurados)
- Si una tarea es ambigua, hacer el trabajo más conservador e indicarlo en el PR

### Tareas

- Si la tarea es demasiado grande para resolverse en una sola ejecución, partir el trabajo en subtareas y notificar
- Si se encuentra un bug o problema inesperado durante el trabajo, documentarlo en el PR aunque no sea parte de la tarea
- No inventar funcionalidades que no fueron pedidas
- Ante la duda, hacer menos y documentar la duda en el PR

### Seguridad

- **Nunca** escribir API keys, tokens, passwords o secretos en el código
- Usar variables de entorno siempre. Referencias: `.env.example`
- No hacer logging de datos sensibles

---

## Formato de Instrucciones

Las instrucciones se envían por Telegram con el siguiente formato:

```
/task <proyecto> <descripción libre>

Ejemplos:
/task mi-api Implementa autenticación JWT con refresh tokens
/task frontend Arregla el bug donde el modal no cierra en mobile
/task mi-api Agrega endpoint GET /users/{id} con sus proyectos anidados
```

Opciones adicionales:
```
/task <proyecto> <descripción> --priority high   # Alta prioridad
/task <proyecto> <descripción> --agent gpt4      # Especificar agente
/status                                           # Ver cola de tareas
/projects                                         # Ver proyectos activos
```

---

## Configuración de un Proyecto

Cada proyecto tiene un archivo `projects/{nombre}/config.yml`:

```yaml
# projects/mi-api/config.yml
name: mi-api
repo_url: https://github.com/adolfo/mi-api
local_clone_path: /workspace/repos/mi-api
default_agent: claude-opus-4
fallback_agent: claude-sonnet-4
base_branch: main
tech_stack:
  - python
  - fastapi
  - postgresql
test_command: pytest
lint_command: ruff check .
format_command: ruff format .
pr_reviewers: []         # vacío = solo Adolfo
notifications:
  telegram: true
  on_start: false        # notificar cuando inicia
  on_finish: true        # notificar cuando PR está listo
```

---

## Flujo Completo de una Tarea

```
1. Adolfo envía: /task mi-api Implementa JWT auth

2. Telegram Bot parsea la instrucción
   → proyecto: mi-api
   → descripción: "Implementa JWT auth"
   → crea Task en DB con status: QUEUED

3. Celery encola la tarea
   → Router consulta config de mi-api
   → asigna agente: claude-opus-4

4. Agent Worker se activa
   → Clona / actualiza el repo localmente
   → Lee projects/mi-api/context.md para contexto del proyecto
   → Crea branch: feat/task-42-jwt-auth
   → Ejecuta el trabajo usando tools (leer archivos, escribir, ejecutar tests)
   → Hace commits incrementales

5. Al terminar
   → Corre tests (pytest)
   → Si pasan: abre PR en GitHub con descripción detallada
   → Actualiza Task en DB con status: PR_OPEN + link al PR

6. Notificación a Adolfo
   → Telegram: "✅ Task #42 completada — PR listo para revisar"
   → Link directo al PR

7. Adolfo revisa, aprueba y mergea
   → Sistema detecta merge (webhook de GitHub)
   → Task actualiza a status: DONE
```

---

## Variables de Entorno Requeridas

```bash
# .env.example

# APIs de IA
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_AI_API_KEY=

# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=          # Tu chat ID personal

# GitHub
GITHUB_TOKEN=              # Personal Access Token con permisos repo + PR

# Base de datos
DATABASE_URL=postgresql://user:pass@localhost:5432/agentdb
# o para dev: DATABASE_URL=sqlite:///./dev.db

# Redis
REDIS_URL=redis://localhost:6379/0

# Sistema
SECRET_KEY=                # Para JWT interno del API
ENVIRONMENT=development    # development | production
LOG_LEVEL=INFO
```

---

## Fases de Desarrollo

### Fase 1 — MVP (semana 1-2)
- [ ] Telegram Bot básico que recibe `/task` y guarda en DB
- [ ] Un agente Claude que recibe una tarea y trabaja en un repo local
- [ ] Git tools: branch, commit, PR via GitHub API
- [ ] Notificación de PR listo por Telegram
- [ ] Un proyecto de prueba configurado end-to-end

### Fase 2 — Cola y múltiples proyectos (semana 3-4)
- [ ] Celery + Redis para cola de tareas
- [ ] Soporte para múltiples proyectos (config.yml por proyecto)
- [ ] Contexto persistente por proyecto (context.md)
- [ ] Comandos /status y /projects en Telegram

### Fase 3 — Multi-agente (semana 5-6)
- [ ] LiteLLM para soporte de GPT-4, Gemini
- [ ] Router inteligente (asigna agente según tipo de tarea)
- [ ] Agentes en paralelo para distintos proyectos simultáneamente

### Fase 4 — Dashboard y refinamiento (semana 7-8)
- [ ] Web UI simple para ver estado de todas las tareas
- [ ] Reintentos automáticos si el agente falla
- [ ] Historial de tareas con diff de lo que hizo cada agente
- [ ] Métricas: tiempo por tarea, tasa de éxito, costo por tarea

---

## Decisiones Técnicas (ADR)

### Por qué Celery + Redis vs otras opciones
Celery es maduro, bien documentado y tiene soporte nativo en Python. Redis como broker es simple de operar. Alternativa considerada: BullMQ (Node.js) — descartada para mantener todo en Python.

### Por qué Telegram vs Slack/Discord
Telegram es gratis, tiene una API excelente, no requiere workspace de empresa y es más simple de configurar para uso personal. El Chat ID propio garantiza que solo Adolfo puede enviar instrucciones.

### Por qué un VPS vs serverless
Los agentes necesitan clonar repos y ejecutar procesos largos. Las funciones serverless tienen límites de tiempo y no son apropiadas. Un VPS de Hetzner (CX21, ~5€/mes) cubre perfectamente las necesidades.

### Por qué LiteLLM
Abstrae todos los providers de LLM bajo una sola interfaz OpenAI-compatible. Cambiar de Claude a GPT o Gemini no requiere cambiar código de agentes.

---

## Contacto y Ownership

- **Dueño del sistema:** Adolfo Fragoso
- **Canal de instrucciones:** Telegram personal
- **Repositorio de este sistema:** (definir URL)
- **Proyectos gestionados:** (agregar a medida que se integran)
