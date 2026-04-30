"""
Tools para leer y escribir archivos dentro del repositorio del proyecto.
Los agentes usan estas funciones para interactuar con el código fuente.
"""

import os
from pathlib import Path


def read_file(repo_path: str, file_path: str) -> dict:
    """
    Lee el contenido de un archivo del repositorio.

    Args:
        repo_path: Ruta absoluta al repositorio clonado.
        file_path: Ruta relativa al archivo dentro del repo.

    Returns:
        {"content": str, "lines": int} o {"error": str}
    """
    full_path = Path(repo_path) / file_path
    try:
        content = full_path.read_text(encoding="utf-8")
        return {"content": content, "lines": len(content.splitlines())}
    except FileNotFoundError:
        return {"error": f"Archivo no encontrado: {file_path}"}
    except Exception as e:
        return {"error": str(e)}


def write_file(repo_path: str, file_path: str, content: str) -> dict:
    """
    Escribe (o sobreescribe) un archivo en el repositorio.
    Crea los directorios intermedios si no existen.

    Args:
        repo_path: Ruta absoluta al repositorio clonado.
        file_path: Ruta relativa al archivo dentro del repo.
        content: Contenido a escribir.

    Returns:
        {"success": True, "bytes_written": int} o {"error": str}
    """
    full_path = Path(repo_path) / file_path
    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return {"success": True, "bytes_written": len(content.encode("utf-8"))}
    except Exception as e:
        return {"error": str(e)}


def list_directory(repo_path: str, dir_path: str = ".") -> dict:
    """
    Lista el contenido de un directorio del repositorio.

    Args:
        repo_path: Ruta absoluta al repositorio clonado.
        dir_path: Ruta relativa al directorio a listar.

    Returns:
        {"files": [...], "dirs": [...]} o {"error": str}
    """
    full_path = Path(repo_path) / dir_path
    try:
        entries = list(full_path.iterdir())
        return {
            "files": sorted(e.name for e in entries if e.is_file()),
            "dirs": sorted(e.name for e in entries if e.is_dir() and e.name != ".git"),
        }
    except Exception as e:
        return {"error": str(e)}


def delete_file(repo_path: str, file_path: str) -> dict:
    """Elimina un archivo del repositorio."""
    full_path = Path(repo_path) / file_path
    try:
        full_path.unlink()
        return {"success": True}
    except FileNotFoundError:
        return {"error": f"Archivo no encontrado: {file_path}"}
    except Exception as e:
        return {"error": str(e)}


def get_file_tree(repo_path: str, max_depth: int = 3) -> dict:
    """
    Devuelve el árbol de archivos del repositorio hasta una profundidad dada.
    Útil para que el agente entienda la estructura del proyecto.
    """
    tree_lines = []
    base = Path(repo_path)

    def _walk(path: Path, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return
        entries = sorted(path.iterdir(), key=lambda e: (e.is_file(), e.name))
        for i, entry in enumerate(entries):
            if entry.name in {".git", "__pycache__", ".venv", "node_modules", ".ruff_cache"}:
                continue
            connector = "└── " if i == len(entries) - 1 else "├── "
            tree_lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir():
                extension = "    " if i == len(entries) - 1 else "│   "
                _walk(entry, prefix + extension, depth + 1)

    try:
        tree_lines.append(base.name)
        _walk(base, "", 1)
        return {"tree": "\n".join(tree_lines)}
    except Exception as e:
        return {"error": str(e)}


# Definición de tools para Claude API (tool use)
FILE_TOOLS = [
    {
        "name": "read_file",
        "description": "Lee el contenido de un archivo del repositorio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Ruta relativa al archivo dentro del repositorio.",
                }
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "write_file",
        "description": "Escribe o sobreescribe un archivo en el repositorio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Ruta relativa al archivo dentro del repositorio.",
                },
                "content": {
                    "type": "string",
                    "description": "Contenido completo del archivo.",
                },
            },
            "required": ["file_path", "content"],
        },
    },
    {
        "name": "list_directory",
        "description": "Lista archivos y carpetas en un directorio del repositorio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dir_path": {
                    "type": "string",
                    "description": "Ruta relativa al directorio. Usa '.' para la raíz.",
                    "default": ".",
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_file_tree",
        "description": "Devuelve el árbol de archivos del repositorio. Úsalo al inicio para entender la estructura.",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_depth": {
                    "type": "integer",
                    "description": "Profundidad máxima del árbol.",
                    "default": 3,
                }
            },
            "required": [],
        },
    },
]
