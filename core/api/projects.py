"""
Endpoints para gestión de proyectos.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.models.project import Project

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    repo_url: str
    description: str | None = None
    base_branch: str = "main"
    default_agent: str = "claude-opus-4"
    fallback_agent: str = "claude-sonnet-4"
    test_command: str | None = None
    lint_command: str | None = None
    format_command: str | None = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    repo_url: str
    description: str | None
    base_branch: str
    default_agent: str
    fallback_agent: str
    test_command: str | None
    lint_command: str | None
    is_active: bool

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).filter(Project.is_active == True).all()


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return project


@router.post("/", response_model=ProjectResponse, status_code=201)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    existing = db.query(Project).filter(Project.name == body.name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Ya existe un proyecto con nombre '{body.name}'")
    project = Project(**body.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
def deactivate_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    project.is_active = False
    db.commit()
