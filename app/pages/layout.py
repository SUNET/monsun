import uuid

from nicegui import app, ui
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models import (
    Exercise,
    ExerciseMembership,
    ExerciseState,
    FeedType,
    Post,
    User,
)

BRAND_COLOR = "#CA402B"


async def refresh_role_from_db():
    """Re-read the user's role from the database and update session storage.

    Ensures role demotions take effect without requiring re-login.
    Returns False if the user no longer exists (session should be cleared).
    """
    uid = app.storage.user.get("user_id")
    if not uid:
        return False
    async with async_session() as session:
        user = await session.get(User, uuid.UUID(uid))
    if not user:
        app.storage.user.clear()
        return False
    app.storage.user["role"] = user.role.value
    app.storage.user["display_name"] = user.display_name
    app.storage.user["username"] = user.username
    return True


def apply_theme():
    ui.add_head_html('<link rel="stylesheet" href="/static/theme.css">')
    ui.add_head_html('<link rel="icon" type="image/png" href="/static/favicon.png">')
    ui.colors(primary=BRAND_COLOR, accent="#7209b7")


async def _find_active_exercise(user_id: str, role: str) -> str | None:
    async with async_session() as session:
        if role in ("superadmin", "admin"):
            result = await session.execute(
                select(Exercise)
                .where(Exercise.state.in_([ExerciseState.live, ExerciseState.ready, ExerciseState.draft]))
                .order_by(Exercise.updated_at.desc())
                .limit(1)
            )
        else:
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
    return str(exercise.id) if exercise else None


