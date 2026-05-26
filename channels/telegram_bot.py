"""
Telegram Bot — canal de instrucciones principal.

Comandos soportados:
  /task <proyecto> <descripción> [--priority high|normal|low] [--agent <modelo>]
  /fix <task_id> <corrección>
  /status
  /projects
  /help
"""

import re
import structlog
from html import escape
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
# Helpers
# ---------------------------------------------------------------------------

def h(text: str) -> str:
    """Escapa texto para uso seguro en mensajes HTML de Telegram."""
    return escape(str(text))


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 <b>Agent Automation Bot</b>\n\n"
        "Comandos disponibles:\n"
        "<code>/task &lt;proyecto&gt; &lt;descripción&gt;</code> — Encola una tarea nueva\n"
        "<code>/fix &lt;task_id&gt; &lt;corrección&gt;</code> — Corrige el PR de una tarea existente\n"
        "<code>/cancel &lt;task_id&gt;</code> — Cancela una tarea encolada\n"
        "<code>/retry &lt;task_id&gt;</code> — Reintenta una tarea fallida o cancelada\n"
        "<code>/status</code> — Ver las últimas tareas\n"
        "<code>/projects</code> — Ver proyectos activos\n"
        "<code>/agents</code> — Ver agentes disponibles\n"
        "<code>/help</code> — Ayuda\n",
        parse_mode="HTML",
    )


async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /task <proyecto> <descripción> [--priority high] [--agent claude-opus-4-6]
    """
    if not _is_authorized(update):
        await update.message.reply_text("⛔ No autorizado.")
        return

    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text(
            "Uso: <code>/task &lt;proyecto&gt; &lt;descripción&gt;</code>\n"
            "Ejemplo: <code>/task mi-api Implementa JWT auth</code>",
            parse_mode="HTML",
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
        await update.message.reply_text(
            "❌ Falta la descripción. Uso: <code>/task &lt;proyecto&gt; &lt;descripción&gt;</code>",
            parse_mode="HTML",
        )
        return

    project_name, description = parts[0], parts[1]

    db = SessionLocal()
    try:
        project = db.query(Project).filter(
            Project.name == project_name,
            Project.is_active == True,
        ).first()

        if not project:
            await update.message.reply_text(
                f"❌ Proyecto <code>{h(project_name)}</code> no encontrado o inactivo.\n"
                "Usa <code>/projects</code> para ver los proyectos disponibles.",
                parse_mode="HTML",
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

        enqueue_task(task.id)

        await update.message.reply_text(
            f"✅ <b>Task #{task.id} encolada</b>\n\n"
            f"📦 Proyecto: <code>{h(project_name)}</code>\n"
            f"📝 Tarea: {h(description)}\n"
            f"🤖 Agente: <code>{h(task.agent)}</code>\n"
            f"⚡ Prioridad: <code>{priority.value}</code>",
            parse_mode="HTML",
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

        status_emoji = {
            TaskStatus.QUEUED: "⏳",
            TaskStatus.IN_PROGRESS: "🔄",
            TaskStatus.PR_OPEN: "👀",
            TaskStatus.DONE: "✅",
            TaskStatus.FAILED: "❌",
            TaskStatus.CANCELLED: "🚫",
        }

        lines = ["<b>Últimas tareas:</b>\n"]
        for t in tasks:
            emoji = status_emoji.get(t.status, "❓")
            desc = h(t.description[:40])
            lines.append(f"{emoji} <code>#{t.id}</code> {desc} — <i>{t.status.value}</i>")

        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
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

        lines = ["<b>Proyectos activos:</b>\n"]
        for p in projects:
            lines.append(f"• <code>{h(p.name)}</code> — {h(p.repo_url)}")

        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
    finally:
        db.close()


async def cmd_fix(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /fix <task_id> <corrección>
    Crea una tarea de corrección que trabaja en el branch del PR existente.
    """
    if not _is_authorized(update):
        await update.message.reply_text("⛔ No autorizado.")
        return

    text = " ".join(context.args) if context.args else ""
    parts = text.split(maxsplit=1)

    if len(parts) < 2 or not parts[0].isdigit():
        await update.message.reply_text(
            "Uso: <code>/fix &lt;task_id&gt; &lt;corrección&gt;</code>\n"
            "Ejemplo: <code>/fix 5 Agrega sección de instalación al README</code>",
            parse_mode="HTML",
        )
        return

    task_id = int(parts[0])
    correction = parts[1]

    db = SessionLocal()
    try:
        original = db.query(Task).filter(Task.id == task_id).first()
        if not original:
            await update.message.reply_text(f"❌ Tarea <code>#{task_id}</code> no encontrada.", parse_mode="HTML")
            return

        if not original.branch_name:
            await update.message.reply_text(
                f"❌ La tarea <code>#{task_id}</code> no tiene un branch asociado.\n"
                "Solo puedes usar <code>/fix</code> en tareas que ya abrieron un PR.",
                parse_mode="HTML",
            )
            return

        project = db.query(Project).filter(Project.id == original.project_id).first()

        fix_task = Task(
            project_id=original.project_id,
            description=f"[FIX de #{task_id}] {correction}",
            status=TaskStatus.QUEUED,
            priority=TaskPriority.HIGH,
            agent=original.agent,
            branch_name=original.branch_name,
        )
        db.add(fix_task)
        db.commit()
        db.refresh(fix_task)

        enqueue_task(fix_task.id)

        await update.message.reply_text(
            f"🔧 <b>Fix #{fix_task.id} encolado</b>\n\n"
            f"📦 Proyecto: <code>{h(project.name)}</code>\n"
            f"🔗 Branch: <code>{h(original.branch_name)}</code>\n"
            f"📝 Corrección: {h(correction)}\n"
            f"🤖 Agente: <code>{h(fix_task.agent)}</code>",
            parse_mode="HTML",
        )

    finally:
        db.close()


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /cancel <task_id>
    Cancela una tarea que esté en estado QUEUED.
    """
    if not _is_authorized(update):
        await update.message.reply_text("⛔ No autorizado.")
        return

    args = context.args or []
    if not args or not args[0].isdigit():
        await update.message.reply_text(
            "Uso: <code>/cancel &lt;task_id&gt;</code>\n"
            "Ejemplo: <code>/cancel 5</code>",
            parse_mode="HTML",
        )
        return

    task_id = int(args[0])
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            await update.message.reply_text(
                f"❌ Tarea <code>#{task_id}</code> no encontrada.",
                parse_mode="HTML",
            )
            return

        if task.status == TaskStatus.IN_PROGRESS:
            await update.message.reply_text(
                f"⚠️ La tarea <code>#{task_id}</code> está en progreso y no puede cancelarse.\n"
                "Espera a que termine o falle.",
                parse_mode="HTML",
            )
            return

        if task.status in (TaskStatus.DONE, TaskStatus.CANCELLED):
            await update.message.reply_text(
                f"ℹ️ La tarea <code>#{task_id}</code> ya está en estado <i>{task.status.value}</i>.",
                parse_mode="HTML",
            )
            return

        task.status = TaskStatus.CANCELLED
        db.commit()

        # Cerrar el PR en GitHub si existe
        pr_closed = False
        if task.pr_number:
            project = db.query(Project).filter(Project.id == task.project_id).first()
            try:
                from tools.git_tools import _get_github_repo
                gh_repo = _get_github_repo(project.repo_url)
                pr = gh_repo.get_pull(task.pr_number)
                pr.edit(state="closed")
                pr_closed = True
            except Exception as e:
                logger.warning("No se pudo cerrar el PR", pr=task.pr_number, error=str(e))

        msg = f"🚫 <b>Task #{task_id} cancelada</b>\n\n📝 {h(task.description[:60])}"
        if pr_closed:
            msg += f"\n🔒 PR #{task.pr_number} cerrado en GitHub"
        elif task.pr_number:
            msg += f"\n⚠️ No se pudo cerrar el PR #{task.pr_number} automáticamente"

        await update.message.reply_text(msg, parse_mode="HTML")
    finally:
        db.close()


async def cmd_retry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /retry <task_id>
    Reintenta una tarea fallida o cancelada.
    """
    if not _is_authorized(update):
        await update.message.reply_text("⛔ No autorizado.")
        return

    args = context.args or []
    if not args or not args[0].isdigit():
        await update.message.reply_text(
            "Uso: <code>/retry &lt;task_id&gt;</code>\n"
            "Ejemplo: <code>/retry 5</code>",
            parse_mode="HTML",
        )
        return

    task_id = int(args[0])
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            await update.message.reply_text(
                f"❌ Tarea <code>#{task_id}</code> no encontrada.",
                parse_mode="HTML",
            )
            return

        if task.status not in (TaskStatus.FAILED, TaskStatus.CANCELLED):
            await update.message.reply_text(
                f"⚠️ Solo puedes reintentar tareas <i>fallidas</i> o <i>canceladas</i>.\n"
                f"La tarea <code>#{task_id}</code> está en estado <i>{task.status.value}</i>.",
                parse_mode="HTML",
            )
            return

        # Resetear estado y limpiar campos del intento anterior
        task.status = TaskStatus.QUEUED
        task.error_message = None
        task.agent_log = None
        task.branch_name = None
        task.pr_url = None
        task.pr_number = None
        task.started_at = None
        task.completed_at = None
        db.commit()

        enqueue_task(task.id)

        project = db.query(Project).filter(Project.id == task.project_id).first()
        await update.message.reply_text(
            f"🔁 <b>Task #{task_id} reintentando</b>\n\n"
            f"📦 Proyecto: <code>{h(project.name)}</code>\n"
            f"📝 {h(task.description[:60])}\n"
            f"🤖 Agente: <code>{h(task.agent)}</code>",
            parse_mode="HTML",
        )
    finally:
        db.close()


