import uuid

from nicegui import app, ui
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models import Exercise, ExerciseMembership, ExerciseState
from app.pages.layout import nav_header

STATE_STYLES = {
    "draft": ("gray", "draft_orders"),
    "ready": ("blue", "check_circle_outline"),
    "live": ("green", "circle"),
    "ended": ("orange", "stop_circle"),
    "archived": ("red", "archive"),
}


def exercises_page():
    @ui.page("/exercises")
    async def exercises():
        user_id = app.storage.user.get("user_id")
        if not user_id:
            return ui.navigate.to("/login")
        await nav_header()
        role = app.storage.user.get("role")
        is_admin = role in ("superadmin", "admin")

        async def load_exercises():
            exercise_list.clear()
            async with async_session() as session:
                if role == "superadmin":
                    result = await session.execute(
                        select(Exercise).order_by(Exercise.created_at.desc())
                    )
                else:
                    result = await session.execute(
                        select(Exercise)
                        .join(ExerciseMembership)
                        .where(ExerciseMembership.user_id == uuid.UUID(user_id))
                        .order_by(Exercise.created_at.desc())
                    )
                exs = result.scalars().all()

            with exercise_list:
                if not exs:
                    with ui.column().classes("items-center py-16 w-full"):
                        ui.icon("folder_open", size="xl").classes("text-gray-300")
                        ui.label(
                            "No exercises yet" if is_admin else "You haven't been added to any exercises yet"
                        ).classes("text-gray-400 text-lg mt-2")
                    return

                # Participants with exactly one active exercise go straight to it
                if not is_admin:
                    active = [
                        ex for ex in exs
                        if ex.state in (ExerciseState.live, ExerciseState.ready)
                    ]
                    if len(active) == 1:
                        ui.navigate.to(f"/feed/{active[0].id}")
                        return

                for ex in exs:
                    state_color, state_icon = STATE_STYLES.get(ex.state.value, ("gray", "circle"))

                    if is_admin:
                        # Admin view — full detail, click to exercise management
                        target = f"/exercise/{ex.id}"
                    else:
                        # Participant view — click straight to feed
                        target = f"/feed/{ex.id}"

                    with ui.card().classes("w-full cursor-pointer transition-shadow").on(
                        "click", lambda _, t=target: ui.navigate.to(t)
                    ):
                        with ui.row().classes("items-center justify-between w-full p-1"):
                            with ui.row().classes("items-center gap-3"):
                                ui.icon(state_icon, size="sm").classes(f"text-{state_color}-500")
                                with ui.column().classes("gap-0"):
                                    ui.label(ex.name).classes("text-base font-semibold text-gray-800")
                                    if is_admin and ex.description:
                                        ui.label(ex.description).classes("text-gray-500 text-sm")
                                    elif not is_admin and ex.state == ExerciseState.live:
                                        ui.label("Tap to open feed").classes("text-gray-400 text-sm")
                            ui.badge(ex.state.value, color=state_color)

        async def create_exercise():
            if not name_input.value.strip():
                ui.notify("Name is required", type="warning")
                return
            async with async_session() as session:
                ex = Exercise(
                    name=name_input.value.strip(),
                    description=desc_input.value.strip(),
                )
                session.add(ex)
                await session.commit()
            name_input.value = ""
            desc_input.value = ""
            dialog.close()
            await load_exercises()
            ui.notify("Exercise created", type="positive")

        # Layout
        with ui.column().classes("w-full max-w-4xl mx-auto p-6"):
            with ui.row().classes("items-center justify-between w-full mb-6"):
                with ui.column().classes("gap-0"):
                    ui.label("Exercises").classes("text-2xl font-bold text-gray-800")
                    if is_admin:
                        ui.label("Manage your simulation exercises").classes("text-sm text-gray-500")
                    else:
                        ui.label("Your simulation exercises").classes("text-sm text-gray-500")
                if is_admin:
                    ui.button("New Exercise", icon="add", on_click=lambda: dialog.open()).props(
                        "unelevated no-caps"
                    )

            exercise_list = ui.column().classes("w-full gap-3")

            if is_admin:
                with ui.dialog() as dialog:
                    with ui.card().classes("w-96 p-4"):
                        ui.label("Create Exercise").classes("text-lg font-bold text-gray-800 mb-3")
                        name_input = ui.input("Name").props("outlined").classes("w-full")
                        desc_input = ui.textarea("Description").props("outlined").classes("w-full")
                        with ui.row().classes("justify-end w-full mt-3 gap-2"):
                            ui.button("Cancel", on_click=dialog.close).props("flat no-caps")
                            ui.button("Create", on_click=create_exercise).props("unelevated no-caps")

        await load_exercises()
