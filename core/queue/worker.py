"""
Celery worker — ejecuta las tareas de los agentes de forma asíncrona.
"""

import asyncio
from datetime import datetime

import structlog
from celery import Celery

from core.config import get_settings
from core.database import SessionLocal
from core.models.task import Task, TaskStatus
from core.models.project import Project

logger = structlog.get_logger()
settings = get_settings()

# Instancia de Celery
celery_app = Celery(
    "agent_automation",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,           # Reencolar si el worker muere
    worker_prefetch_multiplier=1,  # Un task a la vez por worker
)


def enqueue_task(task_id: int) -> None:
    """Encola una tarea para ser procesada por el worker."""
    run_agent_task.delay(task_id)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def run_agent_task(self, task_id: int) -> dict:
    """
    Task de Celery que ejecuta un agente para completar la tarea.
    Maneja el ciclo completo: IN_PROGRESS → ejecutar agente → PR_OPEN / FAILED.
    """
    log = logger.bind(task_id=task_id, celery_task_id=self.request.id)
    db = SessionLocal()

    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            log.error("Task no encontrada en DB")
            return {"error": "Task not found"}

        project = db.query(Project).filter(Project.id == task.project_id).first()
        if not project:
            log.error("Proyecto no encontrado")
            return {"error": "Project not found"}

        # Marcar como IN_PROGRESS
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.utcnow()
        db.commit()

        log.info("Iniciando agente", project=project.name, agent=task.agent)

        # Ejecutar el agente
        from core.queue.router import route_task
        result = asyncio.run(route_task(task, project))

        if result.success:
            # Abrir PR si el agente hizo push
            if result.branch_name:
                from tools.git_tools import open_pull_request
                pr_title = f"[Task #{task.id}] {task.description[:80]}"
                pr_body = result.log
                pr_result = open_pull_request(
                    repo_url=project.repo_url,
                    branch_name=result.branch_name,
                    title=pr_title,
                    body=pr_body,
                    base_branch=project.base_branch,
                )
                if pr_result.get("success"):
                    task.pr_url = pr_result["pr_url"]
                    task.pr_number = pr_result["pr_number"]
                    task.status = TaskStatus.PR_OPEN
                    log.info("PR abierto", pr_url=task.pr_url)

                    # Notificar a Adolfo
                    from notifier.telegram_notifier import notify_pr_ready
                    asyncio.run(notify_pr_ready(
                        task_id=task.id,
                        project_name=project.name,
                        description=task.description,
                        pr_url=task.pr_url,
                        pr_number=task.pr_number,
                        branch_name=result.branch_name,
                    ))
                else:
                    task.status = TaskStatus.FAILED
                    task.error_message = pr_result.get("error", "Error al abrir PR")
            else:
                task.status = TaskStatus.DONE
        else:
            task.status = TaskStatus.FAILED
            task.error_message = result.error

            from notifier.telegram_notifier import notify_task_failed
            asyncio.run(notify_task_failed(
                task_id=task.id,
                project_name=project.name,
                description=task.description,
                error=result.error or "Error desconocido",
            ))

        task.agent_log = result.log
        task.branch_name = result.branch_name
        task.completed_at = datetime.utcnow()
        db.commit()

        return {"task_id": task_id, "status": task.status.value}

    except Exception as e:
        log.error("Error inesperado en worker", error=str(e))
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                task.completed_at = datetime.utcnow()
                db.commit()
        except Exception:
            pass
        raise self.retry(exc=e)
    finally:
        db.close()
