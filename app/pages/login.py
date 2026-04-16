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

        with ui.card().classes("absolute-center w-96 p-6"):
            with ui.column().classes("items-center w-full mb-4"):
                ui.image("/static/sunet-logo.svg").classes("w-12")
                ui.label("Monsun").classes("text-2xl font-bold mt-2").style(f"color: {BRAND_COLOR}")
                username = ui.input("Username").props("outlined").classes("w-full")
                password = ui.input("Password", password=True, password_toggle_button=True).props(
                    "outlined"
                ).classes("w-full")
                password.on("keydown.enter", try_login)
                ui.button("Log in", on_click=try_login).props(
                    "unelevated no-caps"
                ).classes("w-full mt-2").style("height: 44px; font-size: 15px")
