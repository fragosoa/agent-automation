"""
FastAPI app — punto de entrada principal.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from core.database import init_db
from core.api.tasks import router as tasks_router
from core.api.projects import router as projects_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crear tablas al arrancar si no existen
    init_db()
    yield


app = FastAPI(
    title="Agent Automation API",
    description="Orquestador personal de agentes de IA",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
app.include_router(projects_router, prefix="/projects", tags=["projects"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
