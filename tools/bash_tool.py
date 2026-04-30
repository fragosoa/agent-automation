"""
Tool para ejecutar comandos de shell dentro del repositorio del proyecto.
Usado por los agentes para correr tests, linters, formatters, etc.
"""

import subprocess
from pathlib import Path


DEFAULT_TIMEOUT = 120  # segundos


def run_command(
    repo_path: str,
    command: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """
    Ejecuta un comando en el directorio del repositorio.

    Args:
        repo_path: Ruta absoluta al repositorio clonado.
        command: Comando a ejecutar (string, se pasa a bash -c).
        timeout: Tiempo máximo en segundos.

    Returns:
        {"stdout": str, "stderr": str, "returncode": int, "success": bool}
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Comando cancelado: superó el timeout de {timeout}s.",
            "returncode": -1,
            "success": False,
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
            "success": False,
        }


# Definición de tool para Claude API
BASH_TOOLS = [
    {
        "name": "run_command",
        "description": (
            "Ejecuta un comando de shell en el repositorio. "
            "Úsalo para correr tests (pytest), linters (ruff), "
            "o cualquier comando necesario para el proyecto."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Comando bash a ejecutar.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout en segundos. Default: 120.",
                    "default": 120,
                },
            },
            "required": ["command"],
        },
    }
]
