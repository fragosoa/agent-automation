"""
Router de agentes — decide qué agente ejecuta cada tarea
y prepara el contexto necesario.
"""

import os
import structlog
from core.config import get_settings
from core.models.task import Task
from core.models.project import Project
from agents.base_agent import AgentTask, AgentResult

logger = structlog.get_logger()
settings = get_settings()


async def route_task(task: Task, project: Project) -> AgentResult:
    """
    Selecciona el agente correcto para la tarea y lo ejecuta.

    Criterio de selección:
    1. Si la task tiene agent_override, úsalo.
    2. Si no, usa el default_agent del proyecto.
    3. Si falla, reintenta con el fallback_agent.
    """
    agent_name = task.agent or project.default_agent
    agent = _build_agent(agent_name)

    repo_path = _get_repo_path(project)
    agent_task = AgentTask(
        task_id=task.id,
        description=task.description,
        repo_path=repo_path,
        repo_url=project.repo_url,
        base_branch=project.base_branch,
        test_command=project.test_command,
        lint_command=project.lint_command,
        existing_branch=task.branch_name or None,  # Si la task tiene branch, trabajar en él
    )

    # Asegurarse de que el repo está clonado/actualizado antes de empezar
    import shutil
    from pathlib import Path
    from tools.git_tools import clone_or_update_repo, _inject_token

    # Si el repo existe pero el remote no tiene token, borrarlo para re-clonar limpio
    repo_dir = Path(repo_path)
    if repo_dir.exists() and (repo_dir / ".git").exists():
        try:
            import git as gitpkg
            existing_repo = gitpkg.Repo(repo_path)
            current_url = list(existing_repo.remotes.origin.urls)[0]
            if "@" not in current_url:
                logger.info("Remote sin token detectado, re-clonando repo", path=repo_path)
                shutil.rmtree(repo_path)
        except Exception:
            pass

    clone_result = clone_or_update_repo(project.repo_url, repo_path)
    if "error" in clone_result:
        logger.error("Error clonando repo", error=clone_result["error"])
        return AgentResult(
            success=False,
            error=f"No se pudo clonar/actualizar el repo: {clone_result['error']}",
        )

    logger.info("Ejecutando agente", agent=agent.name, task_id=task.id)
    result = await agent.execute(agent_task)

    # Si falló y hay fallback, reintentamos con otro agente
    if not result.success and project.fallback_agent and project.fallback_agent != agent_name:
        logger.warning(
            "Agente principal falló, reintentando con fallback",
            primary=agent_name,
            fallback=project.fallback_agent,
        )
        fallback = _build_agent(project.fallback_agent)
        result = await fallback.execute(agent_task)

    return result


def _build_agent(agent_name: str):
    """Instancia el agente correspondiente al nombre."""
    if "claude" in agent_name.lower():
        from agents.claude_agent import ClaudeAgent
        return ClaudeAgent(model=agent_name)
    elif "gpt" in agent_name.lower():
        # Placeholder para futura integración con OpenAI
        raise NotImplementedError(f"Agente GPT aún no implementado: {agent_name}")
    else:
        # Fallback: intentar con LiteLLM en el futuro
        raise ValueError(f"Agente no reconocido: {agent_name}")


def _get_repo_path(project: Project) -> str:
    """Devuelve la ruta local donde se clona el repositorio del proyecto."""
    workspace = settings.workspace_dir
    return os.path.join(workspace, project.name)
