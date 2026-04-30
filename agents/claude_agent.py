"""
Agente Claude — implementación usando Claude API con tool use.
Usa claude-opus-4 por defecto para tareas complejas de coding.
"""

import json
import structlog
import anthropic

from agents.base_agent import BaseAgent, AgentTask, AgentResult
from tools.file_tools import read_file, write_file, list_directory, get_file_tree, FILE_TOOLS
from tools.bash_tool import run_command, BASH_TOOLS
from tools.git_tools import create_branch, commit_changes, push_branch, open_pull_request, GIT_TOOLS
from tools.search_tool import search_in_repo, SEARCH_TOOLS
from core.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

# Todos los tools disponibles para el agente
ALL_TOOLS = FILE_TOOLS + BASH_TOOLS + GIT_TOOLS + SEARCH_TOOLS

# Máximo de iteraciones del agente (evitar loops infinitos)
MAX_ITERATIONS = 50

SYSTEM_PROMPT = """Eres un agente de software autónomo. Tu trabajo es implementar la tarea asignada en el repositorio de código.

## Reglas fundamentales

1. **Nunca hagas push directo a main/master.** Siempre crea un branch con `create_branch` antes de hacer cambios.
2. **Commits atómicos.** Haz un commit por cada cambio lógico, no uno gigante al final.
3. **Mensajes de commit en inglés**, formato Conventional Commits: `type(scope): descripción`.
4. **No introduzcas dependencias nuevas** sin mencionarlo en el resumen final.
5. **No rompas tests existentes.** Corre los tests antes de terminar.
6. **Si la tarea es ambigua**, implementa la opción más conservadora y documéntalo.
7. **Nunca escribas secretos o API keys** en el código.

## Flujo de trabajo esperado

1. Usa `get_file_tree` para entender la estructura del proyecto.
2. Lee los archivos relevantes con `read_file`.
3. Crea el branch con `create_branch`.
4. Implementa los cambios con `write_file`.
5. Haz commits incrementales con `commit_changes`.
6. Corre tests con `run_command` si hay comando configurado.
7. Haz push con `push_branch`.
8. Responde con un resumen de lo que hiciste.

## Formato del resumen final

Al terminar, responde con un JSON así:
```json
{
  "branch_name": "feat/task-42-jwt-auth",
  "summary": "Descripción de los cambios implementados",
  "commits": ["lista de mensajes de commit"],
  "tests_passed": true
}
```
"""


class ClaudeAgent(BaseAgent):
    def __init__(self, model: str | None = None):
        self.model = model or settings.default_agent
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    @property
    def name(self) -> str:
        return self.model

    async def execute(self, task: AgentTask) -> AgentResult:
        log = structlog.get_logger().bind(task_id=task.task_id, agent=self.name)
        log.info("Iniciando ejecución de tarea", description=task.description)

        branch_name = self._build_branch_name(task.task_id, task.description)
        messages = [
            {
                "role": "user",
                "content": (
                    f"Tarea #{task.task_id}: {task.description}\n\n"
                    f"Repositorio: {task.repo_path}\n"
                    f"Branch a crear: {branch_name}\n"
                    f"Branch base: {task.base_branch}\n"
                    f"Comando de tests: {task.test_command or 'No configurado'}\n\n"
                    "Implementa la tarea siguiendo las instrucciones del sistema."
                ),
            }
        ]

        full_log = []
        iterations = 0

        try:
            while iterations < MAX_ITERATIONS:
                iterations += 1
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=8096,
                    system=SYSTEM_PROMPT,
                    tools=ALL_TOOLS,
                    messages=messages,
                )

                # Agregar respuesta del asistente al historial
                messages.append({"role": "assistant", "content": response.content})

                # Si el agente terminó (stop_reason = end_turn), extraer resultado
                if response.stop_reason == "end_turn":
                    final_text = " ".join(
                        block.text for block in response.content if hasattr(block, "text")
                    )
                    full_log.append(f"[Agente terminó]\n{final_text}")
                    result = self._parse_final_response(final_text, branch_name)
                    result.log = "\n".join(full_log)
                    log.info("Tarea completada", pr_url=result.pr_url)
                    return result

                # Procesar tool calls
                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    tool_name = block.name
                    tool_input = block.input
                    log.info("Ejecutando tool", tool=tool_name, input=tool_input)

                    result_content = self._execute_tool(tool_name, tool_input, task)
                    full_log.append(f"[Tool: {tool_name}]\nInput: {json.dumps(tool_input)}\nOutput: {json.dumps(result_content)}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result_content),
                    })

                # Enviar resultados de tools de vuelta al agente
                messages.append({"role": "user", "content": tool_results})

            # Si llegamos aquí, el agente superó el límite de iteraciones
            return AgentResult(
                success=False,
                branch_name=branch_name,
                log="\n".join(full_log),
                error=f"El agente superó el límite de {MAX_ITERATIONS} iteraciones.",
            )

        except Exception as e:
            log.error("Error en ejecución del agente", error=str(e))
            return AgentResult(
                success=False,
                branch_name=branch_name,
                log="\n".join(full_log),
                error=str(e),
            )

    def _execute_tool(self, tool_name: str, tool_input: dict, task: AgentTask) -> dict:
        """Despacha la llamada al tool correcto."""
        repo = task.repo_path

        match tool_name:
            # File tools
            case "read_file":
                return read_file(repo, tool_input["file_path"])
            case "write_file":
                return write_file(repo, tool_input["file_path"], tool_input["content"])
            case "list_directory":
                return list_directory(repo, tool_input.get("dir_path", "."))
            case "get_file_tree":
                return get_file_tree(repo, tool_input.get("max_depth", 3))
            # Bash tool
            case "run_command":
                return run_command(repo, tool_input["command"], tool_input.get("timeout", 120))
            # Git tools
            case "create_branch":
                return create_branch(repo, tool_input["branch_name"])
            case "commit_changes":
                return commit_changes(repo, tool_input["message"])
            case "push_branch":
                return push_branch(repo, tool_input["branch_name"])
            # Search tool
            case "search_in_repo":
                return search_in_repo(repo, tool_input["pattern"], tool_input.get("file_glob", "*"))
            case _:
                return {"error": f"Tool desconocido: {tool_name}"}

    def _parse_final_response(self, text: str, fallback_branch: str) -> AgentResult:
        """Intenta parsear el JSON de respuesta final del agente."""
        import re
        try:
            match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                return AgentResult(
                    success=True,
                    branch_name=data.get("branch_name", fallback_branch),
                    log=data.get("summary", text),
                )
        except (json.JSONDecodeError, AttributeError):
            pass

        # Si no hay JSON válido, devolver éxito con el texto como log
        return AgentResult(success=True, branch_name=fallback_branch, log=text)
