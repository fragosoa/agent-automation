"""
Interfaz base para todos los agentes de IA del sistema.
Cualquier agente nuevo debe extender esta clase.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AgentTask:
    """Representa una tarea que el agente debe ejecutar."""
    task_id: int
    description: str
    repo_path: str
    repo_url: str
    base_branch: str = "main"
    test_command: str | None = None
    lint_command: str | None = None
    existing_branch: str | None = None  # Si se define, trabajar en este branch en lugar de crear uno nuevo
    project_context: str = ""           # Contenido del context.md del proyecto


@dataclass
class AgentResult:
    """Resultado de la ejecución de una tarea por un agente."""
    success: bool
    branch_name: str | None = None
    pr_url: str | None = None
    pr_number: int | None = None
    log: str = ""         # Log completo de debug (tool calls, outputs) — solo para DB
    summary: str = ""     # Resumen limpio para el PR body
    error: str | None = None


class BaseAgent(ABC):
    """
    Interfaz común para todos los agentes.

    Implementar:
        - execute(task): ejecuta la tarea y devuelve un AgentResult
        - name: propiedad con el nombre del agente
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre identificador del agente (ej: 'claude-opus-4')."""
        ...

    @abstractmethod
    async def execute(self, task: AgentTask) -> AgentResult:
        """
        Ejecuta la tarea asignada.

        El agente debe:
        1. Leer el contexto del proyecto
        2. Crear un branch con el nombre correcto
        3. Implementar los cambios usando los tools disponibles
        4. Hacer commits atómicos y descriptivos
        5. Correr tests si están configurados
        6. Hacer push y devolver el resultado

        Args:
            task: La tarea a ejecutar con toda la info necesaria.

        Returns:
            AgentResult con el resultado de la ejecución.
        """
        ...

    def _build_branch_name(self, task_id: int, description: str) -> str:
        """
        Genera el nombre del branch siguiendo la convención del proyecto.
        Ejemplo: feat/task-42-jwt-auth
        """
        import re
        slug = re.sub(r"[^a-z0-9]+", "-", description.lower())[:40].strip("-")
        return f"feat/task-{task_id}-{slug}"

    def _build_pr_body(self, task: AgentTask, log: str) -> str:
        """Genera el cuerpo del PR con el contexto de la tarea."""
        return f"""## Descripción

{task.description}

## Cambios realizados

{log}

## Cómo probar

```bash
{task.test_command or "# No hay comando de test configurado para este proyecto"}
```

---
*PR generado automáticamente por el agente `{self.name}` · Task #{task.task_id}*
"""
