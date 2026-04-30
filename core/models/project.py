from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Identificación
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)

    # Repositorio
    repo_url: Mapped[str] = mapped_column(String(500), nullable=False)
    base_branch: Mapped[str] = mapped_column(String(100), default="main")

    # Agente preferido
    default_agent: Mapped[str] = mapped_column(String(50), default="claude-opus-4")
    fallback_agent: Mapped[str] = mapped_column(String(50), default="claude-sonnet-4")

    # Comandos del proyecto
    test_command: Mapped[str | None] = mapped_column(String(200))
    lint_command: Mapped[str | None] = mapped_column(String(200))
    format_command: Mapped[str | None] = mapped_column(String(200))

    # Estado
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relación
    tasks: Mapped[list["Task"]] = relationship(  # noqa: F821
        "Task", back_populates="project", order_by="Task.created_at.desc()"
    )

    def __repr__(self) -> str:
        return f"<Project {self.name} ({self.repo_url})>"
