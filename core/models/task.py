import enum
from datetime import datetime
from sqlalchemy import String, Text, Enum, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base


class TaskStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    PR_OPEN = "PR_OPEN"
    DONE = "DONE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)

    # Instrucción original del usuario
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Estado
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.QUEUED, nullable=False
    )
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority), default=TaskPriority.NORMAL, nullable=False
    )

    # Agente asignado
    agent: Mapped[str | None] = mapped_column(String(50))

    # Git
    branch_name: Mapped[str | None] = mapped_column(String(200))
    pr_url: Mapped[str | None] = mapped_column(String(500))
    pr_number: Mapped[int | None] = mapped_column()

    # Logs / resultado
    agent_log: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Relación
    project: Mapped["Project"] = relationship("Project", back_populates="tasks")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Task #{self.id} [{self.status}] {self.description[:40]}>"
