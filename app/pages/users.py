import os
import uuid

from nicegui import app, events, ui
from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models import User, UserRole
from app.pages.layout import nav_header
from app.services.auth import hash_password


def _user_avatar(user: "User", size: str = "sm"):
    """Render a user avatar — image if available, letter fallback."""
    if user.avatar_url:
        ui.image(user.avatar_url).classes(
            f"rounded-full object-cover {'w-8 h-8' if size == 'sm' else 'w-10 h-10'}"
        )
    else:
        ui.avatar(
            user.display_name[0].upper(), color="primary", text_color="white", size=size
        )


def users_page():
    @ui.page("/users")
    async def users():
        user_id = app.storage.user.get("user_id")
        role = app.storage.user.get("role")
        if not user_id or role != "superadmin":
            return ui.navigate.to("/")
        nav_header()

        # --- State ---
        edit_user_id = [None]
        delete_user_id = [None]
        edit_avatar_path = [None]

        # --- Avatar upload handler for edit dialog ---
        async def handle_avatar_upload(e: events.UploadEventArguments):
            ext = os.path.splitext(e.file.name)[1].lower()
            filename = f"avatar_{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(settings.media_dir, filename)
            await e.file.save(filepath)
            edit_avatar_path[0] = f"/media/{filename}"
            edit_avatar_preview.set_source(edit_avatar_path[0])
            edit_avatar_preview.set_visibility(True)
            ui.notify("Avatar uploaded", type="positive")

        async def load_users():
            user_list.clear()
            async with async_session() as session:
                result = await session.execute(
                    select(User).order_by(User.username)
                )
                all_users = result.scalars().all()

            with user_list:
                if not all_users:
                    with ui.column().classes("items-center py-16 w-full"):
                        ui.icon("people_outline", size="xl").classes("text-gray-300")
                        ui.label("No users yet").classes("text-gray-400 text-lg mt-2")
                    return
                for u in all_users:
                    is_self = str(u.id) == user_id
                    with ui.row().classes(
                        "items-center gap-4 w-full py-3 px-3 rounded-lg hover:bg-gray-50"
                    ):
                        _user_avatar(u)
                        with ui.column().classes("gap-0 flex-1"):
                            ui.label(u.display_name).classes("font-medium text-gray-800")
                            ui.label(f"@{u.username}").classes("text-gray-500 text-sm")
                        ui.badge(u.role.value)
                        with ui.row().classes("gap-1"):
                            ui.button(
                                icon="edit",
                                on_click=lambda _, uid=u.id: open_edit(uid),
                            ).props("flat dense round size=sm color=primary")
                            if not is_self:
                                ui.button(
                                    icon="delete",
                                    on_click=lambda _, uid=u.id, uname=u.display_name: confirm_delete(uid, uname),
                                ).props("flat dense round size=sm color=red")

        # --- Create user ---
        async def create_user():
            if not new_username.value.strip() or not new_password.value:
                ui.notify("Username and password required", type="warning")
                return
            async with async_session() as session:
                user = User(
                    username=new_username.value.strip(),
                    display_name=new_display.value.strip() or new_username.value.strip(),
                    password_hash=hash_password(new_password.value),
                    role=UserRole(new_role.value),
                )
                session.add(user)
                await session.commit()
            new_username.value = ""
            new_display.value = ""
            new_password.value = ""
            create_dialog.close()
            await load_users()
            ui.notify("User created", type="positive")

        # --- Edit user ---
        async def open_edit(uid: uuid.UUID):
            edit_user_id[0] = uid
            edit_avatar_path[0] = None
            async with async_session() as session:
                u = await session.get(User, uid)
                if not u:
                    ui.notify("User not found", type="negative")
                    return
                edit_username.value = u.username
                edit_display.value = u.display_name
                edit_password.value = ""
                edit_role.value = u.role.value
                if u.avatar_url:
                    edit_avatar_preview.set_source(u.avatar_url)
                    edit_avatar_preview.set_visibility(True)
                    edit_avatar_path[0] = u.avatar_url
                else:
                    edit_avatar_preview.set_visibility(False)
            edit_upload.reset()
            edit_dialog.open()

        async def save_edit():
            if not edit_username.value.strip():
                ui.notify("Username is required", type="warning")
                return
            async with async_session() as session:
                u = await session.get(User, edit_user_id[0])
                if not u:
                    ui.notify("User not found", type="negative")
                    return
                u.username = edit_username.value.strip()
                u.display_name = edit_display.value.strip() or edit_username.value.strip()
                u.role = UserRole(edit_role.value)
                if edit_password.value:
                    u.password_hash = hash_password(edit_password.value)
                if edit_avatar_path[0] is not None:
                    u.avatar_url = edit_avatar_path[0] or None
                await session.commit()
            edit_dialog.close()
            await load_users()
            ui.notify("User updated", type="positive")

        async def remove_avatar():
            edit_avatar_path[0] = ""  # empty string signals removal
            edit_avatar_preview.set_visibility(False)

        # --- Delete user ---
        async def confirm_delete(uid: uuid.UUID, display_name: str):
            delete_user_id[0] = uid
            delete_confirm_label.set_text(
                f'Are you sure you want to delete "{display_name}"? This cannot be undone.'
            )
            delete_dialog.open()

        async def do_delete():
            async with async_session() as session:
                u = await session.get(User, delete_user_id[0])
                if u:
                    await session.delete(u)
                    await session.commit()
            delete_dialog.close()
            await load_users()
            ui.notify("User deleted", type="positive")

        # --- Page layout ---
        with ui.column().classes("w-full max-w-4xl mx-auto p-6"):
            with ui.row().classes("items-center justify-between w-full mb-6"):
                with ui.column().classes("gap-0"):
                    ui.label("User Management").classes("text-2xl font-bold text-gray-800")
                    ui.label("Create and manage user accounts").classes("text-sm text-gray-500")
                ui.button("New User", icon="person_add", on_click=lambda: create_dialog.open()).props(
                    "unelevated no-caps"
                )

            with ui.card().classes("w-full p-2"):
                user_list = ui.column().classes("w-full")

            # Create dialog
            with ui.dialog() as create_dialog:
                with ui.card().classes("w-96 p-4"):
                    ui.label("Create User").classes("text-lg font-bold text-gray-800 mb-3")
                    new_username = ui.input("Username").props("outlined").classes("w-full")
                    new_display = ui.input("Display Name").props("outlined").classes("w-full")
                    new_password = ui.input("Password", password=True).props("outlined").classes("w-full")
                    new_role = ui.select(
                        {r.value: r.value for r in UserRole},
                        value="participant",
                        label="Role",
                    ).props("outlined").classes("w-full")
                    with ui.row().classes("justify-end w-full mt-3 gap-2"):
                        ui.button("Cancel", on_click=create_dialog.close).props("flat no-caps")
                        ui.button("Create", on_click=create_user).props("unelevated no-caps")

            # Edit dialog
            with ui.dialog() as edit_dialog:
                with ui.card().classes("w-96 p-4"):
                    ui.label("Edit User").classes("text-lg font-bold text-gray-800 mb-3")

                    # Avatar section
                    ui.label("Avatar").classes("text-sm font-medium text-gray-600 mb-1")
                    with ui.row().classes("items-center gap-3 w-full"):
                        edit_avatar_preview = ui.image().classes(
                            "w-16 h-16 rounded-full object-cover"
                        )
                        edit_avatar_preview.set_visibility(False)
                        with ui.column().classes("gap-1"):
                            edit_upload = ui.upload(
                                on_upload=handle_avatar_upload, auto_upload=True, max_files=1,
                                label="Upload photo",
                            ).props('accept="image/*" flat hide-upload-btn').classes("upload-btn")
                            ui.button(
                                "Remove", icon="close",
                                on_click=lambda: (remove_avatar(), edit_upload.reset()),
                            ).props("flat no-caps dense size=sm color=grey")

                    edit_username = ui.input("Username").props("outlined").classes("w-full")
                    edit_display = ui.input("Display Name").props("outlined").classes("w-full")
                    edit_password = ui.input(
                        "New Password", password=True
                    ).props("outlined").classes("w-full")
                    ui.label("Leave blank to keep current password").classes("text-xs text-gray-400 -mt-2")
                    edit_role = ui.select(
                        {r.value: r.value for r in UserRole},
                        value="participant",
                        label="Role",
                    ).props("outlined").classes("w-full")
                    with ui.row().classes("justify-end w-full mt-3 gap-2"):
                        ui.button("Cancel", on_click=edit_dialog.close).props("flat no-caps")
                        ui.button("Save", on_click=save_edit).props("unelevated no-caps")

            # Delete confirmation dialog
            with ui.dialog() as delete_dialog:
                with ui.card().classes("w-96 p-4"):
                    with ui.row().classes("items-center gap-2 mb-3"):
                        ui.icon("warning", size="sm").classes("text-red-500")
                        ui.label("Delete User").classes("text-lg font-bold text-gray-800")
                    delete_confirm_label = ui.label("").classes("text-gray-600")
                    with ui.row().classes("justify-end w-full mt-4 gap-2"):
                        ui.button("Cancel", on_click=delete_dialog.close).props("flat no-caps")
                        ui.button("Delete", on_click=do_delete).props("unelevated no-caps color=red")

        await load_users()
