"""
Webhook de GitHub — recibe eventos de PRs y actualiza el estado de las tareas.
"""

import hashlib
import hmac
import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from core.config import get_settings
from core.database import get_db
from core.models.task import Task, TaskStatus

router = APIRouter()
logger = structlog.get_logger()
settings = get_settings()


def _verify_signature(payload: bytes, signature: str) -> bool:
    """Verifica que el webhook viene realmente de GitHub."""
    if not settings.github_webhook_secret:
        # Si no hay secret configurado, aceptar (solo para desarrollo)
        return True
    expected = "sha256=" + hmac.new(
        key=settings.github_webhook_secret.encode(),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/github")
async def github_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_github_event: str = Header(default=""),
    x_hub_signature_256: str = Header(default=""),
):
    """
    Recibe eventos de GitHub y actualiza el estado de las tareas.

    Eventos manejados:
    - pull_request (closed + merged) → Task: PR_OPEN → DONE
    - pull_request (closed sin merge) → Task: PR_OPEN → FAILED
    """
    payload = await request.body()

    # Verificar firma
    if x_hub_signature_256 and not _verify_signature(payload, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Firma inválida")

    # Solo procesar eventos de pull_request
    if x_github_event != "pull_request":
        return {"ignored": True, "event": x_github_event}

    data = await request.json()
    action = data.get("action")
    pr = data.get("pull_request", {})
    pr_number = pr.get("number")
    merged = pr.get("merged", False)

    log = logger.bind(event=x_github_event, action=action, pr_number=pr_number)

    if action != "closed" or pr_number is None:
        return {"ignored": True, "reason": "not a close event"}

    # Buscar la tarea por pr_number
    task = db.query(Task).filter(Task.pr_number == pr_number).first()
    if not task:
        log.info("No se encontró tarea para este PR")
        return {"ignored": True, "reason": "no task found for this PR"}

    if merged:
        task.status = TaskStatus.DONE
        log.info("PR mergeado — tarea marcada como DONE", task_id=task.id)
    else:
        task.status = TaskStatus.CANCELLED
        log.info("PR cerrado sin merge — tarea marcada como CANCELLED", task_id=task.id)

    db.commit()
    return {"ok": True, "task_id": task.id, "status": task.status.value}
