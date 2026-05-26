"""
Agente genérico via LiteLLM — soporta GPT-4o, Gemini y cualquier modelo compatible.
Usa el formato OpenAI de tool use (function calling).
"""

import json
import structlog
import litellm

from agents.base_agent import BaseAgent, AgentTask, AgentResult
from tools.file_tools import read_file, write_file, list_directory, get_file_tree
from tools.bash_tool import run_command
from tools.git_tools import create_branch, commit_changes, push_branch
from tools.search_tool import search_in_repo
from core.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

MAX_ITERATIONS = 50

# Tools en formato OpenAI (function calling)
OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Lee el contenido de un archivo del repositorio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Ruta relativa al archivo."}
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Escribe o sobreescribe un archivo en el repositorio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Ruta relativa al archivo."},
                    "content": {"type": "string", "description": "Contenido completo del archivo."},
                },
                "required": ["file_path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "Lista archivos y carpetas en un directorio del repositorio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dir_path": {"type": "string", "description": "Ruta relativa al directorio. Usa '.' para la raíz.", "default": "."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_tree",
            "description": "Devuelve el árbol de archivos del repositorio. Úsalo al inicio para entender la estructura.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_depth": {"type": "integer", "description": "Profundidad máxima del árbol.", "default": 3}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Ejecuta un comando shell en el repositorio. Útil para tests, linters y operaciones git.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Comando a ejecutar."},
                    "timeout": {"type": "integer", "description": "Timeout en segundos.", "default": 120},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_branch",
            "description": "Crea un nuevo branch en el repositorio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "branch_name": {"type": "string", "description": "Nombre del branch. Formato: feat/task-{id}-{descripcion}."}
                },
                "required": ["branch_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "commit_changes",
            "description": "Hace stage de todos los cambios y crea un commit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Mensaje de commit en formato Conventional Commits."}
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "push_branch",
            "description": "Hace push del branch al repositorio remoto en GitHub.",
            "parameters": {
                "type": "object",
                "properties": {
                    "branch_name": {"type": "string", "description": "Nombre del branch a hacer push."}
                },
                "required": ["branch_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_repo",
            "description": "Busca un patrón de texto en los archivos del repositorio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Patrón a buscar (regex o texto literal)."},
                    "file_glob": {"type": "string", "description": "Glob para filtrar archivos. Ejemplo: '*.py'", "default": "*"},
                },
                "required": ["pattern"],
            },
        },
    },
]

