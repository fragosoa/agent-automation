# Instrucciones para Agentes de IA

> Si eres un agente de IA trabajando en este proyecto, lee esto primero.
> Complementa las reglas generales de CLAUDE.md con el contexto actual.

---

## Cómo orientarte al inicio de una sesión

1. Lee `CLAUDE.md` — reglas generales y arquitectura
2. Lee `context/PROJECT_STATE.md` — qué está hecho y qué sigue
3. Lee `context/DECISIONS.md` — decisiones ya tomadas (no las replantees sin motivo)
4. Si hay tarea específica asignada, léela completa antes de tocar código

---

## Cómo terminar una sesión

Antes de terminar, actualiza `context/PROJECT_STATE.md`:
- Mueve las tareas completadas a la tabla "Qué está hecho" con la fecha
- Deja en "Qué sigue" solo lo que quedó pendiente
- Si tomaste decisiones técnicas nuevas, agrégalas a `context/DECISIONS.md`

---

## Reglas de trabajo en este proyecto

### Lo que puedes hacer sin preguntar
- Crear nuevos archivos dentro de la estructura definida en CLAUDE.md
- Escribir tests para código que implementas
- Agregar entradas a `context/DECISIONS.md` con nuevas decisiones

### Lo que debes mencionar antes de hacer
- Cambiar la estructura de directorios del proyecto
- Agregar dependencias nuevas (actualizar `pyproject.toml` o `requirements.txt`)
- Modificar el esquema de base de datos

### Lo que nunca debes hacer
- Push directo a `main`
- Hardcodear API keys o secretos
- Cambiar decisiones ya registradas en DECISIONS.md sin justificación

---

## Stack de referencia rápida

```
Lenguaje:    Python 3.12
API:         FastAPI
Cola:        Celery + Redis
DB:          SQLite (dev) / PostgreSQL (prod)
Agentes:     Claude API + LiteLLM
Git:         GitHub API + gh CLI
Canal:       Telegram Bot
Linter:      ruff
Formatter:   ruff format
Tests:       pytest
```

---

## Variables de entorno esperadas

Ver `.env.example` en la raíz del proyecto.
Nunca leer secretos de otro lugar que no sea variables de entorno.
