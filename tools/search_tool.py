"""
Tool para buscar en el codebase del repositorio.
Permite al agente encontrar definiciones, usos y patrones en el código.
"""

import subprocess
from pathlib import Path


def search_in_repo(repo_path: str, pattern: str, file_glob: str = "*") -> dict:
    """
    Busca un patrón de texto (regex) en los archivos del repositorio usando ripgrep o grep.

    Args:
        repo_path: Ruta absoluta al repositorio.
        pattern: Patrón de búsqueda (regex).
        file_glob: Glob para filtrar archivos. Ejemplo: "*.py", "*.ts".

    Returns:
        {"matches": [{"file": str, "line": int, "content": str}], "total": int}
    """
    try:
        # Intentar con ripgrep primero, fallback a grep
        cmd = ["rg", "--json", "-g", file_glob, pattern, repo_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode not in (0, 1):  # rg no encontrado
            raise FileNotFoundError

        matches = []
        import json
        for line in result.stdout.splitlines():
            try:
                data = json.loads(line)
                if data.get("type") == "match":
                    m = data["data"]
                    matches.append({
                        "file": str(Path(m["path"]["text"]).relative_to(repo_path)),
                        "line": m["line_number"],
                        "content": m["lines"]["text"].rstrip(),
                    })
            except (json.JSONDecodeError, KeyError):
                continue

        return {"matches": matches[:50], "total": len(matches)}  # limitar a 50 resultados

    except FileNotFoundError:
        # Fallback a grep
        try:
            cmd = ["grep", "-rn", "--include", f"*{file_glob.lstrip('*')}", pattern, repo_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            matches = []
            for line in result.stdout.splitlines():
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    try:
                        matches.append({
                            "file": str(Path(parts[0]).relative_to(repo_path)),
                            "line": int(parts[1]),
                            "content": parts[2].strip(),
                        })
                    except (ValueError, OSError):
                        continue
            return {"matches": matches[:50], "total": len(matches)}
        except Exception as e:
            return {"error": str(e), "matches": [], "total": 0}

    except Exception as e:
        return {"error": str(e), "matches": [], "total": 0}


# Definición de tool para Claude API
SEARCH_TOOLS = [
    {
        "name": "search_in_repo",
        "description": (
            "Busca un patrón de texto o regex en el codebase del repositorio. "
            "Útil para encontrar definiciones de funciones, importaciones, usos de variables, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Patrón de búsqueda (string o regex).",
                },
                "file_glob": {
                    "type": "string",
                    "description": "Glob para filtrar archivos. Ejemplo: '*.py', '*.ts'. Default: '*'.",
                    "default": "*",
                },
            },
            "required": ["pattern"],
        },
    }
]