SYSTEM_PROMPT = """Eres un agente de software autónomo. Tu trabajo es implementar la tarea asignada en el repositorio de código.

## Reglas fundamentales

1. **Nunca hagas push directo a main/master.** Siempre crea un branch con `create_branch` antes de hacer cambios.
2. **Commits atómicos.** Haz un commit por cada cambio lógico.
3. **Mensajes de commit en inglés**, formato Conventional Commits: `type(scope): descripción`.
4. **No introduzcas dependencias nuevas** sin mencionarlo en el resumen final.
5. **No rompas tests existentes.** Corre los tests antes de terminar.
6. **Si la tarea es ambigua**, implementa la opción más conservadora y documéntalo.
7. **Nunca escribas secretos o API keys** en el código.
8. **Nunca ejecutes `env`, `printenv` ni comandos que listen variables de entorno.**

## Flujo de trabajo esperado

1. Usa `get_file_tree` para entender la estructura del proyecto.
2. Lee los archivos relevantes con `read_file`.
3. Crea el branch con `create_branch`.
4. Implementa los cambios con `write_file`.
5. Haz commits incrementales con `commit_changes`.
6. Corre tests con `run_command` si hay comando configurado.
7. Haz push con `push_branch`.
8. Responde con un JSON de resumen.

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


class LiteLLMAgent(BaseAgent):
    def __init__(self, model: str):
        self.model = model
        # Configurar API keys
        litellm.openai_key = settings.openai_api_key or None
        litellm.google_key = settings.google_ai_api_key or None

    @property
    def name(self) -> str:
        return self.model

    async def execute(self, task: AgentTask) -> AgentResult:
        log = structlog.get_logger().bind(task_id=task.task_id, agent=self.model)
        log.info("Iniciando ejecución LiteLLM", description=task.description)

        if task.existing_branch:
            branch_name = task.existing_branch
            branch_instruction = (
                f"Branch existente a usar: `{branch_name}` — "
                f"NO crees un branch nuevo. Haz checkout con: git checkout {branch_name}"
            )
        else:
            branch_name = self._build_branch_name(task.task_id, task.description)
            branch_instruction = f"Branch a crear: `{branch_name}` — usa `create_branch`."

        context_section = ""
        if task.project_context:
            context_section = f"\n## Contexto del proyecto\n\n{task.project_context}\n"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Tarea #{task.task_id}: {task.description}\n\n"
                    f"Repositorio: {task.repo_path}\n"
                    f"{branch_instruction}\n"
                    f"Branch base: {task.base_branch}\n"
                    f"Comando de tests: {task.test_command or 'No configurado'}\n"
                    f"{context_section}\n"
                    "Implementa la tarea siguiendo las instrucciones del sistema."
                ),
            },
        ]

        full_log = []
        iterations = 0

        try:
            while iterations < MAX_ITERATIONS:
                iterations += 1

                response = await litellm.acompletion(
                    model=self.model,
                    messages=messages,
                    tools=OPENAI_TOOLS,
                    tool_choice="auto",
                    max_tokens=4096,
                )

                message = response.choices[0].message
                messages.append(message.model_dump())

                # Sin tool calls — el agente terminó
                if not message.tool_calls:
                    final_text = message.content or ""
                    full_log.append(f"[Agente terminó]\n{final_text}")
                    result = self._parse_final_response(final_text, branch_name)
                    result.log = self._sanitize_log("\n".join(full_log))
                    return result

                # Ejecutar tool calls
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        tool_input = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        tool_input = {}

                    log.info("Ejecutando tool", tool=tool_name)
                    result_content = self._execute_tool(tool_name, tool_input, task)
                    full_log.append(f"[Tool: {tool_name}]\nInput: {json.dumps(tool_input)}\nOutput: {json.dumps(result_content)}")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result_content),
                    })

            return AgentResult(
                success=False,
                branch_name=branch_name,
                log="\n".join(full_log),
                error=f"El agente superó el límite de {MAX_ITERATIONS} iteraciones.",
            )

        except Exception as e:
            log.error("Error en ejecución LiteLLM", error=str(e))
            return AgentResult(
                success=False,
                branch_name=branch_name,
                log="\n".join(full_log),
                error=str(e),
            )

    def _execute_tool(self, tool_name: str, tool_input: dict, task: AgentTask) -> dict:
        repo = task.repo_path
        match tool_name:
            case "read_file":
                return read_file(repo, tool_input["file_path"])
            case "write_file":
                return write_file(repo, tool_input["file_path"], tool_input["content"])
            case "list_directory":
                return list_directory(repo, tool_input.get("dir_path", "."))
            case "get_file_tree":
                return get_file_tree(repo, tool_input.get("max_depth", 3))
            case "run_command":
                return run_command(repo, tool_input["command"], tool_input.get("timeout", 120))
            case "create_branch":
                return create_branch(repo, tool_input["branch_name"])
            case "commit_changes":
                return commit_changes(repo, tool_input["message"])
            case "push_branch":
                return push_branch(repo, tool_input["branch_name"])
            case "search_in_repo":
                return search_in_repo(repo, tool_input["pattern"], tool_input.get("file_glob", "*"))
            case _:
                return {"error": f"Tool desconocido: {tool_name}"}

    def _parse_final_response(self, text: str, fallback_branch: str) -> AgentResult:
        import re
        try:
            match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                summary = self._build_pr_summary(data)
                return AgentResult(
                    success=True,
                    branch_name=data.get("branch_name", fallback_branch),
                    summary=summary,
                    log=text,
                )
        except (json.JSONDecodeError, AttributeError):
            pass
        return AgentResult(success=True, branch_name=fallback_branch, summary=text, log=text)

    def _build_pr_summary(self, data: dict) -> str:
        lines = []
        summary = data.get("summary", "")
        if summary:
            lines.append(f"## ¿Qué se hizo?\n\n{summary}\n")
        commits = data.get("commits", [])
        if commits:
            lines.append("## Commits\n")
            for c in commits:
                lines.append(f"- `{c}`")
            lines.append("")
        tests_passed = data.get("tests_passed")
        if tests_passed is not None:
            status = "✅ Tests pasaron" if tests_passed else "❌ Tests fallaron"
            lines.append(f"## Tests\n\n{status}\n")
        return "\n".join(lines)

    def _sanitize_log(self, log: str) -> str:
        import re
        patterns = [
            (r"(GITHUB_TOKEN=)[^\s\n]+", r"\1[REDACTED]"),
            (r"(ANTHROPIC_API_KEY=)[^\s\n]+", r"\1[REDACTED]"),
            (r"(OPENAI_API_KEY=)[^\s\n]+", r"\1[REDACTED]"),
            (r"(TELEGRAM_BOT_TOKEN=)[^\s\n]+", r"\1[REDACTED]"),
            (r"(SECRET_KEY=)[^\s\n]+", r"\1[REDACTED]"),
            (r"(DATABASE_URL=)[^\s\n]+", r"\1[REDACTED]"),
        ]
        for pattern, replacement in patterns:
            log = re.sub(pattern, replacement, log)
        return log