async def nav_header():
    apply_theme()
    user_id = app.storage.user.get("user_id")
    if not user_id:
        return

    # Re-verify role from DB on every page load
    if not await refresh_role_from_db():
        ui.navigate.to("/login")
        return

    role = app.storage.user.get("role", "")
    is_admin = role in ("superadmin", "admin")

    async def go_to_feed():
        ex_id = await _find_active_exercise(user_id, role)
        if ex_id:
            ui.navigate.to(f"/feed/{ex_id}")
        else:
            ui.notify("No active exercise found", type="warning")

    # --- Search ---
    async def do_search():
        query = search_input.value.strip()
        search_results.clear()

        if len(query) < 2:
            with search_results:
                ui.label("Type at least 2 characters to search").classes(
                    "text-gray-400 text-sm py-4 text-center"
                )
            return

        pattern = f"%{query}%"

        async with async_session() as session:
            # Search posts the user can see
            post_query = (
                select(Post)
                .options(selectinload(Post.persona))
                .where(
                    Post.is_published == True,
                    Post.parent_post_id == None,
                    or_(
                        Post.content.ilike(pattern),
                        Post.headline.ilike(pattern),
                    ),
                )
                .order_by(Post.published_at.desc())
                .limit(10)
            )
            if not is_admin:
                post_query = post_query.join(
                    ExerciseMembership,
                    ExerciseMembership.exercise_id == Post.exercise_id,
                ).where(ExerciseMembership.user_id == uuid.UUID(user_id))

            result = await session.execute(post_query)
            posts = result.scalars().all()

            users = []
            exercises = []
            if is_admin:
                # Search users
                result = await session.execute(
                    select(User)
                    .where(
                        or_(
                            User.username.ilike(pattern),
                            User.display_name.ilike(pattern),
                        )
                    )
                    .order_by(User.display_name)
                    .limit(5)
                )
                users = result.scalars().all()

                # Search exercises
                result = await session.execute(
                    select(Exercise)
                    .where(
                        or_(
                            Exercise.name.ilike(pattern),
                            Exercise.description.ilike(pattern),
                        )
                    )
                    .order_by(Exercise.updated_at.desc())
                    .limit(5)
                )
                exercises = result.scalars().all()

        with search_results:
            found = False

            if users:
                found = True
                ui.label("Users").classes("text-xs font-semibold text-gray-400 uppercase tracking-wide mt-2 mb-1")
                for u in users:
                    with ui.row().classes(
                        "items-center gap-3 w-full py-2 px-3 rounded-lg cursor-pointer hover:bg-gray-100"
                    ).on("click", lambda _, uid=u.id: (
                        search_dialog.close(),
                        ui.navigate.to("/users"),
                    )):
                        ui.avatar(u.display_name[0].upper(), color="primary", text_color="white", size="xs")
                        with ui.column().classes("gap-0"):
                            ui.label(u.display_name).classes("text-sm font-medium text-gray-800")
                            ui.label(f"@{u.username}").classes("text-xs text-gray-500")
                        ui.badge(u.role.value).classes("ml-auto").props("dense")

            if exercises:
                found = True
                ui.label("Exercises").classes("text-xs font-semibold text-gray-400 uppercase tracking-wide mt-3 mb-1")
                for ex in exercises:
                    state_color = {
                        "draft": "gray", "ready": "blue", "live": "green",
                        "ended": "orange", "archived": "red",
                    }.get(ex.state.value, "gray")
                    with ui.row().classes(
                        "items-center gap-3 w-full py-2 px-3 rounded-lg cursor-pointer hover:bg-gray-100"
                    ).on("click", lambda _, eid=ex.id: (
                        search_dialog.close(),
                        ui.navigate.to(f"/exercise/{eid}"),
                    )):
                        ui.icon("assignment", size="xs").classes("text-gray-500")
                        ui.label(ex.name).classes("text-sm font-medium text-gray-800 flex-1")
                        ui.badge(ex.state.value, color=state_color).props("dense")

            social_posts = [p for p in posts if p.feed_type == FeedType.social]
            news_posts = [p for p in posts if p.feed_type == FeedType.news]

            if social_posts:
                found = True
                ui.label("Social Posts").classes("text-xs font-semibold text-gray-400 uppercase tracking-wide mt-3 mb-1")
                for p in social_posts:
                    handle = f"@{p.persona.handle}" if p.persona else ""
                    preview = (p.content or "")[:100]
                    with ui.row().classes(
                        "items-center gap-3 w-full py-2 px-3 rounded-lg cursor-pointer hover:bg-gray-100"
                    ).on("click", lambda _, eid=p.exercise_id: (
                        search_dialog.close(),
                        ui.navigate.to(f"/feed/{eid}"),
                    )):
                        ui.icon("tag", size="xs").classes("text-orange-500")
                        with ui.column().classes("gap-0 flex-1 min-w-0"):
                            if handle:
                                ui.label(handle).classes("text-xs text-gray-500")
                            ui.label(preview).classes("text-sm text-gray-700 truncate")

            if news_posts:
                found = True
                ui.label("News Articles").classes("text-xs font-semibold text-gray-400 uppercase tracking-wide mt-3 mb-1")
                for p in news_posts:
                    source = f"@{p.persona.handle}" if p.persona else ""
                    with ui.row().classes(
                        "items-center gap-3 w-full py-2 px-3 rounded-lg cursor-pointer hover:bg-gray-100"
                    ).on("click", lambda _, eid=p.exercise_id: (
                        search_dialog.close(),
                        ui.navigate.to(f"/feed/{eid}"),
                    )):
                        ui.icon("newspaper", size="xs").classes("text-red-500")
                        with ui.column().classes("gap-0 flex-1 min-w-0"):
                            ui.label(p.headline or "").classes("text-sm font-medium text-gray-800 truncate")
                            if source:
                                ui.label(source).classes("text-xs text-gray-500")

            if not found:
                with ui.column().classes("items-center py-6 w-full"):
                    ui.icon("search_off", size="md").classes("text-gray-300")
                    ui.label("No results found").classes("text-gray-400 text-sm mt-1")

    # Search dialog
    with ui.dialog() as search_dialog:
        with ui.card().classes("w-full max-w-lg").style("min-height: 200px"):
            with ui.row().classes("items-center gap-2 w-full"):
                ui.icon("search", size="sm").classes("text-gray-400")
                search_input = ui.input(
                    placeholder="Search posts, articles" + (", users, exercises..." if is_admin else "..."),
                ).props("outlined dense autofocus").classes("flex-1").on(
                    "keydown.enter", do_search
                )
                ui.button("Search", on_click=do_search).props("unelevated no-caps dense")
            search_results = ui.column().classes("w-full mt-2 max-h-96 overflow-y-auto")
            with search_results:
                ui.label("Type at least 2 characters to search").classes(
                    "text-gray-400 text-sm py-4 text-center"
                )

    # --- Header ---
    with ui.header().classes("items-center justify-between px-6 py-2").style(
        f"background: white; border-bottom: 3px solid {BRAND_COLOR}"
    ):
        with ui.row().classes("items-center gap-3 cursor-pointer").on(
            "click", go_to_feed if not is_admin else lambda: ui.navigate.to("/exercises")
        ):
            ui.image("/static/sunet-logo.svg").classes("w-6")
            ui.label("Monsun").classes("text-xl font-bold").style(
                f"color: {BRAND_COLOR}"
            )

        with ui.row().classes("items-center gap-1"):
            ui.button(icon="search", on_click=search_dialog.open).props(
                "flat round"
            ).style(f"color: {BRAND_COLOR}")
            if is_admin:
                ui.button("Feed", icon="dynamic_feed", on_click=go_to_feed).props(
                    "flat unelevated no-caps"
                ).style(f"color: {BRAND_COLOR}")
            if role == "superadmin":
                ui.button("Users", icon="people", on_click=lambda: ui.navigate.to("/users")).props(
                    "flat unelevated no-caps"
                ).style(f"color: {BRAND_COLOR}")
            if is_admin:
                ui.button("Exercises", icon="assignment", on_click=lambda: ui.navigate.to("/exercises")).props(
                    "flat unelevated no-caps"
                ).style(f"color: {BRAND_COLOR}")
            display = app.storage.user.get("display_name", "")
            if display:
                ui.separator().props("vertical").classes("mx-2 h-6")
                ui.label(display).classes("text-sm font-medium text-gray-600")
            ui.button(
                "Logout", icon="logout",
                on_click=lambda: (app.storage.user.clear(), ui.navigate.to("/login")),
            ).props("flat unelevated no-caps").classes("text-gray-500")
