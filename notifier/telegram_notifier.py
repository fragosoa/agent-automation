"""
Módulo para enviar notificaciones a Adolfo via Telegram.
Se usa para avisar cuando un PR está listo o cuando una tarea falla.
"""

import structlog
from html import escape
from telegram import Bot
from telegram.constants import ParseMode

from core.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


def h(text: str) -> str:
    """Escapa texto para uso seguro en mensajes HTML de Telegram."""
    return escape(str(text))


async def send_message(text: str) -> bool:
    """Envía un mensaje de texto al chat de Adolfo."""
    try:
        bot = Bot(token=settings.telegram_bot_token)
        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
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
        f"✅ <b>Task #{task_id} completada</b>\n\n"
        f"📦 Proyecto: <code>{h(project_name)}</code>\n"
        f"📝 Tarea: {h(description)}\n"
        f"🌿 Branch: <code>{h(branch_name)}</code>\n\n"
        f"👀 <a href=\"{h(pr_url)}\">Ver PR #{pr_number}</a>"
    )
    return await send_message(text)


async def notify_task_started(task_id: int, project_name: str, description: str) -> bool:
    """Notifica que un agente comenzó a trabajar en una tarea."""
    text = (
        f"🤖 <b>Task #{task_id} iniciada</b>\n\n"
        f"📦 Proyecto: <code>{h(project_name)}</code>\n"
        f"📝 Tarea: {h(description)}\n\n"
        "<i>El agente está trabajando...</i>"
    )
    return await send_message(text)


async def notify_task_failed(
    task_id: int, project_name: str, description: str, error: str
) -> bool:
    """Notifica que una tarea falló."""
    text = (
        f"❌ <b>Task #{task_id} falló</b>\n\n"
        f"📦 Proyecto: <code>{h(project_name)}</code>\n"
        f"📝 Tarea: {h(description)}\n\n"
        f"⚠️ Error:\n<code>{h(error[:300])}</code>"
    )
    return await send_message(text)
