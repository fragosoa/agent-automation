"""
Módulo para enviar notificaciones a Adolfo via Telegram.
Se usa para avisar cuando un PR está listo o cuando una tarea falla.
"""

import structlog
from telegram import Bot
from telegram.constants import ParseMode

from core.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


async def send_message(text: str) -> bool:
    """Envía un mensaje de texto al chat de Adolfo."""
    try:
        bot = Bot(token=settings.telegram_bot_token)
        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return True
    except Exception as e:
        logger.error("Error enviando notificación Telegram", error=str(e))
        return False


async def notify_pr_ready(
    task_id: int,
    project_name: str,
    description: str,
    pr_url: str,
    pr_number: int,
    branch_name: str,
) -> bool:
    """Notifica que un PR está listo para revisar."""
    text = (
        f"✅ *Task \\#{task_id} completada*\n\n"
        f"📦 Proyecto: `{_escape(project_name)}`\n"
        f"📝 Tarea: {_escape(description)}\n"
        f"🌿 Branch: `{_escape(branch_name)}`\n\n"
        f"👀 [Ver PR \\#{pr_number}]({_escape(pr_url)})"
    )
    return await send_message(text)


async def notify_task_started(task_id: int, project_name: str, description: str) -> bool:
    """Notifica que un agente comenzó a trabajar en una tarea."""
    text = (
        f"🤖 *Task \\#{task_id} iniciada*\n\n"
        f"📦 Proyecto: `{_escape(project_name)}`\n"
        f"📝 Tarea: {_escape(description)}\n\n"
        "_El agente está trabajando\\.\\.\\._"
    )
    return await send_message(text)


async def notify_task_failed(
    task_id: int, project_name: str, description: str, error: str
) -> bool:
    """Notifica que una tarea falló."""
    text = (
        f"❌ *Task \\#{task_id} falló*\n\n"
        f"📦 Proyecto: `{_escape(project_name)}`\n"
        f"📝 Tarea: {_escape(description)}\n\n"
        f"⚠️ Error:\n`{_escape(error[:300])}`"
    )
    return await send_message(text)


def _escape(text: str) -> str:
    """Escapa caracteres especiales para Telegram MarkdownV2."""
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in str(text))
