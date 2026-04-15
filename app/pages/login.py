from nicegui import app, ui

from app.database import async_session
from app.pages.layout import BRAND_COLOR, apply_theme
from app.services.auth import authenticate_user


def login_page():
    @ui.page("/login")
    async def login():
        apply_theme()

        async def try_login():
            async with async_session() as session:
                user = await authenticate_user(
                    session, username.value, password.value
                )
            if user:
                app.storage.user["user_id"] = str(user.id)
                app.storage.user["username"] = user.username
                app.storage.user["display_name"] = user.display_name
                app.storage.user["role"] = user.role.value
                ui.navigate.to("/")
            else:
                ui.notify("Invalid username or password", type="negative")

        with ui.column().classes("absolute-center items-center gap-6"):
            with ui.row().classes("items-center gap-3 mb-2"):
                ui.image("/static/sunet-logo.svg").classes("w-10")
                ui.label("Monsun").classes("text-3xl font-bold").style(f"color: {BRAND_COLOR}")
            ui.label("Media Simulator").classes("text-sm text-gray-500 -mt-4")

            with ui.card().classes("w-96 p-6"):
                ui.label("Sign in").classes("text-xl font-bold text-gray-800 mb-2")
                username = ui.input("Username").props("outlined").classes("w-full")
                password = ui.input("Password", password=True, password_toggle_button=True).props(
                    "outlined"
                ).classes("w-full")
                password.on("keydown.enter", try_login)
                ui.button("Log in", on_click=try_login).props(
                    "unelevated no-caps"
                ).classes("w-full mt-2").style("height: 44px; font-size: 15px")
