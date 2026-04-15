import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid


class PersonaType(str, enum.Enum):
    social = "social"
    news = "news"
    both = "both"


class Persona(Base, TimestampMixin):
    __tablename__ = "personas"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    exercise_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exercises.id"))
    handle: Mapped[str] = mapped_column(String(100))
    display_name: Mapped[str] = mapped_column(String(255))
    avatar_url: Mapped[str] = mapped_column(String(500), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    persona_type: Mapped[PersonaType] = mapped_column(
        Enum(PersonaType), default=PersonaType.social
    )

    exercise: Mapped["Exercise"] = relationship(back_populates="personas")
