import os
import uuid

from nicegui import app, events, ui
from sqlalchemy import select

from app.config import settings, validate_upload_extension
from app.database import async_session
from app.models import User
from app.pages.layout import nav_header


def profile_page():
    @ui.page("/profile")
    async def profile():
        user_id = app.storage.user.get("user_id")
        if not user_id:
            return ui.navigate.to("/login")
        await nav_header()

        # --- State ---
        # None  = unchanged, ""  = remove, "/media/..." = new/current value
        avatar_path = [None]

        async def handle_avatar_upload(e: events.UploadEventArguments):
            ext = validate_upload_extension(e.file.name)
            if not ext:
                ui.notify(
                    "Only image files (jpg, png, gif, webp) are allowed",
                    type="negative",
                )
                return
            filename = f"avatar_{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(settings.media_dir, filename)
            await e.file.save(filepath)
            avatar_path[0] = f"/media/{filename}"
            avatar_preview.set_source(avatar_path[0])
            avatar_preview.set_visibility(True)
            avatar_fallback.set_visibility(False)
            ui.notify("Photo uploaded — save to apply", type="positive")

        def remove_avatar():
            avatar_path[0] = ""  # empty string signals removal
            avatar_preview.set_visibility(False)
            avatar_fallback.set_visibility(True)
            upload.reset()

        async def save():
            async with async_session() as session:
                u = await session.get(User, uuid.UUID(user_id))
                if not u:
                    ui.notify("User not found", type="negative")
                    return
                if avatar_path[0] is not None:
                    u.avatar_url = avatar_path[0] or None
                await session.commit()
                app.storage.user["avatar_url"] = u.avatar_url or ""
            ui.notify("Profile updated", type="positive")
            ui.navigate.to("/profile")

        # --- Load current user ---
        async with async_session() as session:
            current = await session.get(User, uuid.UUID(user_id))
        if not current:
            app.storage.user.clear()
            return ui.navigate.to("/login")

        # --- Layout ---
        with ui.column().classes("w-full max-w-md mx-auto p-6"):
            with ui.column().classes("gap-0 mb-6"):
                ui.label("Profile").classes("text-2xl font-bold text-gray-800")
                ui.label("Manage your profile picture").classes("text-sm text-gray-500")

            with ui.card().classes("w-full p-6"):
                ui.label("Profile picture").classes(
                    "text-sm font-medium text-gray-600 mb-2"
                )
                with ui.row().classes("items-center gap-4 w-full"):
                    avatar_preview = ui.image().classes(
                        "w-20 h-20 rounded-full object-cover"
                    )
                    avatar_fallback = ui.avatar(
                        current.display_name[0].upper(),
                        color="primary",
                        text_color="white",
                        size="xl",
                    )
                    if current.avatar_url:
                        avatar_preview.set_source(current.avatar_url)
                        avatar_preview.set_visibility(True)
                        avatar_fallback.set_visibility(False)
                    else:
                        avatar_preview.set_visibility(False)

                    with ui.column().classes("gap-1"):
                        upload = ui.upload(
                            on_upload=handle_avatar_upload,
                            auto_upload=True,
                            max_files=1,
                            label="Upload photo",
                        ).props('accept="image/*" flat hide-upload-btn').classes(
                            "upload-btn"
                        )
                        ui.button(
                            "Remove", icon="close", on_click=remove_avatar
                        ).props("flat no-caps dense size=sm color=grey")

                with ui.row().classes("justify-end w-full mt-6"):
                    ui.button("Save", on_click=save).props("unelevated no-caps")
