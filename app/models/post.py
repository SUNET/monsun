import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid


class FeedType(str, enum.Enum):
    social = "social"
    news = "news"


class InteractionType(str, enum.Enum):
    like = "like"
    repost = "repost"


class Post(Base, TimestampMixin):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    exercise_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exercises.id"), index=True)
    persona_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("personas.id"))
    author_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    feed_type: Mapped[FeedType] = mapped_column(Enum(FeedType), default=FeedType.social)
    content: Mapped[str] = mapped_column(Text)
    headline: Mapped[str | None] = mapped_column(String(500))
    article_body: Mapped[str | None] = mapped_column(Text)
    parent_post_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("posts.id"))
    repost_of_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("posts.id"))
    is_scheduled: Mapped[bool] = mapped_column(Boolean, default=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    is_inject: Mapped[bool] = mapped_column(Boolean, default=False)
    image_url: Mapped[str | None] = mapped_column(String(500))
    sort_order: Mapped[int | None] = mapped_column(default=None)

    persona: Mapped["Persona | None"] = relationship()
    author: Mapped["User"] = relationship(foreign_keys=[author_user_id])
    interactions: Mapped[list["PostInteraction"]] = relationship(back_populates="post")
    replies: Mapped[list["Post"]] = relationship(
        foreign_keys=[parent_post_id],
        remote_side=[id],
        viewonly=True,
    )


class PostInteraction(Base):
    __tablename__ = "post_interactions"
    __table_args__ = (UniqueConstraint("post_id", "user_id", "interaction"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("posts.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    interaction: Mapped[InteractionType] = mapped_column(Enum(InteractionType))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )

    post: Mapped["Post"] = relationship(back_populates="interactions")
