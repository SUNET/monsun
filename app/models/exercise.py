import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid


class ExerciseState(str, enum.Enum):
    draft = "draft"
    ready = "ready"
    live = "live"
    ended = "ended"
    archived = "archived"


class MemberRole(str, enum.Enum):
    admin = "admin"
    participant = "participant"


class Exercise(Base, TimestampMixin):
    __tablename__ = "exercises"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    state: Mapped[ExerciseState] = mapped_column(
        Enum(ExerciseState), default=ExerciseState.draft
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cloned_from_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("exercises.id")
    )

    members: Mapped[list["ExerciseMembership"]] = relationship(back_populates="exercise")
    personas: Mapped[list["Persona"]] = relationship("Persona", back_populates="exercise")


class ExerciseMembership(Base):
    __tablename__ = "exercise_memberships"
    __table_args__ = (UniqueConstraint("exercise_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    exercise_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exercises.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    role: Mapped[MemberRole] = mapped_column(
        Enum(MemberRole), default=MemberRole.participant
    )

    exercise: Mapped["Exercise"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship()
