"""
Tools para operaciones de Git y GitHub.
Cubre el ciclo completo: clonar → branch → commits → PR.
"""

import re
from pathlib import Path

import git
from github import Github, GithubException

from core.config import get_settings

settings = get_settings()


# ---------------------------------------------------------------------------
# Git local (GitPython)
# ---------------------------------------------------------------------------

def _inject_token(repo_url: str) -> str:
    """Inyecta el GITHUB_TOKEN en la URL HTTPS para autenticación sin prompt."""
    token = settings.github_token
    if token and "github.com" in repo_url and "@" not in repo_url:
        repo_url = repo_url.replace("https://", f"https://x-access-token:{token}@")
    return repo_url


def clone_or_update_repo(repo_url: str, local_path: str) -> dict:
    """
    Clona el repo si no existe localmente, o hace pull si ya existe.

    Returns:
        {"success": True, "path": str} o {"error": str}
    """
    path = Path(local_path)
    auth_url = _inject_token(repo_url)
    try:
        if path.exists() and (path / ".git").exists():
            repo = git.Repo(local_path)
            # Asegurar que el remote tiene el token actualizado
            repo.remotes.origin.set_url(auth_url)
            repo.remotes.origin.pull()
            return {"success": True, "path": local_path, "action": "pulled"}
        else:
            path.mkdir(parents=True, exist_ok=True)
            git.Repo.clone_from(auth_url, local_path)
            return {"success": True, "path": local_path, "action": "cloned"}
    except Exception as e:
        return {"error": str(e)}


def create_branch(repo_path: str, branch_name: str) -> dict:
    """
    Crea y hace checkout a un nuevo branch desde main/master.

    Returns:
        {"success": True, "branch": str} o {"error": str}
    """
    try:
        repo = git.Repo(repo_path)
        # Asegurarse de estar en el branch base actualizado
        origin = repo.remotes.origin
        origin.fetch()
        base = repo.heads["main"] if "main" in repo.heads else repo.heads["master"]
        base.checkout()
        origin.pull()
        # Crear nuevo branch
        new_branch = repo.create_head(branch_name)
        new_branch.checkout()
        return {"success": True, "branch": branch_name}
    except Exception as e:
        return {"error": str(e)}


def commit_changes(repo_path: str, message: str, add_all: bool = True) -> dict:
    """
    Hace stage de cambios y crea un commit.

    Args:
        repo_path: Ruta al repositorio.
        message: Mensaje del commit (Conventional Commits).
        add_all: Si True, hace git add -A antes del commit.

    Returns:
        {"success": True, "commit_sha": str} o {"error": str, "nothing_to_commit": bool}
    """
    try:
        repo = git.Repo(repo_path)
        if add_all:
            repo.git.add("-A")
        # Verificar si hay algo para commitear
        if not repo.is_dirty(index=True, working_tree=True, untracked_files=True):
            return {"success": False, "nothing_to_commit": True, "error": "No hay cambios para commitear."}
        commit = repo.index.commit(message)
        return {"success": True, "commit_sha": commit.hexsha[:8]}
    except Exception as e:
        return {"error": str(e)}


def push_branch(repo_path: str, branch_name: str) -> dict:
    """Hace push del branch al remoto."""
    try:
        repo = git.Repo(repo_path)
        origin = repo.remotes.origin
        # Asegurar que el remote tiene el token antes del push
        current_url = list(origin.urls)[0]
        auth_url = _inject_token(current_url)
        if auth_url != current_url:
            origin.set_url(auth_url)
        origin.push(refspec=f"{branch_name}:{branch_name}", set_upstream=True)
        return {"success": True, "branch": branch_name}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# GitHub API (PyGithub)
# ---------------------------------------------------------------------------

def _get_github_repo(repo_url: str):
    """Extrae owner/repo de la URL y devuelve el objeto PyGithub Repository."""
    match = re.search(r"github\.com[:/](.+?/.+?)(?:\.git)?$", repo_url)
    if not match:
        raise ValueError(f"URL de GitHub no reconocida: {repo_url}")
    gh = Github(settings.github_token)
    return gh.get_repo(match.group(1))


def open_pull_request(
    repo_url: str,
    branch_name: str,
    title: str,
    body: str,
    base_branch: str = "main",
) -> dict:
    """
    Abre un Pull Request en GitHub.

    Returns:
        {"success": True, "pr_url": str, "pr_number": int} o {"error": str}
    """
    try:
        gh_repo = _get_github_repo(repo_url)
        pr = gh_repo.create_pull(
            title=title,
            body=body,
            head=branch_name,
            base=base_branch,
        )
        return {
            "success": True,
            "pr_url": pr.html_url,
            "pr_number": pr.number,
        }
    except GithubException as e:
        return {"error": f"GitHub API error: {e.data.get('message', str(e))}"}
    except Exception as e:
        return {"error": str(e)}


def get_pr_status(repo_url: str, pr_number: int) -> dict:
    """Devuelve el estado actual de un PR (open, closed, merged)."""
    try:
        gh_repo = _get_github_repo(repo_url)
        pr = gh_repo.get_pull(pr_number)
        return {
            "number": pr.number,
            "state": pr.state,
            "merged": pr.merged,
            "url": pr.html_url,
            "title": pr.title,
        }
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Definición de tools para Claude API
# ---------------------------------------------------------------------------

GIT_TOOLS = [
    {
        "name": "create_branch",
        "description": "Crea un nuevo branch en el repositorio para trabajar en la tarea.",
        "input_schema": {
            "type": "object",
            "properties": {
                "branch_name": {
                    "type": "string",
                    "description": "Nombre del branch. Formato: feat/task-{id}-{descripcion} o fix/task-{id}-{descripcion}.",
                }
            },
            "required": ["branch_name"],
        },
    },
    {
        "name": "commit_changes",
        "description": "Hace stage de todos los cambios y crea un commit.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Mensaje del commit en formato Conventional Commits. Ejemplo: 'feat(auth): add JWT token generation'.",
                }
            },
            "required": ["message"],
        },
    },
    {
        "name": "push_branch",
        "description": "Hace push del branch actual al repositorio remoto en GitHub.",
        "input_schema": {
            "type": "object",
            "properties": {
                "branch_name": {
                    "type": "string",
                    "description": "Nombre del branch a hacer push.",
                }
            },
            "required": ["branch_name"],
        },
    },
]
