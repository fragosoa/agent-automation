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
            # Regenerar el grafo de dependencias y commitearlo junto con los cambios
            if result.branch_name:
                _update_dependency_graph(task_id, project.name, result.branch_name, log)

            # Abrir PR si el agente hizo push
            if result.branch_name:
                from tools.git_tools import open_pull_request
                pr_title = f"[Task #{task.id}] {task.description[:80]}"
                pr_body = (result.summary or result.log or task.description) + f"\n\n---\n*PR generado automáticamente por `{task.agent}` · Task #{task.id}*"
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


# ---------------------------------------------------------------------------
# Dependency graph helpers
# ---------------------------------------------------------------------------

def _update_dependency_graph(task_id: int, project_name: str, branch_name: str, log) -> None:
    """
    Regenera context/DEPENDENCY_GRAPH.md en el repo del proyecto
    y lo commitea en el mismo branch del agente.

    Se ejecuta automáticamente después de que el agente termina su trabajo,
    antes de abrir el PR — así el grafo siempre está actualizado en el PR.
    """
    from core.config import get_settings
    import os

    settings = get_settings()
    repo_path = os.path.join(settings.workspace_dir, project_name)
    graph_path = os.path.join(repo_path, "context", "DEPENDENCY_GRAPH.md")

    try:
        graph_content = _build_dependency_graph(repo_path)
        os.makedirs(os.path.join(repo_path, "context"), exist_ok=True)

        with open(graph_path, "w", encoding="utf-8") as f:
            f.write(graph_content)

        # Commitear el grafo actualizado en el branch del agente
        from tools.git_tools import commit_changes
        result = commit_changes(
            repo_path=repo_path,
            message="chore(context): update dependency graph",
        )
        if result.get("success"):
            log.info("Dependency graph actualizado y commiteado")
        elif result.get("nothing_to_commit"):
            log.info("Dependency graph sin cambios, no se commitea")
        else:
            log.warning("No se pudo commitear el dependency graph", error=result.get("error"))

    except Exception as e:
        # No fallar la tarea entera si esto falla — es un paso de contexto, no crítico
        log.warning("Error actualizando dependency graph", error=str(e))


def _build_dependency_graph(repo_path: str) -> str:
    """
    Analiza estáticamente los imports del proyecto y construye
    el contenido de DEPENDENCY_GRAPH.md.
    Soporta Python (ast) con fallback a grep para otros lenguajes.
    """
    import ast
    from pathlib import Path
    from collections import defaultdict
    from datetime import datetime

    root = Path(repo_path)
    EXCLUDE_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", "dist", "build", ".ruff_cache"}

    def _is_excluded(path: Path) -> bool:
        return any(part in EXCLUDE_DIRS for part in path.parts)

    # Recopilar todos los archivos .py del proyecto
    py_files = [f for f in root.rglob("*.py") if not _is_excluded(f)]

    # Construir mapa de módulo → ruta de archivo
    module_map: dict[str, Path] = {}
    for f in py_files:
        rel = f.relative_to(root)
        parts = list(rel.with_suffix("").parts)
        module_map[".".join(parts)] = f
        if parts[-1] == "__init__":
            module_map[".".join(parts[:-1])] = f

    # Calcular dependencias: archivo → [archivos que importa dentro del proyecto]
    deps: dict[str, list[str]] = {}
    for f in py_files:
        key = str(f.relative_to(root))
        deps[key] = []
        try:
            tree = ast.parse(f.read_text(errors="ignore"))
            for node in ast.walk(tree):
                mod = None
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.level == 0:
                        mod = node.module
                    else:
                        # Import relativo — resolver desde la carpeta actual
                        package_parts = list(f.relative_to(root).parent.parts)
                        for _ in range(node.level - 1):
                            package_parts = package_parts[:-1] if package_parts else package_parts
                        mod = ".".join(package_parts + ([node.module] if node.module else []))
                elif isinstance(node, ast.Import):
                    mod = node.names[0].name

                if mod and mod in module_map:
                    dep_key = str(module_map[mod].relative_to(root))
                    if dep_key != key and dep_key not in deps[key]:
                        deps[key].append(dep_key)
        except Exception:
            pass

    # Calcular aristas entrantes (quién depende de cada archivo)
    incoming: dict[str, list[str]] = defaultdict(list)
    for src, targets in deps.items():
        for tgt in targets:
            incoming[tgt].append(src)

    # Ordenar hubs por número de dependientes
    hubs = sorted(
        [(f, inc) for f, inc in incoming.items() if len(inc) >= 2],
        key=lambda x: len(x[1]),
        reverse=True,
    )
    entry_points = [f for f in deps if not deps[f] and not incoming.get(f)]
    isolated = [f for f in deps if not deps[f] and not incoming.get(f)]

    # Construir el markdown
    lines = [
        "# Dependency Graph",
        "",
        f"> Generado automáticamente por análisis estático de imports · {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC",
        "> Una arista A → B significa 'A importa B'.",
        "> Actualizado automáticamente en cada PR del sistema de agentes.",
        "",
        "---",
        "",
        "## Archivos hub (más dependidos — tocar con cuidado)",
        "",
    ]

    if hubs:
        for f, inc in hubs:
            lines.append(f"- `{f}` — usado por {len(inc)} archivo(s): {', '.join(f'`{i}`' for i in inc)}")
    else:
        lines.append("_(ningún archivo es importado por más de un módulo aún)_")

    lines += [
        "",
        "---",
        "",
        "## Entry points (sin dependencias internas)",
        "",
    ]
    entry_points = [f for f in deps if not deps[f] and incoming.get(f)]
    if entry_points:
        for f in sorted(entry_points):
            lines.append(f"- `{f}`")
    else:
        lines.append("_(no detectados)_")

    lines += [
        "",
        "---",
        "",
        "## Grafo completo (lista de adyacencia)",
        "",
    ]

    for src in sorted(deps):
        targets = deps[src]
        lines.append(f"### `{src}`")
        if targets:
            for tgt in sorted(targets):
                lines.append(f"- → `{tgt}`")
        else:
            lines.append("- _(sin dependencias internas)_")
        lines.append("")

    lines += [
        "---",
        "",
        "## Guía de búsqueda rápida",
        "",
        "| Si modificas... | Revisa también... |",
        "|---|---|",
    ]
    for f, inc in hubs:
        lines.append(f"| `{f}` | {', '.join(f'`{i}`' for i in inc)} |")

    return "\n".join(lines) + "\n"
