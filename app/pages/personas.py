import os
import uuid

from nicegui import app, events, ui
from sqlalchemy import delete as sa_delete, select, update as sa_update

from app.config import settings, validate_upload_extension
from app.database import async_session
from app.models import Persona, PersonaExercise, PersonaType, Post
from app.pages.layout import nav_header


def personas_page():
    @ui.page("/personas")
    async def personas_view():
        user_id = app.storage.user.get("user_id")
        role = app.storage.user.get("role")
        if not user_id or role not in ("superadmin", "admin"):
            return ui.navigate.to("/")
        await nav_header()

        edit_persona_id = [None]
        delete_persona_id = [None]
        create_avatar_path = [None]
        edit_avatar_path = [None]

        async def handle_create_avatar(e: events.UploadEventArguments):
            ext = validate_upload_extension(e.file.name)
            if not ext:
                ui.notify("Only image files (jpg, png, gif, webp) are allowed", type="negative")
                return
            filename = f"avatar_{uuid.uuid4().hex}{ext}"
            await e.file.save(os.path.join(settings.media_dir, filename))
            create_avatar_path[0] = f"/media/{filename}"
            create_avatar_preview.set_source(create_avatar_path[0])
            create_avatar_preview.set_visibility(True)
            ui.notify("Avatar uploaded", type="positive")

        async def handle_edit_avatar(e: events.UploadEventArguments):
            ext = validate_upload_extension(e.file.name)
            if not ext:
                ui.notify("Only image files (jpg, png, gif, webp) are allowed", type="negative")
                return
            filename = f"avatar_{uuid.uuid4().hex}{ext}"
            await e.file.save(os.path.join(settings.media_dir, filename))
            edit_avatar_path[0] = f"/media/{filename}"
            edit_avatar_preview.set_source(edit_avatar_path[0])
            edit_avatar_preview.set_visibility(True)
            ui.notify("Avatar uploaded", type="positive")

        async def load_personas():
            persona_list.clear()
            async with async_session() as session:
                result = await session.execute(
                    select(Persona).order_by(Persona.handle)
                )
                all_personas = result.scalars().all()
            with persona_list:
                if not all_personas:
                    with ui.column().classes("items-center py-16 w-full"):
                        ui.icon("people_outline", size="xl").classes("text-gray-300")
                        ui.label("No personas yet").classes("text-gray-400 text-lg mt-2")
                    return
                for p in all_personas:
                    with ui.row().classes(
                        "items-center gap-4 w-full py-3 px-3 rounded-lg hover:bg-gray-50"
                    ):
                        if p.avatar_url:
                            ui.image(p.avatar_url).classes("w-8 h-8 rounded-full object-cover")
                        else:
                            ui.avatar(
                                p.display_name[0].upper(), color="primary", text_color="white", size="sm"
                            )
                        with ui.column().classes("gap-0 flex-1"):
                            ui.label(p.display_name).classes("font-medium text-gray-800")
                            ui.label(f"@{p.handle}").classes("text-gray-500 text-sm font-mono")
                        ui.badge(p.persona_type.value)
                        with ui.row().classes("gap-1"):
                            ui.button(
                                icon="edit",
                                on_click=lambda _, pid=p.id: open_edit(pid),
                            ).props("flat dense round size=sm color=primary")
                            ui.button(
                                icon="delete",
                                on_click=lambda _, pid=p.id, name=p.display_name: confirm_delete(pid, name),
                            ).props("flat dense round size=sm color=red")

        async def create_persona():
            if not new_handle.value.strip():
                ui.notify("Handle is required", type="warning")
                return
            async with async_session() as session:
                p = Persona(
                    handle=new_handle.value.strip(),
                    display_name=new_display.value.strip() or new_handle.value.strip(),
                    bio=new_bio.value.strip(),
                    persona_type=PersonaType(new_type.value),
                    avatar_url=create_avatar_path[0] or "",
                )
                session.add(p)
                await session.commit()
            create_avatar_path[0] = None
            create_avatar_preview.set_visibility(False)
            create_upload.reset()
            new_handle.value = ""
            new_display.value = ""
            new_bio.value = ""
            create_dialog.close()
            await load_personas()
            ui.notify("Persona created", type="positive")

        async def open_edit(pid: uuid.UUID):
            edit_persona_id[0] = pid
            edit_avatar_path[0] = None
            async with async_session() as session:
                p = await session.get(Persona, pid)
                if not p:
                    return
                edit_handle.value = p.handle
                edit_display.value = p.display_name
                edit_bio.value = p.bio or ""
                edit_type.value = p.persona_type.value
                if p.avatar_url:
                    edit_avatar_preview.set_source(p.avatar_url)
                    edit_avatar_preview.set_visibility(True)
                    edit_avatar_path[0] = p.avatar_url
                else:
                    edit_avatar_preview.set_visibility(False)
            edit_upload.reset()
            edit_dialog.open()

        async def save_edit():
            if not edit_handle.value.strip():
                ui.notify("Handle is required", type="warning")
                return
            async with async_session() as session:
                p = await session.get(Persona, edit_persona_id[0])
                if not p:
                    return
                p.handle = edit_handle.value.strip()
                p.display_name = edit_display.value.strip() or edit_handle.value.strip()
                p.bio = edit_bio.value.strip()
                p.persona_type = PersonaType(edit_type.value)
                if edit_avatar_path[0] is not None:
                    p.avatar_url = edit_avatar_path[0] or ""
                await session.commit()
            edit_dialog.close()
            await load_personas()
            ui.notify("Persona updated", type="positive")

        async def confirm_delete(pid: uuid.UUID, display_name: str):
            delete_persona_id[0] = pid
            delete_confirm_label.set_text(
                f'Delete "{display_name}"? Posts by this persona will lose their author reference. This cannot be undone.'
            )
            delete_dialog.open()

        async def do_delete():
            async with async_session() as session:
                await session.execute(
                    sa_update(Post).where(Post.persona_id == delete_persona_id[0]).values(persona_id=None)
                )
                await session.execute(
                    sa_delete(PersonaExercise).where(PersonaExercise.persona_id == delete_persona_id[0])
                )
                p = await session.get(Persona, delete_persona_id[0])
                if p:
                    await session.delete(p)
                await session.commit()
            delete_dialog.close()
            await load_personas()
            ui.notify("Persona deleted", type="positive")

        with ui.column().classes("w-full max-w-4xl mx-auto p-6"):
            with ui.row().classes("items-center justify-between w-full mb-6"):
                with ui.column().classes("gap-0"):
                    ui.label("Persona Registry").classes("text-2xl font-bold text-gray-800")
                    ui.label("Global personas reusable across exercises").classes("text-sm text-gray-500")
                ui.button("New Persona", icon="person_add", on_click=lambda: create_dialog.open()).props(
                    "unelevated no-caps"
                )

            with ui.card().classes("w-full p-2"):
                persona_list = ui.column().classes("w-full")

            with ui.dialog() as create_dialog:
                with ui.card().classes("w-96 p-4"):
                    ui.label("Create Persona").classes("text-lg font-bold text-gray-800 mb-3")
                    new_handle = ui.input("Handle (e.g. svt_nyheter)").props("outlined").classes("w-full")
                    new_display = ui.input("Display Name").props("outlined").classes("w-full")
                    new_bio = ui.textarea("Bio").props("outlined").classes("w-full")
                    new_type = ui.select(
                        {t.value: t.value for t in PersonaType}, value="social", label="Type"
                    ).props("outlined").classes("w-full")
                    ui.label("Avatar").classes("text-sm font-medium text-gray-600 mt-1")
                    with ui.row().classes("items-center gap-3 w-full"):
                        create_avatar_preview = ui.image().classes("w-16 h-16 rounded-full object-cover")
                        create_avatar_preview.set_visibility(False)
                        with ui.column().classes("gap-1"):
                            create_upload = ui.upload(
                                on_upload=handle_create_avatar, auto_upload=True, max_files=1,
                                label="Upload photo",
                            ).props('accept="image/*" flat hide-upload-btn').classes("upload-btn")
                            ui.button(
                                "Remove", icon="close",
                                on_click=lambda: (
                                    create_avatar_path.__setitem__(0, ""),
                                    create_avatar_preview.set_visibility(False),
                                    create_upload.reset(),
                                ),
                            ).props("flat no-caps dense size=sm color=grey")
                    with ui.row().classes("justify-end w-full mt-3 gap-2"):
                        ui.button("Cancel", on_click=create_dialog.close).props("flat no-caps")
                        ui.button("Create", on_click=create_persona).props("unelevated no-caps")

            with ui.dialog() as edit_dialog:
                with ui.card().classes("w-96 p-4"):
                    ui.label("Edit Persona").classes("text-lg font-bold text-gray-800 mb-1")
                    ui.label("Changes apply in all exercises using this persona.").classes(
                        "text-xs text-gray-400 mb-3"
                    )
                    edit_handle = ui.input("Handle").props("outlined").classes("w-full")
                    edit_display = ui.input("Display Name").props("outlined").classes("w-full")
                    edit_bio = ui.textarea("Bio").props("outlined").classes("w-full")
                    edit_type = ui.select(
                        {t.value: t.value for t in PersonaType}, value="social", label="Type"
                    ).props("outlined").classes("w-full")
                    ui.label("Avatar").classes("text-sm font-medium text-gray-600 mt-1")
                    with ui.row().classes("items-center gap-3 w-full"):
                        edit_avatar_preview = ui.image().classes("w-16 h-16 rounded-full object-cover")
                        edit_avatar_preview.set_visibility(False)
                        with ui.column().classes("gap-1"):
                            edit_upload = ui.upload(
                                on_upload=handle_edit_avatar, auto_upload=True, max_files=1,
                                label="Upload photo",
                            ).props('accept="image/*" flat hide-upload-btn').classes("upload-btn")
                            ui.button(
                                "Remove", icon="close",
                                on_click=lambda: (
                                    edit_avatar_path.__setitem__(0, ""),
                                    edit_avatar_preview.set_visibility(False),
                                    edit_upload.reset(),
                                ),
                            ).props("flat no-caps dense size=sm color=grey")
                    with ui.row().classes("justify-end w-full mt-3 gap-2"):
                        ui.button("Cancel", on_click=edit_dialog.close).props("flat no-caps")
                        ui.button("Save", on_click=save_edit).props("unelevated no-caps")

            with ui.dialog() as delete_dialog:
                with ui.card().classes("w-96 p-4"):
                    with ui.row().classes("items-center gap-2 mb-3"):
                        ui.icon("warning", size="sm").classes("text-red-500")
                        ui.label("Delete Persona").classes("text-lg font-bold text-gray-800")
                    delete_confirm_label = ui.label("").classes("text-gray-600")
                    with ui.row().classes("justify-end w-full mt-4 gap-2"):
                        ui.button("Cancel", on_click=delete_dialog.close).props("flat no-caps")
                        ui.button("Delete", on_click=do_delete).props("unelevated no-caps color=red")

        await load_personas()
