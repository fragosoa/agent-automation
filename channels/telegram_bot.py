"""
Telegram Bot — canal de instrucciones principal.

Comandos soportados:
  /task <proyecto> <descripción> [--priority high|normal|low] [--agent <modelo>]
  /status
  /projects
  /help
"""

import re
import structlog
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from core.config import get_settings
from core.database import SessionLocal
from core.models.task import Task, TaskStatus, TaskPriority
from core.models.project import Project
from core.queue.worker import enqueue_task

logger = structlog.get_logger()
settings = get_settings()


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 *Agent Automation Bot*\n\n"
        "Comandos disponibles:\n"
        "`/task <proyecto> <descripción>` — Encola una tarea\n"
        "`/status` — Ver cola de tareas\n"
        "`/projects` — Ver proyectos activos\n"
        "`/help` — Ayuda\n",
        parse_mode="Markdown",
    )


async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /task <proyecto> <descripción> [--priority high] [--agent claude-opus-4]
    """
    if not _is_authorized(update):
        await update.message.reply_text("⛔ No autorizado.")
        return

    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text(
            "Uso: `/task <proyecto> <descripción>`\n"
            "Ejemplo: `/task mi-api Implementa JWT auth`",
            parse_mode="Markdown",
        )
        return

    # Parsear opciones
    priority = TaskPriority.NORMAL
    agent_override = None

    priority_match = re.search(r"--priority\s+(high|normal|low)", text)
    if priority_match:
        priority = TaskPriority(priority_match.group(1))
        text = text.replace(priority_match.group(0), "").strip()

    agent_match = re.search(r"--agent\s+(\S+)", text)
    if agent_match:
        agent_override = agent_match.group(1)
        text = text.replace(agent_match.group(0), "").strip()

    # Separar proyecto y descripción
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await update.message.reply_text("❌ Falta la descripción. Uso: `/task <proyecto> <descripción>`")
        return

    project_name, description = parts[0], parts[1]

    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.name == project_name, Project.is_active == True).first()
        if not project:
            await update.message.reply_text(
                f"❌ Proyecto `{project_name}` no encontrado o inactivo.\n"
                "Usa `/projects` para ver los proyectos disponibles.",
                parse_mode="Markdown",
            )
            return

        task = Task(
            project_id=project.id,
            description=description,
            status=TaskStatus.QUEUED,
            priority=priority,
            agent=agent_override or project.default_agent,
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        # Encolar en Celery
        enqueue_task(task.id)

        await update.message.reply_text(
            f"✅ *Task #{task.id} encolada*\n\n"
            f"📦 Proyecto: `{project_name}`\n"
            f"📝 Tarea: {description}\n"
            f"🤖 Agente: `{task.agent}`\n"
            f"⚡ Prioridad: `{priority.value}`",
            parse_mode="Markdown",
        )

    finally:
        db.close()


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra el estado de las últimas tareas."""
    if not _is_authorized(update):
        return

    db = SessionLocal()
    try:
        tasks = (
            db.query(Task)
            .order_by(Task.created_at.desc())
            .limit(10)
            .all()
        )

        if not tasks:
            await update.message.reply_text("No hay tareas registradas.")
            return

        lines = ["*Últimas tareas:*\n"]
        status_emoji = {
            TaskStatus.QUEUED: "⏳",
            TaskStatus.IN_PROGRESS: "🔄",
            TaskStatus.PR_OPEN: "👀",
            TaskStatus.DONE: "✅",
            TaskStatus.FAILED: "❌",
            TaskStatus.CANCELLED: "🚫",
        }
        for t in tasks:
            emoji = status_emoji.get(t.status, "❓")
            lines.append(f"{emoji} `#{t.id}` {t.description[:40]} — _{t.status.value}_")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    finally:
        db.close()


async def cmd_projects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lista los proyectos activos."""
    if not _is_authorized(update):
        return

    db = SessionLocal()
    try:
        projects = db.query(Project).filter(Project.is_active == True).all()
        if not projects:
            await update.message.reply_text("No hay proyectos activos.")
            return

        lines = ["*Proyectos activos:*\n"]
        for p in projects:
            lines.append(f"• `{p.name}` — {p.repo_url}")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    finally:
        db.close()


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _is_authorized(update: Update) -> bool:
    """Solo el chat_id configurado puede enviar instrucciones."""
    return str(update.effective_chat.id) == str(settings.telegram_chat_id)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_bot() -> None:
    """Arranca el bot en modo polling."""
    logger.info("Iniciando Telegram Bot")
    app = Application.builder().token(settings.telegram_bot_token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("task", cmd_task))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("projects", cmd_projects))
    app.add_handler(CommandHandler("help", cmd_help))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run_bot()