async def cmd_agents(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lista los agentes disponibles según las API keys configuradas."""
    if not _is_authorized(update):
        return

    lines = ["<b>Agentes disponibles:</b>\n"]

    # Claude (Anthropic)
    if settings.anthropic_api_key:
        lines.append("🟣 <b>Anthropic (Claude)</b>")
        lines.append("  • <code>claude-opus-4-6</code> — máxima capacidad")
        lines.append("  • <code>claude-sonnet-4-6</code> — rápido y eficiente")
        lines.append("")

    # OpenAI (GPT)
    if settings.openai_api_key:
        lines.append("🟢 <b>OpenAI (GPT)</b>")
        lines.append("  • <code>gpt-4o</code> — modelo principal")
        lines.append("  • <code>gpt-4o-mini</code> — rápido y económico")
        lines.append("")

    # Google (Gemini)
    if settings.google_ai_api_key:
        lines.append("🔵 <b>Google (Gemini)</b>")
        lines.append("  • <code>gemini/gemini-1.5-pro</code>")
        lines.append("  • <code>gemini/gemini-1.5-flash</code>")
        lines.append("")

    lines.append(f"⚙️ Agente por defecto: <code>{h(settings.default_agent)}</code>")
    lines.append("\nUso: <code>/task proyecto descripción --agent gpt-4o</code>")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


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
    app.add_handler(CommandHandler("fix", cmd_fix))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("retry", cmd_retry))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("projects", cmd_projects))
    app.add_handler(CommandHandler("agents", cmd_agents))
    app.add_handler(CommandHandler("help", cmd_help))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run_bot()
