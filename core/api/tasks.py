"""
Endpoints para gestión de tareas.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.models.task import Task, TaskStatus, TaskPriority

router = APIRouter()


class TaskCreate(BaseModel):
    project_id: int
    description: str
    priority: TaskPriority = TaskPriority.NORMAL
    agent: str | None = None


class TaskResponse(BaseModel):
    id: int
    project_id: int
    description: str
    status: TaskStatus
    priority: TaskPriority
    agent: str | None
    branch_name: str | None
    pr_url: str | None
    pr_number: int | None
    error_message: str | None
    agent_log: str | None

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[TaskResponse])
def list_tasks(limit: int = 20, db: Session = Depends(get_db)):
    return db.query(Task).order_by(Task.created_at.desc()).limit(limit).all()


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task no encontrada")
    return task


@router.post("/", response_model=TaskResponse, status_code=201)
def create_task(body: TaskCreate, db: Session = Depends(get_db)):
    task = Task(**body.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    from core.queue.worker import enqueue_task
    enqueue_task(task.id)
    return task


@router.delete("/{task_id}", status_code=204)
def cancel_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task no encontrada")
    if task.status == TaskStatus.IN_PROGRESS:
        raise HTTPException(status_code=409, detail="No se puede cancelar una tarea en progreso")
    task.status = TaskStatus.CANCELLED
    db.commit()
