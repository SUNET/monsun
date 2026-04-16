import os
import uuid
from datetime import datetime, timezone

from nicegui import app, events, ui
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.config import settings, validate_upload_extension
from app.database import async_session
from app.models import (
    Exercise,
    ExerciseMembership,
    ExerciseState,
    FeedType,
    Persona,
    PersonaType,
    Post,
    User,
)
from app.pages.layout import nav_header


def exercise_detail_page():
    @ui.page("/exercise/{exercise_id}")
    async def exercise_detail(exercise_id: str):
        user_id = app.storage.user.get("user_id")
        if not user_id:
            return ui.navigate.to("/login")
        role = app.storage.user.get("role")

        # Participants go straight to the feed — this page is admin-only
        if role not in ("superadmin", "admin"):
            return ui.navigate.to(f"/feed/{exercise_id}")

        await nav_header()
        ex_uuid = uuid.UUID(exercise_id)
        user_uuid = uuid.UUID(user_id)

        async with async_session() as session:
            result = await session.execute(
                select(Exercise)
                .options(selectinload(Exercise.personas))
                .where(Exercise.id == ex_uuid)
            )
            exercise = result.scalar_one_or_none()

        if not exercise:
            ui.label("Exercise not found").classes("text-red-500")
            return

        is_admin = role in ("superadmin", "admin")

        # --- Image upload state for flow items ---
        flow_social_image_path = [None]
        flow_news_image_path = [None]

        async def handle_flow_social_image(e: events.UploadEventArguments):
            ext = validate_upload_extension(e.file.name)
            if not ext:
                ui.notify("Only image files (jpg, png, gif, webp) are allowed", type="negative")
                return
            filename = f"{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(settings.media_dir, filename)
            await e.file.save(filepath)
            flow_social_image_path[0] = f"/media/{filename}"
            flow_social_image_preview.set_source(flow_social_image_path[0])
            flow_social_image_preview.set_visibility(True)
            ui.notify("Image attached", type="positive")

        async def handle_flow_news_image(e: events.UploadEventArguments):
            ext = validate_upload_extension(e.file.name)
            if not ext:
                ui.notify("Only image files (jpg, png, gif, webp) are allowed", type="negative")
                return
            filename = f"{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(settings.media_dir, filename)
            await e.file.save(filepath)
            flow_news_image_path[0] = f"/media/{filename}"
            flow_news_image_preview.set_source(flow_news_image_path[0])
            flow_news_image_preview.set_visibility(True)
            ui.notify("Image attached", type="positive")

        # --- Edit exercise name/description ---
        async def save_exercise_details():
            async with async_session() as session:
                result = await session.execute(
                    select(Exercise).where(Exercise.id == ex_uuid)
                )
                ex = result.scalar_one()
                ex.name = edit_ex_name.value.strip()
                ex.description = edit_ex_desc.value.strip()
                await session.commit()
            edit_exercise_dialog.close()
            ui.notify("Exercise updated", type="positive")
            ui.navigate.to(f"/exercise/{exercise_id}")

        # --- Edit persona ---
        edit_persona_id = [None]

        async def open_edit_persona(pid: uuid.UUID):
            edit_persona_id[0] = pid
            async with async_session() as session:
                p = await session.get(Persona, pid)
                if not p:
                    return
                edit_persona_handle.value = p.handle
                edit_persona_display.value = p.display_name
                edit_persona_bio.value = p.bio or ""
                edit_persona_type.value = p.persona_type.value
            edit_persona_dialog.open()

        async def save_persona():
            if not edit_persona_handle.value.strip():
                ui.notify("Handle is required", type="warning")
                return
            async with async_session() as session:
                p = await session.get(Persona, edit_persona_id[0])
                if p:
                    p.handle = edit_persona_handle.value.strip()
                    p.display_name = edit_persona_display.value.strip() or edit_persona_handle.value.strip()
                    p.bio = edit_persona_bio.value.strip()
                    p.persona_type = PersonaType(edit_persona_type.value)
                    await session.commit()
            edit_persona_dialog.close()
            ui.notify("Persona updated", type="positive")
            ui.navigate.to(f"/exercise/{exercise_id}")

        # --- Edit flow item ---
        edit_flow_id = [None]
        edit_flow_type = [None]

        async def open_edit_flow(post_id: uuid.UUID):
            async with async_session() as session:
                post = await session.get(Post, post_id)
                if not post:
                    return
                edit_flow_id[0] = post_id
                edit_flow_type[0] = post.feed_type
                edit_flow_content.value = post.content or ""
                edit_flow_headline.value = post.headline or ""
                edit_flow_body.value = post.article_body or ""
                # Show/hide news-specific fields
                edit_flow_headline_field.set_visibility(post.feed_type == FeedType.news)
                edit_flow_body_field.set_visibility(post.feed_type == FeedType.news)
            edit_flow_dialog.open()

        async def save_flow_item():
            async with async_session() as session:
                post = await session.get(Post, edit_flow_id[0])
                if post:
                    post.content = edit_flow_content.value.strip()
                    if post.feed_type == FeedType.news:
                        post.headline = edit_flow_headline.value.strip()
                        post.article_body = edit_flow_body.value.strip()
                    await session.commit()
            edit_flow_dialog.close()
            await load_flow()
            ui.notify("Flow item updated", type="positive")

        # --- Clone exercise ---
        async def clone_exercise():
            async with async_session() as session:
                # Load source exercise with personas and flow items
                result = await session.execute(
                    select(Exercise)
                    .options(selectinload(Exercise.personas))
                    .where(Exercise.id == ex_uuid)
                )
                src = result.scalar_one()

                result = await session.execute(
                    select(ExerciseMembership).where(
                        ExerciseMembership.exercise_id == ex_uuid
                    )
                )
                src_members = result.scalars().all()

                result = await session.execute(
                    select(Post)
                    .where(
                        Post.exercise_id == ex_uuid,
                        Post.is_inject == True,
                        Post.sort_order != None,
                    )
                    .order_by(Post.sort_order)
                )
                src_flow = result.scalars().all()

                # Create new exercise
                new_ex = Exercise(
                    name=f"{src.name} (copy)",
                    description=src.description,
                    state=ExerciseState.draft,
                    cloned_from_id=src.id,
                )
                session.add(new_ex)
                await session.flush()

                # Clone personas — map old id to new id for flow items
                persona_map = {}
                for p in src.personas:
                    new_p = Persona(
                        exercise_id=new_ex.id,
                        handle=p.handle,
                        display_name=p.display_name,
                        bio=p.bio,
                        persona_type=p.persona_type,
                    )
                    session.add(new_p)
                    await session.flush()
                    persona_map[p.id] = new_p.id

                # Clone members
                for m in src_members:
                    session.add(ExerciseMembership(
                        exercise_id=new_ex.id,
                        user_id=m.user_id,
                        role=m.role,
                    ))

                # Clone flow items (all unpublished)
                for item in src_flow:
                    new_persona_id = persona_map.get(item.persona_id) if item.persona_id else None
                    session.add(Post(
                        exercise_id=new_ex.id,
                        persona_id=new_persona_id,
                        author_user_id=user_uuid,
                        content=item.content,
                        headline=item.headline,
                        article_body=item.article_body,
                        feed_type=item.feed_type,
                        image_url=item.image_url,
                        is_inject=True,
                        is_published=False,
                        sort_order=item.sort_order,
                    ))

                await session.commit()
                new_id = new_ex.id

            ui.notify("Exercise cloned", type="positive")
            ui.navigate.to(f"/exercise/{new_id}")

        # Load personas for flow dialogs
        async def get_personas():
            async with async_session() as session:
                result = await session.execute(
                    select(Persona)
                    .where(Persona.exercise_id == ex_uuid)
                    .order_by(Persona.handle)
                )
                return result.scalars().all()

        personas = await get_personas()
        persona_options = {str(p.id): f"@{p.handle} — {p.display_name}" for p in personas}

        # --- State management ---
        async def change_state(new_state: ExerciseState):
            async with async_session() as session:
                result = await session.execute(
                    select(Exercise).where(Exercise.id == ex_uuid)
                )
                ex = result.scalar_one()
                ex.state = new_state
                await session.commit()
            ui.notify(f"Exercise is now {new_state.value}", type="positive")
            ui.navigate.to(f"/exercise/{exercise_id}")

        # --- Persona management ---
        async def create_persona():
            if not handle_input.value.strip():
                ui.notify("Handle is required", type="warning")
                return
            async with async_session() as session:
                persona = Persona(
                    exercise_id=ex_uuid,
                    handle=handle_input.value.strip(),
                    display_name=display_input.value.strip() or handle_input.value.strip(),
                    bio=bio_input.value.strip(),
                    persona_type=PersonaType(type_select.value),
                )
                session.add(persona)
                await session.commit()
            persona_dialog.close()
            ui.notify("Persona created", type="positive")
            ui.navigate.to(f"/exercise/{exercise_id}")

        # --- Member management ---
        async def load_available_users():
            async with async_session() as session:
                existing = await session.execute(
                    select(ExerciseMembership.user_id).where(
                        ExerciseMembership.exercise_id == ex_uuid
                    )
                )
                existing_ids = {row[0] for row in existing.all()}

                result = await session.execute(
                    select(User).order_by(User.display_name)
                )
                all_users = result.scalars().all()

            return {
                str(u.id): f"{u.display_name} (@{u.username})"
                for u in all_users
                if u.id not in existing_ids
            }

        async def open_member_dialog():
            available = await load_available_users()
            member_select.options = available
            member_select.value = None
            member_select.update()
            member_dialog.open()

        async def add_member():
            if not member_select.value:
                ui.notify("Select a user", type="warning")
                return
            async with async_session() as session:
                membership = ExerciseMembership(
                    exercise_id=ex_uuid,
                    user_id=uuid.UUID(member_select.value),
                )
                session.add(membership)
                await session.commit()
            member_dialog.close()
            ui.notify("Member added", type="positive")
            ui.navigate.to(f"/exercise/{exercise_id}")

        # --- Scenario flow management ---
        async def get_next_sort_order():
            async with async_session() as session:
                result = await session.execute(
                    select(func.coalesce(func.max(Post.sort_order), 0))
                    .where(
                        Post.exercise_id == ex_uuid,
                        Post.is_inject == True,
                        Post.sort_order != None,
                    )
                )
                return (result.scalar() or 0) + 1

        async def load_flow():
            flow_container.clear()
            async with async_session() as session:
                result = await session.execute(
                    select(Post)
                    .options(selectinload(Post.persona))
                    .where(
                        Post.exercise_id == ex_uuid,
                        Post.is_inject == True,
                        Post.sort_order != None,
                    )
                    .order_by(Post.sort_order)
                )
                items = result.scalars().all()

            with flow_container:
                if not items:
                    with ui.row().classes("items-center gap-2 py-6 justify-center"):
                        ui.icon("playlist_add", size="sm").classes("text-gray-300")
                        ui.label("No scenario items yet").classes("text-gray-400")
                    return

                published_count = sum(1 for i in items if i.is_published)
                total = len(items)
                with ui.row().classes("items-center gap-3 mb-2"):
                    ui.label(f"{published_count}/{total} published").classes(
                        "text-sm text-gray-500"
                    )
                    if any(not i.is_published for i in items):
                        ui.button(
                            "Publish next", icon="play_arrow",
                            on_click=publish_next,
                        ).props("unelevated no-caps dense color=green size=sm")

                for idx, item in enumerate(items):
                    is_social = item.feed_type == FeedType.social
                    accent = "orange" if is_social else "red"
                    type_label = "Social" if is_social else "News"
                    persona_label = f"@{item.persona.handle}" if item.persona else "—"
                    preview = ""
                    if item.headline:
                        preview = item.headline
                    elif item.content:
                        preview = item.content[:80] + ("..." if len(item.content) > 80 else "")

                    with ui.row().classes(
                        f"items-center gap-3 w-full py-2 px-3 rounded-lg "
                        f"{'bg-green-50 border border-green-200' if item.is_published else 'bg-white border border-gray-200'}"
                    ):
                        ui.label(f"#{item.sort_order}").classes(
                            "text-sm font-mono text-gray-400 w-8"
                        )
                        ui.badge(type_label, color=accent).props("dense")
                        if item.is_published:
                            ui.icon("check_circle", size="xs").classes("text-green-500")
                        else:
                            ui.icon("schedule", size="xs").classes("text-gray-400")
                        with ui.column().classes("flex-1 gap-0 min-w-0"):
                            ui.label(persona_label).classes("text-xs text-gray-500")
                            with ui.row().classes("items-center gap-2"):
                                ui.label(preview).classes(
                                    "text-sm text-gray-700 truncate"
                                )
                                if item.image_url:
                                    ui.icon("image", size="xs").classes("text-gray-400").tooltip("Has image")
                        with ui.row().classes("gap-0"):
                            if idx > 0:
                                ui.button(icon="arrow_upward").props(
                                    "flat dense round size=xs color=grey"
                                ).on("click", lambda _, iid=item.id: move_item(iid, -1))
                            if idx < len(items) - 1:
                                ui.button(icon="arrow_downward").props(
                                    "flat dense round size=xs color=grey"
                                ).on("click", lambda _, iid=item.id: move_item(iid, 1))
                            ui.button(icon="edit").props(
                                "flat dense round size=xs color=grey"
                            ).on("click", lambda _, iid=item.id: open_edit_flow(iid))
                            if not item.is_published:
                                ui.button(icon="play_arrow").props(
                                    "flat dense round size=xs color=green"
                                ).on(
                                    "click",
                                    lambda _, iid=item.id: publish_single(iid),
                                ).tooltip("Publish this item")
                            ui.button(icon="delete").props(
                                "flat dense round size=xs color=red"
                            ).on("click", lambda _, iid=item.id: delete_flow_item(iid))

        async def add_social_to_flow():
            if not flow_social_persona.value:
                ui.notify("Select a persona", type="warning")
                return
            if not flow_social_content.value.strip() and not flow_social_image_path[0]:
                ui.notify("Content or image is required", type="warning")
                return
            order = await get_next_sort_order()
            async with async_session() as session:
                post = Post(
                    exercise_id=ex_uuid,
                    persona_id=uuid.UUID(flow_social_persona.value),
                    author_user_id=user_uuid,
                    content=flow_social_content.value.strip(),
                    feed_type=FeedType.social,
                    is_inject=True,
                    is_published=False,
                    sort_order=order,
                    image_url=flow_social_image_path[0],
                )
                session.add(post)
                await session.commit()
            flow_social_content.value = ""
            flow_social_image_path[0] = None
            flow_social_image_preview.set_visibility(False)
            flow_social_upload.reset()
            flow_social_dialog.close()
            await load_flow()
            ui.notify("Added to flow", type="positive")

        async def add_news_to_flow():
            if not flow_news_persona.value:
                ui.notify("Select a news source", type="warning")
                return
            if not flow_news_headline.value.strip():
                ui.notify("Headline is required", type="warning")
                return
            order = await get_next_sort_order()
            async with async_session() as session:
                post = Post(
                    exercise_id=ex_uuid,
                    persona_id=uuid.UUID(flow_news_persona.value),
                    author_user_id=user_uuid,
                    content=flow_news_summary.value.strip(),
                    headline=flow_news_headline.value.strip(),
                    article_body=flow_news_body.value.strip(),
                    feed_type=FeedType.news,
                    is_inject=True,
                    is_published=False,
                    sort_order=order,
                    image_url=flow_news_image_path[0],
                )
                session.add(post)
                await session.commit()
            flow_news_headline.value = ""
            flow_news_summary.value = ""
            flow_news_body.value = ""
            flow_news_image_path[0] = None
            flow_news_image_preview.set_visibility(False)
            flow_news_upload.reset()
            flow_news_dialog.close()
            await load_flow()
            ui.notify("Added to flow", type="positive")

        async def publish_next():
            async with async_session() as session:
                result = await session.execute(
                    select(Post)
                    .where(
                        Post.exercise_id == ex_uuid,
                        Post.is_inject == True,
                        Post.sort_order != None,
                        Post.is_published == False,
                    )
                    .order_by(Post.sort_order)
                    .limit(1)
                )
                post = result.scalar_one_or_none()
                if not post:
                    ui.notify("All items already published", type="info")
                    return
                post.is_published = True
                post.published_at = datetime.now(timezone.utc)
                await session.commit()
            await load_flow()
            ui.notify("Published", type="positive")

        async def publish_single(post_id: uuid.UUID):
            async with async_session() as session:
                post = await session.get(Post, post_id)
                if post and not post.is_published:
                    post.is_published = True
                    post.published_at = datetime.now(timezone.utc)
                    await session.commit()
            await load_flow()
            ui.notify("Published", type="positive")

        async def move_item(post_id: uuid.UUID, direction: int):
            async with async_session() as session:
                result = await session.execute(
                    select(Post)
                    .where(
                        Post.exercise_id == ex_uuid,
                        Post.is_inject == True,
                        Post.sort_order != None,
                    )
                    .order_by(Post.sort_order)
                )
                items = result.scalars().all()
                idx = next((i for i, p in enumerate(items) if p.id == post_id), None)
                if idx is None:
                    return
                swap_idx = idx + direction
                if swap_idx < 0 or swap_idx >= len(items):
                    return
                items[idx].sort_order, items[swap_idx].sort_order = (
                    items[swap_idx].sort_order,
                    items[idx].sort_order,
                )
                await session.commit()
            await load_flow()

        async def delete_flow_item(post_id: uuid.UUID):
            async with async_session() as session:
                post = await session.get(Post, post_id)
                if post:
                    await session.delete(post)
                    await session.commit()
            await load_flow()
            ui.notify("Removed from flow", type="positive")

        # --- Layout ---
        with ui.column().classes("w-full max-w-4xl mx-auto p-6"):
            # Header
            with ui.row().classes("items-center justify-between w-full mb-2"):
                with ui.row().classes("items-center gap-3"):
                    ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/exercises")).props(
                        "flat round"
                    )
                    ui.label(exercise.name).classes("text-2xl font-bold text-gray-800")
                    state_color = {
                        "draft": "gray", "ready": "blue", "live": "green",
                        "ended": "orange", "archived": "red",
                    }.get(exercise.state.value, "gray")
                    ui.badge(exercise.state.value, color=state_color)
                    if is_admin:
                        ui.button(icon="edit", on_click=lambda: (
                            setattr(edit_ex_name, 'value', exercise.name),
                            setattr(edit_ex_desc, 'value', exercise.description or ""),
                            edit_exercise_dialog.open(),
                        )).props("flat round dense size=sm color=grey")
                if is_admin:
                    ui.button("Clone", icon="content_copy", on_click=clone_exercise).props(
                        "outlined no-caps"
                    )

            if exercise.description:
                ui.label(exercise.description).classes("text-gray-500 mb-4 ml-12")

            # State controls
            if is_admin:
                with ui.row().classes("gap-2 mb-6 ml-12"):
                    if exercise.state == ExerciseState.draft:
                        ui.button("Mark Ready", icon="check", on_click=lambda: change_state(ExerciseState.ready)).props(
                            "unelevated no-caps color=primary"
                        )
                    elif exercise.state == ExerciseState.ready:
                        ui.button("Go Live", icon="play_arrow", on_click=lambda: change_state(ExerciseState.live)).props(
                            "unelevated no-caps color=green"
                        )
                    elif exercise.state == ExerciseState.live:
                        ui.button("End Exercise", icon="stop", on_click=lambda: change_state(ExerciseState.ended)).props(
                            "unelevated no-caps color=orange"
                        )
                        ui.button("Open Feed", icon="dynamic_feed", on_click=lambda: ui.navigate.to(f"/feed/{exercise_id}")).props(
                            "unelevated no-caps"
                        )
                    if exercise.state in (ExerciseState.draft, ExerciseState.ready, ExerciseState.live):
                        ui.button("Open Feed", icon="dynamic_feed", on_click=lambda: ui.navigate.to(f"/feed/{exercise_id}")).props(
                            "outlined no-caps"
                        )

            # Scenario Flow
            if is_admin:
                with ui.card().classes("w-full mb-4 p-4"):
                    with ui.row().classes("items-center justify-between w-full mb-3"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("playlist_play", size="sm").classes("text-gray-500")
                            ui.label("Scenario Flow").classes("text-lg font-semibold text-gray-800")
                        with ui.row().classes("gap-1"):
                            ui.button("Social Post", icon="add", on_click=lambda: flow_social_dialog.open()).props(
                                "flat no-caps color=primary dense"
                            )
                            ui.button("News Article", icon="add", on_click=lambda: flow_news_dialog.open()).props(
                                "flat no-caps color=red dense"
                            )

                    flow_container = ui.column().classes("w-full gap-1")

            # Personas
            with ui.card().classes("w-full mb-4 p-4"):
                with ui.row().classes("items-center justify-between w-full mb-3"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("person_outline", size="sm").classes("text-gray-500")
                        ui.label("Personas").classes("text-lg font-semibold text-gray-800")
                    if is_admin:
                        ui.button("Add Persona", icon="add", on_click=lambda: persona_dialog.open()).props(
                            "flat no-caps color=primary"
                        )

                if exercise.personas:
                    for p in exercise.personas:
                        with ui.row().classes("items-center gap-3 py-2 px-2 rounded-lg hover:bg-gray-50"):
                            ui.avatar(p.display_name[0].upper(), color="primary", text_color="white", size="sm")
                            with ui.column().classes("gap-0 flex-1"):
                                ui.label(p.display_name).classes("font-medium text-gray-800")
                                ui.label(f"@{p.handle}").classes("text-gray-500 text-sm font-mono")
                            ui.badge(p.persona_type.value)
                            if is_admin:
                                ui.button(icon="edit", on_click=lambda _, pid=p.id: open_edit_persona(pid)).props(
                                    "flat dense round size=xs color=grey"
                                )
                else:
                    with ui.row().classes("items-center gap-2 py-4 justify-center"):
                        ui.icon("person_add", size="sm").classes("text-gray-300")
                        ui.label("No personas defined yet").classes("text-gray-400")

            # Members
            with ui.card().classes("w-full p-4"):
                with ui.row().classes("items-center justify-between w-full mb-3"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("group", size="sm").classes("text-gray-500")
                        ui.label("Members").classes("text-lg font-semibold text-gray-800")
                    if is_admin:
                        ui.button("Add Member", icon="person_add", on_click=open_member_dialog).props(
                            "flat no-caps color=primary"
                        )

                async with async_session() as session:
                    result = await session.execute(
                        select(ExerciseMembership)
                        .options(selectinload(ExerciseMembership.user))
                        .where(ExerciseMembership.exercise_id == ex_uuid)
                    )
                    members = result.scalars().all()

                if members:
                    for m in members:
                        with ui.row().classes("items-center gap-3 py-2 px-2 rounded-lg hover:bg-gray-50"):
                            ui.avatar(m.user.display_name[0].upper(), color="primary", text_color="white", size="sm")
                            with ui.column().classes("gap-0"):
                                ui.label(m.user.display_name).classes("font-medium text-gray-800")
                                ui.label(f"@{m.user.username}").classes("text-gray-500 text-sm")
                            ui.badge(m.role.value).classes("ml-auto")
                else:
                    with ui.row().classes("items-center gap-2 py-4 justify-center"):
                        ui.icon("group_add", size="sm").classes("text-gray-300")
                        ui.label("No members yet").classes("text-gray-400")

        # Dialogs
        with ui.dialog() as persona_dialog:
            with ui.card().classes("w-96 p-4"):
                ui.label("Create Persona").classes("text-lg font-bold text-gray-800 mb-3")
                handle_input = ui.input("Handle (e.g. svt_nyheter)").props("outlined").classes("w-full")
                display_input = ui.input("Display Name").props("outlined").classes("w-full")
                bio_input = ui.textarea("Bio").props("outlined").classes("w-full")
                type_select = ui.select(
                    {t.value: t.value for t in PersonaType},
                    value="social",
                    label="Type",
                ).props("outlined").classes("w-full")
                with ui.row().classes("justify-end w-full mt-3 gap-2"):
                    ui.button("Cancel", on_click=persona_dialog.close).props("flat no-caps")
                    ui.button("Create", on_click=create_persona).props("unelevated no-caps")

        with ui.dialog() as member_dialog:
            with ui.card().classes("w-96 p-4"):
                ui.label("Add Member").classes("text-lg font-bold text-gray-800 mb-3")
                member_select = ui.select(
                    {}, label="Select user"
                ).props("outlined").classes("w-full")
                with ui.row().classes("justify-end w-full mt-3 gap-2"):
                    ui.button("Cancel", on_click=member_dialog.close).props("flat no-caps")
                    ui.button("Add", on_click=add_member).props("unelevated no-caps")

        # Flow dialogs
        if is_admin:
            with ui.dialog() as flow_social_dialog:
                with ui.card().classes("w-full max-w-xl p-4"):
                    ui.label("Add Social Post to Flow").classes("text-lg font-bold text-gray-800 mb-3")
                    flow_social_persona = ui.select(
                        persona_options,
                        value=str(personas[0].id) if personas else None,
                        label="Post as persona",
                    ).props("outlined").classes("w-full")
                    flow_social_content = ui.textarea("Post content").classes(
                        "w-full"
                    ).props("autogrow outlined rows=3")
                    with ui.row().classes("items-center gap-3 w-full"):
                        flow_social_image_preview = ui.image().classes(
                            "w-20 h-20 rounded-lg object-cover"
                        )
                        flow_social_image_preview.set_visibility(False)
                        flow_social_upload = ui.upload(
                            on_upload=handle_flow_social_image, auto_upload=True, max_files=1,
                            label="Attach image",
                        ).props('accept="image/*" flat hide-upload-btn').classes("upload-btn")
                    with ui.row().classes("justify-end w-full mt-3 gap-2"):
                        ui.button("Cancel", on_click=flow_social_dialog.close).props("flat no-caps")
                        ui.button("Add to Flow", on_click=add_social_to_flow).props("unelevated no-caps")

            with ui.dialog() as flow_news_dialog:
                with ui.card().classes("w-full max-w-xl p-4"):
                    ui.label("Add News Article to Flow").classes("text-lg font-bold text-gray-800 mb-3")
                    flow_news_persona = ui.select(
                        persona_options,
                        value=str(personas[0].id) if personas else None,
                        label="News source (persona)",
                    ).props("outlined").classes("w-full")
                    flow_news_headline = ui.input("Headline").props("outlined").classes("w-full")
                    flow_news_summary = ui.input("Summary (shown in feed)").props("outlined").classes("w-full")
                    flow_news_body = ui.textarea("Full article (Markdown)").classes("w-full").props(
                        "autogrow outlined rows=8"
                    )
                    with ui.row().classes("items-center gap-3 w-full"):
                        flow_news_image_preview = ui.image().classes(
                            "w-20 h-20 rounded-lg object-cover"
                        )
                        flow_news_image_preview.set_visibility(False)
                        flow_news_upload = ui.upload(
                            on_upload=handle_flow_news_image, auto_upload=True, max_files=1,
                            label="Attach image",
                        ).props('accept="image/*" flat hide-upload-btn').classes("upload-btn")
                    with ui.row().classes("justify-end w-full mt-3 gap-2"):
                        ui.button("Cancel", on_click=flow_news_dialog.close).props("flat no-caps")
                        ui.button("Add to Flow", on_click=add_news_to_flow).props("unelevated no-caps")

            # Edit flow item dialog
            with ui.dialog() as edit_flow_dialog:
                with ui.card().classes("w-full max-w-xl p-4"):
                    ui.label("Edit Flow Item").classes("text-lg font-bold text-gray-800 mb-3")
                    edit_flow_content = ui.textarea("Content").classes("w-full").props("autogrow outlined rows=3")
                    edit_flow_headline_field = ui.input("Headline").props("outlined").classes("w-full")
                    edit_flow_headline = edit_flow_headline_field
                    edit_flow_body_field = ui.textarea("Full article (Markdown)").classes("w-full").props(
                        "autogrow outlined rows=8"
                    )
                    edit_flow_body = edit_flow_body_field
                    with ui.row().classes("justify-end w-full mt-3 gap-2"):
                        ui.button("Cancel", on_click=edit_flow_dialog.close).props("flat no-caps")
                        ui.button("Save", on_click=save_flow_item).props("unelevated no-caps")

            await load_flow()

        # Edit exercise dialog
        if is_admin:
            with ui.dialog() as edit_exercise_dialog:
                with ui.card().classes("w-96 p-4"):
                    ui.label("Edit Exercise").classes("text-lg font-bold text-gray-800 mb-3")
                    edit_ex_name = ui.input("Name").props("outlined").classes("w-full")
                    edit_ex_desc = ui.textarea("Description").props("outlined").classes("w-full")
                    with ui.row().classes("justify-end w-full mt-3 gap-2"):
                        ui.button("Cancel", on_click=edit_exercise_dialog.close).props("flat no-caps")
                        ui.button("Save", on_click=save_exercise_details).props("unelevated no-caps")

            with ui.dialog() as edit_persona_dialog:
                with ui.card().classes("w-96 p-4"):
                    ui.label("Edit Persona").classes("text-lg font-bold text-gray-800 mb-3")
                    edit_persona_handle = ui.input("Handle").props("outlined").classes("w-full")
                    edit_persona_display = ui.input("Display Name").props("outlined").classes("w-full")
                    edit_persona_bio = ui.textarea("Bio").props("outlined").classes("w-full")
                    edit_persona_type = ui.select(
                        {t.value: t.value for t in PersonaType},
                        value="social",
                        label="Type",
                    ).props("outlined").classes("w-full")
                    with ui.row().classes("justify-end w-full mt-3 gap-2"):
                        ui.button("Cancel", on_click=edit_persona_dialog.close).props("flat no-caps")
                        ui.button("Save", on_click=save_persona).props("unelevated no-caps")
