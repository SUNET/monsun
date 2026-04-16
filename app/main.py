import logging
import os
import uuid as _uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from nicegui import app, ui

from app.config import WEAK_SECRETS, settings

logger = logging.getLogger("monsun")

# Warn loudly about weak secrets at import time
if settings.storage_secret in WEAK_SECRETS:
    logger.warning(
        "CLAW_STORAGE_SECRET is set to a weak default (%r). "
        "Set a strong random value before deploying to production.",
        settings.storage_secret,
    )
if settings.secret_key in WEAK_SECRETS:
    logger.warning(
        "CLAW_SECRET_KEY is set to a weak default (%r). "
        "Set a strong random value before deploying to production.",
        settings.secret_key,
    )

os.makedirs(settings.media_dir, exist_ok=True)
app.add_static_files("/media", settings.media_dir)
app.add_static_files("/static", os.path.join(os.path.dirname(os.path.dirname(__file__)), "static"))

# Increase Socket.IO / WebSocket message size limits
# max_http_buffer_size = incoming HTTP long-poll limit
# websocket_max_message_size = WebSocket frame limit (websockets lib default is 1MB)
from nicegui import core
core.sio.eio.max_http_buffer_size = 10 * 1024 * 1024  # 10MB
core.sio.eio.websocket_max_message_size = 10 * 1024 * 1024  # 10MB

# Strip base path prefix so NiceGUI's routes match, but keep root_path for URL generation
if settings.base_path:
    class StripPrefixMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            if request.url.path.startswith(settings.base_path):
                request.scope["path"] = request.url.path[len(settings.base_path):] or "/"
                request.scope["root_path"] = settings.base_path
            return await call_next(request)
    app.add_middleware(StripPrefixMiddleware)

import sqlalchemy
from sqlalchemy import select

from app.database import async_session, engine
from app.models import Base, ExerciseMembership, Exercise, ExerciseState
from app.pages.exercise_detail import exercise_detail_page
from app.pages.exercises import exercises_page
from app.pages.feed import feed_page
from app.pages.login import login_page
from app.pages.users import users_page
from app.services.auth import create_default_admin


async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Fix: persona_id must be nullable so participants can post without a persona
        await conn.execute(
            sqlalchemy.text("ALTER TABLE posts ALTER COLUMN persona_id DROP NOT NULL")
        )
        # Add sort_order column for scenario flow ordering
        await conn.execute(
            sqlalchemy.text(
                "ALTER TABLE posts ADD COLUMN IF NOT EXISTS sort_order INTEGER"
            )
        )
        # Add avatar_url column for user avatars
        await conn.execute(
            sqlalchemy.text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500)"
            )
        )
    async with async_session() as session:
        await create_default_admin(session)


app.on_startup(startup)


# Auth middleware — participants go straight to their live feed
@ui.page("/")
async def index():
    user_id = app.storage.user.get("user_id")
    if not user_id:
        return ui.navigate.to("/login")

    role = app.storage.user.get("role", "")
    if role in ("superadmin", "admin"):
        return ui.navigate.to("/exercises")

    # Participant: find their live (or ready) exercise and go to the feed
    import uuid
    async with async_session() as session:
        result = await session.execute(
            select(Exercise)
            .join(ExerciseMembership)
            .where(
                ExerciseMembership.user_id == uuid.UUID(user_id),
                Exercise.state.in_([ExerciseState.live, ExerciseState.ready, ExerciseState.draft]),
            )
            .order_by(Exercise.updated_at.desc())
            .limit(1)
        )
        exercise = result.scalar_one_or_none()

    if exercise:
        return ui.navigate.to(f"/feed/{exercise.id}")
    return ui.navigate.to("/exercises")


# Register all pages
login_page()
exercises_page()
exercise_detail_page()
feed_page()
users_page()

ui.run(
    title="Monsun — Media Simulator",
    storage_secret=settings.storage_secret,
    host="0.0.0.0",
    port=8081,
)
