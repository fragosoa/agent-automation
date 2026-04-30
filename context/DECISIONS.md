# Decisiones Técnicas (ADR — Architecture Decision Records)

> Cada decisión importante va aquí con su contexto y razonamiento.
> Esto evita volver a debatir decisiones ya tomadas.

---

## ADR-001 — Telegram como canal de instrucciones

**Fecha:** 2026-04-30
**Estado:** Aceptado

**Decisión:** Usar Telegram Bot como canal principal de instrucciones.

**Por qué:**
- Gratis, sin workspace de empresa
- API simple y bien documentada (`python-telegram-bot`)
- El Chat ID personal garantiza que solo Adolfo puede enviar instrucciones
- Fácil de usar desde móvil

**Alternativas descartadas:**
- Slack: requiere workspace, más complejo de configurar para uso personal
- Discord: similar a Slack
- GitHub Issues: más lento, no es un canal de mensajería real

---

## ADR-002 — Celery + Redis para cola de tareas

**Fecha:** 2026-04-30
**Estado:** Aceptado

**Decisión:** Celery como task queue con Redis como broker.

**Por qué:**
- Celery es maduro y bien documentado en Python
- Redis es simple de operar y muy rápido
- Soporte nativo para prioridades, reintentos y monitoring

**Alternativas descartadas:**
- BullMQ (Node.js): descartado para mantener todo el stack en Python
- AWS SQS: añade dependencia cloud innecesaria para este escenario

---

## ADR-003 — LiteLLM para abstracción multi-LLM

**Fecha:** 2026-04-30
**Estado:** Aceptado

**Decisión:** LiteLLM como capa de abstracción para todos los providers de LLM.

**Por qué:**
- Interfaz OpenAI-compatible para Claude, GPT, Gemini y otros
- Cambiar de modelo no requiere cambiar código de agentes
- Soporte de fallbacks y load balancing entre modelos

---

## ADR-004 — Infraestructura: Railway

**Fecha:** 2026-04-30
**Estado:** Aceptado

**Decisión:** Desplegar en Railway como plataforma de hosting.

**Por qué:**
- Los agentes necesitan clonar repos y ejecutar procesos largos (minutos a horas)
- Serverless tiene límites de tiempo incompatibles con tareas de coding
- Railway ofrece el balance correcto entre control y simplicidad operativa

**Alternativas descartadas:**
- Hetzner VPS: más barato pero requiere gestión manual del servidor
- AWS / GCP: overkill para este escenario personal

**Responsabilidades:**
- La configuración interna de Railway (watch paths, PR environments, variables de entorno por servicio, etc.) la maneja **Adolfo directamente** en el dashboard de Railway
- Los agentes y el código del proyecto no deben asumir ni replicar esa configuración — solo leer variables de entorno en runtime

---

## ADR-005 — Claude API con tool use como agente principal

**Fecha:** 2026-04-30
**Estado:** Aceptado

**Decisión:** Implementar agentes usando Claude API directamente con tool use, no Claude Code CLI.

**Por qué:**
- Mayor control sobre el comportamiento del agente
- Tools customizados adaptados al flujo del sistema
- claude-opus-4 para tareas complejas, claude-sonnet-4 para tareas simples
- Más fácil de integrar con el orquestador (no hay proceso externo que gestionar)

---

## ADR-006 — Un branch por tarea, PR automático al terminar

**Fecha:** 2026-04-30
**Estado:** Aceptado

**Decisión:** Los agentes siempre trabajan en branches propios con naming `feat/task-{id}-{descripcion}` y abren PR automáticamente al terminar.

**Por qué:**
- Aísla el trabajo de cada agente
- Permite revisión humana antes de mergear a main
- Historial limpio y trazable de qué hizo cada agente
