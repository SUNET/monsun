import os
import uuid
from datetime import datetime, timezone

from nicegui import app, events, ui
from sqlalchemy import delete as sa_delete, func, select, update as sa_update
from sqlalchemy.orm import selectinload

from app.config import settings, validate_upload_extension
from app.database import async_session
from app.models import (
    Exercise,
    ExerciseMembership,
    ExerciseState,
    FeedType,
    Persona,
    PersonaExercise,
    PersonaType,
    Post,
    PostInteraction,
    User,
)
from app.pages.layout import markdown_help_button, nav_header


FLOW_DRAG_JS = """
(() => {
  if (window.__flowDragReady) return;
  window.__flowDragReady = true;
  let dragId = null;
  const rows = () => document.querySelectorAll('.flow-row');
  const clearMarks = () => rows().forEach((r) => {
    r.classList.remove('flow-drop-above', 'flow-drop-below', 'flow-dragging');
  });
  const rowAt = (e) => (e.target.closest ? e.target.closest('.flow-row') : null);
  const onUpperHalf = (row, e) => {
    const rect = row.getBoundingClientRect();
    return e.clientY < rect.top + rect.height / 2;
  };
  document.addEventListener('dragstart', (e) => {
    const row = rowAt(e);
    if (!row) return;
    if (e.target.closest('button')) { e.preventDefault(); return; }
    dragId = row.dataset.id;
    e.dataTransfer.effectAllowed = 'move';
    try { e.dataTransfer.setData('text/plain', dragId); } catch (err) {}
    row.classList.add('flow-dragging');
  });
  document.addEventListener('dragover', (e) => {
    const row = rowAt(e);
    if (!dragId || !row || row.dataset.id === dragId) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    rows().forEach((r) => r.classList.remove('flow-drop-above', 'flow-drop-below'));
    row.classList.add(onUpperHalf(row, e) ? 'flow-drop-above' : 'flow-drop-below');
  });
  document.addEventListener('drop', (e) => {
    const row = rowAt(e);
    if (dragId && row && row.dataset.id !== dragId) {
      e.preventDefault();
      const before = onUpperHalf(row, e);
      // Move the row right away so the drop feels instant; the server
      // re-renders the list afterwards to fix the #N numbering.
      const dragged = document.querySelector('.flow-row[data-id="' + dragId + '"]');
      if (dragged) row.parentNode.insertBefore(dragged, before ? row : row.nextSibling);
      emitEvent('flow_reorder', { source: dragId, target: row.dataset.id, before: before });
    }
    dragId = null;
    clearMarks();
  });
  document.addEventListener('dragend', () => { dragId = null; clearMarks(); });
})();
"""


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
                edit_persona_avatar[0] = p.avatar_url or None
                if p.avatar_url:
                    edit_persona_avatar_preview.set_source(p.avatar_url)
                    edit_persona_avatar_preview.set_visibility(True)
                else:
                    edit_persona_avatar_preview.set_visibility(False)
            edit_persona_upload.reset()
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
                    if edit_persona_avatar[0] is not None:
                        p.avatar_url = edit_persona_avatar[0] or ""
                    await session.commit()
            edit_persona_dialog.close()
            ui.notify("Persona updated", type="positive")
            ui.navigate.to(f"/exercise/{exercise_id}")

        # --- Persona avatar upload ---
        create_persona_avatar = [None]
        edit_persona_avatar = [None]

        async def _save_persona_avatar(e: events.UploadEventArguments):
            ext = validate_upload_extension(e.file.name)
            if not ext:
                ui.notify("Only image files (jpg, png, gif, webp) are allowed", type="negative")
                return None
            filename = f"avatar_{uuid.uuid4().hex}{ext}"
            await e.file.save(os.path.join(settings.media_dir, filename))
            return f"/media/{filename}"

        async def handle_create_persona_avatar(e: events.UploadEventArguments):
            url = await _save_persona_avatar(e)
            if url:
                create_persona_avatar[0] = url
                create_persona_avatar_preview.set_source(url)
                create_persona_avatar_preview.set_visibility(True)
                ui.notify("Avatar uploaded", type="positive")

        async def handle_edit_persona_avatar(e: events.UploadEventArguments):
            url = await _save_persona_avatar(e)
            if url:
                edit_persona_avatar[0] = url
                edit_persona_avatar_preview.set_source(url)
                edit_persona_avatar_preview.set_visibility(True)
                ui.notify("Avatar uploaded", type="positive")

        # --- Edit flow item ---
        edit_flow_id = [None]
        edit_flow_type = [None]
        edit_flow_image_path = [None]

        def show_edit_flow_image(path: str | None):
            edit_flow_image_path[0] = path
            if path:
                edit_flow_image_preview.set_source(path)
            edit_flow_image_preview.set_visibility(bool(path))
            edit_flow_image_remove.set_visibility(bool(path))

        async def handle_edit_flow_image(e: events.UploadEventArguments):
            ext = validate_upload_extension(e.file.name)
            if not ext:
                ui.notify("Only image files (jpg, png, gif, webp) are allowed", type="negative")
                return
            filename = f"{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(settings.media_dir, filename)
            await e.file.save(filepath)
            show_edit_flow_image(f"/media/{filename}")
            ui.notify("Image attached", type="positive")

        def remove_edit_flow_image():
            show_edit_flow_image(None)
            edit_flow_upload.reset()

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
                edit_flow_schedule.value = (
                    post.scheduled_at.strftime("%Y-%m-%dT%H:%M")
                    if post.scheduled_at
                    else ""
                )
                # Show/hide news-specific fields
                edit_flow_headline_field.set_visibility(post.feed_type == FeedType.news)
                edit_flow_body_field.set_visibility(post.feed_type == FeedType.news)
                edit_flow_md_help.set_visibility(post.feed_type == FeedType.news)
                image_url = post.image_url
            edit_flow_upload.reset()
            show_edit_flow_image(image_url)
            # Force the browser inputs to take the server-side values. When the
            # dialog unmounts, NiceGUI's input component writes the browser's
            # own value back over the element's props, so re-opening it with an
            # unchanged server value would keep showing the stale text.
            for field in (
                edit_flow_content,
                edit_flow_headline,
                edit_flow_body,
                edit_flow_schedule,
            ):
                field.run_method("updateValue")
            edit_flow_dialog.open()

        async def save_flow_item():
            async with async_session() as session:
                post = await session.get(Post, edit_flow_id[0])
                if post:
                    post.content = edit_flow_content.value.strip()
                    post.image_url = edit_flow_image_path[0]
                    if post.feed_type == FeedType.news:
                        post.headline = edit_flow_headline.value.strip()
                        post.article_body = edit_flow_body.value.strip()
                    if not post.is_published:
                        sched_dt = parse_schedule(edit_flow_schedule.value)
                        post.scheduled_at = sched_dt
                        post.is_scheduled = sched_dt is not None
                    await session.commit()
            edit_flow_dialog.close()
            await load_flow()
            ui.notify("Flow item updated", type="positive")

        # --- Clone exercise ---
        async def clone_exercise():
            async with async_session() as session:
                result = await session.execute(
                    select(Exercise).where(Exercise.id == ex_uuid)
                )
                src = result.scalar_one()

                result = await session.execute(
                    select(ExerciseMembership).where(
                        ExerciseMembership.exercise_id == ex_uuid
                    )
                )
                src_members = result.scalars().all()

                result = await session.execute(
                    select(PersonaExercise).where(PersonaExercise.exercise_id == ex_uuid)
                )
                src_persona_links = result.scalars().all()

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

                new_ex = Exercise(
                    name=f"{src.name} (copy)",
                    description=src.description,
                    state=ExerciseState.draft,
                    cloned_from_id=src.id,
                )
                session.add(new_ex)
                await session.flush()

                # Link same global personas to the cloned exercise
                for pl in src_persona_links:
                    session.add(PersonaExercise(
                        exercise_id=new_ex.id,
                        persona_id=pl.persona_id,
                    ))

                for m in src_members:
                    session.add(ExerciseMembership(
                        exercise_id=new_ex.id,
                        user_id=m.user_id,
                        role=m.role,
                    ))

                # Clone flow items — personas are global so persona_id stays the same
                for item in src_flow:
                    session.add(Post(
                        exercise_id=new_ex.id,
                        persona_id=item.persona_id,
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

        # Load personas linked to this exercise
        async def get_personas():
            async with async_session() as session:
                result = await session.execute(
                    select(Persona)
                    .join(PersonaExercise, PersonaExercise.persona_id == Persona.id)
                    .where(PersonaExercise.exercise_id == ex_uuid)
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
                    handle=handle_input.value.strip(),
                    display_name=display_input.value.strip() or handle_input.value.strip(),
                    bio=bio_input.value.strip(),
                    persona_type=PersonaType(type_select.value),
                    avatar_url=create_persona_avatar[0] or "",
                )
                session.add(persona)
                await session.flush()
                session.add(PersonaExercise(exercise_id=ex_uuid, persona_id=persona.id))
                await session.commit()
            create_persona_avatar[0] = None
            create_persona_avatar_preview.set_visibility(False)
            create_persona_upload.reset()
            persona_dialog.close()
            ui.notify("Persona created", type="positive")
            ui.navigate.to(f"/exercise/{exercise_id}")

        link_persona_bios: dict[str, str] = {}

        async def open_link_persona_dialog():
            async with async_session() as session:
                linked = await session.execute(
                    select(PersonaExercise.persona_id).where(
                        PersonaExercise.exercise_id == ex_uuid
                    )
                )
                linked_ids = {row[0] for row in linked.all()}
                result = await session.execute(select(Persona).order_by(Persona.handle))
                all_personas = result.scalars().all()
            available = {}
            link_persona_bios.clear()
            for p in all_personas:
                if p.id in linked_ids:
                    continue
                bio = (p.bio or "").strip()
                label = f"@{p.handle} — {p.display_name}"
                if bio:
                    snippet = bio if len(bio) <= 60 else bio[:60].rstrip() + "…"
                    label += f" · {snippet}"
                available[str(p.id)] = label
                link_persona_bios[str(p.id)] = bio
            link_persona_select.options = available
            link_persona_select.value = None
            link_persona_select.update()
            show_link_persona_bio()
            link_persona_dialog.open()

        def show_link_persona_bio():
            bio = link_persona_bios.get(link_persona_select.value or "", "")
            link_persona_bio_label.set_text(bio or "No bio.")
            link_persona_bio_label.set_visibility(bool(link_persona_select.value))

        async def link_persona():
            if not link_persona_select.value:
                ui.notify("Select a persona", type="warning")
                return
            async with async_session() as session:
                session.add(PersonaExercise(
                    exercise_id=ex_uuid,
                    persona_id=uuid.UUID(link_persona_select.value),
                ))
                await session.commit()
            link_persona_dialog.close()
            ui.notify("Persona linked", type="positive")
            ui.navigate.to(f"/exercise/{exercise_id}")

        async def unlink_persona(pid: uuid.UUID):
            async with async_session() as session:
                result = await session.execute(
                    select(PersonaExercise).where(
                        PersonaExercise.exercise_id == ex_uuid,
                        PersonaExercise.persona_id == pid,
                    )
                )
                link = result.scalar_one_or_none()
                if link:
                    await session.delete(link)
                    await session.commit()
            ui.notify("Persona unlinked", type="positive")
            ui.navigate.to(f"/exercise/{exercise_id}")

        async def delete_exercise():
            async with async_session() as session:
                post_ids_result = await session.execute(
                    select(Post.id).where(Post.exercise_id == ex_uuid)
                )
                post_ids = [row[0] for row in post_ids_result.all()]
                if post_ids:
                    await session.execute(
                        sa_delete(PostInteraction).where(PostInteraction.post_id.in_(post_ids))
                    )
                    await session.execute(
                        sa_update(Post)
                        .where(Post.exercise_id == ex_uuid)
                        .values(parent_post_id=None, repost_of_id=None)
                    )
                await session.execute(sa_delete(Post).where(Post.exercise_id == ex_uuid))
                await session.execute(
                    sa_delete(ExerciseMembership).where(ExerciseMembership.exercise_id == ex_uuid)
                )
                await session.execute(
                    sa_delete(PersonaExercise).where(PersonaExercise.exercise_id == ex_uuid)
                )
                await session.execute(
                    sa_update(Exercise).where(Exercise.cloned_from_id == ex_uuid).values(cloned_from_id=None)
                )
                await session.execute(
                    sa_update(Persona).where(Persona.exercise_id == ex_uuid).values(exercise_id=None)
                )
                await session.execute(sa_delete(Exercise).where(Exercise.id == ex_uuid))
                await session.commit()
            ui.notify("Exercise deleted", type="positive")
            ui.navigate.to("/exercises")

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
            member_select.value = []
            member_select.update()
            if not available:
                ui.notify("Everyone is already a member", type="info")
                return
            member_dialog.open()

        def select_all_members():
            member_select.value = list(member_select.options)
            member_select.update()

        def clear_member_selection():
            member_select.value = []
            member_select.update()

        async def add_member():
            selected = member_select.value or []
            if not selected:
                ui.notify("Select at least one user", type="warning")
                return
            async with async_session() as session:
                for user_id in selected:
                    session.add(ExerciseMembership(
                        exercise_id=ex_uuid,
                        user_id=uuid.UUID(user_id),
                    ))
                await session.commit()
            member_dialog.close()
            ui.notify(
                f"{len(selected)} members added" if len(selected) > 1 else "Member added",
                type="positive",
            )
            ui.navigate.to(f"/exercise/{exercise_id}")

        async def remove_member(user_id: uuid.UUID):
            async with async_session() as session:
                result = await session.execute(
                    select(ExerciseMembership).where(
                        ExerciseMembership.exercise_id == ex_uuid,
                        ExerciseMembership.user_id == user_id,
                    )
                )
                membership = result.scalar_one_or_none()
                if membership:
                    await session.delete(membership)
                    await session.commit()
            ui.notify("Member removed", type="positive")
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

        def restore_scroll(scroll_y) -> None:
            """Put the window scroll offset back after a list rebuild."""
            if scroll_y is None:
                return
            ui.run_javascript(
                # Vue patches the DOM on its own tick, so wait a frame (and once
                # more with a timer) before scrolling back.
                f"const y = {float(scroll_y)};"
                "requestAnimationFrame(() => requestAnimationFrame(() => window.scrollTo(0, y)));"
                "setTimeout(() => window.scrollTo(0, y), 50);"
            )

        async def load_flow(preserve_scroll: bool = True):
            """Re-render the scenario flow list.

            Rebuilding the list empties the page for a moment, and the browser
            clamps the scroll position to the (now much shorter) document — which
            dumped the admin at the bottom of the page after every move/edit. So
            grab the scroll offset first and put it back once the list is redrawn.
            """
            scroll_y = None
            if preserve_scroll:
                try:
                    scroll_y = await ui.run_javascript(
                        "window.scrollY || document.scrollingElement.scrollTop", timeout=1.0
                    )
                except Exception:  # client gone or slow — just skip restoring
                    scroll_y = None
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
                    restore_scroll(scroll_y)
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

                    # flex-nowrap + the min-w-0 chain below: without them the
                    # preview label refuses to shrink, overflows its column and
                    # runs underneath the action buttons instead of truncating.
                    with ui.row().classes(
                        f"flow-row items-center flex-nowrap gap-3 w-full py-2 px-3 rounded-lg "
                        f"{'bg-green-50 border border-green-200' if item.is_published else 'bg-white border border-gray-200'}"
                    ).props(f'draggable="true" data-id="{item.id}"'):
                        ui.icon("drag_indicator", size="sm").classes(
                            "flow-handle text-gray-300 shrink-0 -ml-1"
                        ).tooltip("Drag to reorder")
                        ui.label(f"#{item.sort_order}").classes(
                            "text-sm font-mono text-gray-400 w-8 shrink-0"
                        )
                        ui.badge(type_label, color=accent).props("dense").classes("shrink-0")
                        if item.is_published:
                            ui.icon("check_circle", size="xs").classes("text-green-500 shrink-0")
                        elif item.scheduled_at:
                            ui.icon("schedule", size="xs").classes(
                                "text-blue-500 shrink-0"
                            ).tooltip(
                                f"Scheduled for {item.scheduled_at.strftime('%H:%M · %b %d')}"
                            )
                            ui.label(
                                item.scheduled_at.strftime("%H:%M · %b %d")
                            ).classes("text-xs text-blue-500 shrink-0 whitespace-nowrap")
                        else:
                            ui.icon("schedule", size="xs").classes("text-gray-400 shrink-0")
                        with ui.column().classes("flex-1 min-w-0 gap-0 overflow-hidden"):
                            ui.label(persona_label).classes("text-xs text-gray-500 truncate")
                            with ui.row().classes("items-center flex-nowrap gap-2 w-full min-w-0"):
                                ui.label(preview).classes(
                                    "text-sm text-gray-700 truncate flex-1 min-w-0"
                                )
                                if item.image_url:
                                    ui.icon("image", size="xs").classes(
                                        "text-gray-400 shrink-0"
                                    ).tooltip("Has image")
                        # Row actions. `shrink-0` matters: without it the flex row
                        # squeezes these buttons on top of the preview text. The
                        # move arrows are filled discs rather than flat icons —
                        # flat grey arrows all but disappeared against the row.
                        with ui.row().classes("gap-1 items-center shrink-0 ml-2"):
                            if idx > 0:
                                ui.button(icon="arrow_upward").props(
                                    "dense round size=sm unelevated color=grey-4 text-color=grey-10"
                                ).on("click", lambda _, iid=item.id: move_item(iid, -1)).tooltip("Move up")
                            else:
                                ui.element("div").classes("w-8 h-8")
                            if idx < len(items) - 1:
                                ui.button(icon="arrow_downward").props(
                                    "dense round size=sm unelevated color=grey-4 text-color=grey-10"
                                ).on("click", lambda _, iid=item.id: move_item(iid, 1)).tooltip("Move down")
                            else:
                                ui.element("div").classes("w-8 h-8")
                            ui.button(icon="edit").props(
                                "flat dense round size=sm color=grey-8"
                            ).on("click", lambda _, iid=item.id: open_edit_flow(iid)).tooltip("Edit")
                            if not item.is_published:
                                ui.button(icon="play_arrow").props(
                                    "flat dense round size=sm color=green"
                                ).on(
                                    "click",
                                    lambda _, iid=item.id: publish_single(iid),
                                ).tooltip("Publish this item")
                            ui.button(icon="delete").props(
                                "flat dense round size=sm color=red"
                            ).on("click", lambda _, iid=item.id: delete_flow_item(iid)).tooltip("Delete")

            restore_scroll(scroll_y)

        def parse_schedule(val: str | None):
            """Parse a datetime-local string into a UTC-aware datetime, or None."""
            if not val:
                return None
            try:
                dt = datetime.fromisoformat(val)
            except ValueError:
                return None
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt

        async def add_social_to_flow():
            if not flow_social_persona.value:
                ui.notify("Select a persona", type="warning")
                return
            if not flow_social_content.value.strip() and not flow_social_image_path[0]:
                ui.notify("Content or image is required", type="warning")
                return
            order = await get_next_sort_order()
            sched_dt = parse_schedule(flow_social_schedule.value)
            async with async_session() as session:
                post = Post(
                    exercise_id=ex_uuid,
                    persona_id=uuid.UUID(flow_social_persona.value),
                    author_user_id=user_uuid,
                    content=flow_social_content.value.strip(),
                    feed_type=FeedType.social,
                    is_inject=True,
                    is_published=False,
                    is_scheduled=sched_dt is not None,
                    scheduled_at=sched_dt,
                    sort_order=order,
                    image_url=flow_social_image_path[0],
                )
                session.add(post)
                await session.commit()
            flow_social_content.value = ""
            # Deliberately keep flow_social_schedule: admins add runs of injects
            # around the same time, and the browser keeps showing the previous
            # value after the dialog closes anyway (see open_edit_flow) — so
            # clearing it server-side only desynced the two and silently
            # dropped the time when the admin left the field untouched.
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
            sched_dt = parse_schedule(flow_news_schedule.value)
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
                    is_scheduled=sched_dt is not None,
                    scheduled_at=sched_dt,
                    sort_order=order,
                    image_url=flow_news_image_path[0],
                )
                session.add(post)
                await session.commit()
            flow_news_headline.value = ""
            flow_news_summary.value = ""
            flow_news_body.value = ""
            # Keep flow_news_schedule — see add_social_to_flow.
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

        async def reorder_flow(e) -> None:
            """Drop handler for drag-and-drop reordering (see FLOW_DRAG_JS).

            The browser sends the dragged item, the row it was dropped on and
            whether it landed on that row's upper half; the whole list is then
            renumbered 1..n so sort_order stays gap-free.
            """
            args = e.args[0] if isinstance(e.args, list) else e.args
            if not isinstance(args, dict):
                return
            try:
                source = uuid.UUID(args["source"])
                target = uuid.UUID(args["target"])
            except (KeyError, TypeError, ValueError, AttributeError):
                return
            if source == target:
                return
            before = bool(args.get("before"))
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
                items = list(result.scalars().all())
                ids = [p.id for p in items]
                if source not in ids or target not in ids:
                    return
                moving = items.pop(ids.index(source))
                target_idx = [p.id for p in items].index(target)
                items.insert(target_idx if before else target_idx + 1, moving)
                for position, item in enumerate(items, start=1):
                    item.sort_order = position
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
                        "draft": "gray", "live": "green",
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
                    with ui.row().classes("gap-2"):
                        ui.button("Clone", icon="content_copy", on_click=clone_exercise).props(
                            "outlined no-caps"
                        )
                        ui.button("Delete", icon="delete_forever", on_click=lambda: delete_exercise_dialog.open()).props(
                            "outlined no-caps color=red"
                        )

            if exercise.description:
                ui.label(exercise.description).classes("text-gray-500 mb-4 ml-12")

            # State controls
            if is_admin:
                with ui.row().classes("gap-2 mb-6 ml-12"):
                    if exercise.state == ExerciseState.draft:
                        ui.button("Go Live", icon="play_arrow", on_click=lambda: go_live_dialog.open()).props(
                            "unelevated no-caps color=green"
                        )
                    elif exercise.state == ExerciseState.live:
                        ui.button("End Exercise", icon="stop", on_click=lambda: change_state(ExerciseState.ended)).props(
                            "unelevated no-caps color=orange"
                        )
                        ui.button("Open Feed", icon="dynamic_feed", on_click=lambda: ui.navigate.to(f"/feed/{exercise_id}")).props(
                            "unelevated no-caps"
                        )
                        ui.button("Back to Draft", icon="undo", on_click=lambda: back_to_draft_dialog.open()).props(
                            "outlined no-caps"
                        )
                    if exercise.state == ExerciseState.draft:
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
                    # Drag-and-drop reordering. The listeners are delegated from
                    # `document` on purpose: load_flow() rebuilds every row, so
                    # per-row handlers would die on the first refresh.
                    ui.add_body_html(f"<script>{FLOW_DRAG_JS}</script>")
                    ui.on("flow_reorder", reorder_flow)

            # Personas
            with ui.card().classes("w-full mb-4 p-4"):
                with ui.row().classes("items-center justify-between w-full mb-3"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("person_outline", size="sm").classes("text-gray-500")
                        ui.label("Personas").classes("text-lg font-semibold text-gray-800")
                    if is_admin:
                        with ui.row().classes("gap-1"):
                            ui.button("New", icon="add", on_click=lambda: persona_dialog.open()).props(
                                "flat no-caps color=primary dense"
                            )
                            ui.button("Link", icon="link", on_click=open_link_persona_dialog).props(
                                "flat no-caps color=primary dense"
                            )

                if personas:
                    for p in personas:
                        with ui.row().classes("items-center gap-3 py-2 px-2 rounded-lg hover:bg-gray-50"):
                            if p.avatar_url:
                                ui.image(p.avatar_url).classes("w-8 h-8 rounded-full object-cover")
                            else:
                                ui.avatar(p.display_name[0].upper(), color="primary", text_color="white", size="sm")
                            with ui.column().classes("gap-0 flex-1"):
                                ui.label(p.display_name).classes("font-medium text-gray-800")
                                ui.label(f"@{p.handle}").classes("text-gray-500 text-sm font-mono")
                            ui.badge(p.persona_type.value)
                            if is_admin:
                                ui.button(icon="edit", on_click=lambda _, pid=p.id: open_edit_persona(pid)).props(
                                    "flat dense round size=xs color=grey"
                                )
                                ui.button(icon="link_off", on_click=lambda _, pid=p.id: unlink_persona(pid)).props(
                                    "flat dense round size=xs color=grey"
                                ).tooltip("Unlink from exercise")
                else:
                    with ui.row().classes("items-center gap-2 py-4 justify-center"):
                        ui.icon("person_add", size="sm").classes("text-gray-300")
                        ui.label("No personas linked yet").classes("text-gray-400")

            # Members
            with ui.card().classes("w-full p-4"):
                with ui.row().classes("items-center justify-between w-full mb-3"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("group", size="sm").classes("text-gray-500")
                        ui.label("Members").classes("text-lg font-semibold text-gray-800")
                    if is_admin:
                        ui.button("Add Members", icon="person_add", on_click=open_member_dialog).props(
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
                            if is_admin:
                                ui.button(
                                    icon="person_remove",
                                    on_click=lambda _, uid=m.user_id: remove_member(uid),
                                ).props("flat dense round size=xs color=grey").tooltip(
                                    "Remove from exercise"
                                )
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
                ui.label("Avatar").classes("text-sm font-medium text-gray-600 mt-1")
                with ui.row().classes("items-center gap-3 w-full"):
                    create_persona_avatar_preview = ui.image().classes(
                        "w-16 h-16 rounded-full object-cover"
                    )
                    create_persona_avatar_preview.set_visibility(False)
                    with ui.column().classes("gap-1"):
                        create_persona_upload = ui.upload(
                            on_upload=handle_create_persona_avatar, auto_upload=True, max_files=1,
                            label="Upload photo",
                        ).props('accept="image/*" flat hide-upload-btn').classes("upload-btn")
                        ui.button(
                            "Remove", icon="close",
                            on_click=lambda: (
                                create_persona_avatar.__setitem__(0, ""),
                                create_persona_avatar_preview.set_visibility(False),
                                create_persona_upload.reset(),
                            ),
                        ).props("flat no-caps dense size=sm color=grey")
                with ui.row().classes("justify-end w-full mt-3 gap-2"):
                    ui.button("Cancel", on_click=persona_dialog.close).props("flat no-caps")
                    ui.button("Create", on_click=create_persona).props("unelevated no-caps")

        with ui.dialog() as member_dialog:
            with ui.card().classes("w-96 p-4"):
                ui.label("Add Members").classes("text-lg font-bold text-gray-800 mb-3")
                member_select = ui.select(
                    {}, label="Select users", multiple=True, with_input=True
                ).props("outlined use-chips").classes("w-full")
                with ui.row().classes("items-center gap-2 mt-1"):
                    ui.button("Select all", on_click=select_all_members).props(
                        "flat no-caps dense size=sm color=primary"
                    )
                    ui.button("Clear", on_click=clear_member_selection).props(
                        "flat no-caps dense size=sm color=grey"
                    )
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
                    flow_social_schedule = ui.input(
                        "Publish at (optional — blank = publish manually)"
                    ).props("outlined type=datetime-local").classes("w-full")
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
                        "outlined rows=16"
                    )
                    with ui.row().classes("items-center gap-1 -mt-1"):
                        ui.label("Markdown supported").classes("text-xs text-gray-400")
                        markdown_help_button()
                    flow_news_schedule = ui.input(
                        "Publish at (optional — blank = publish manually)"
                    ).props("outlined type=datetime-local").classes("w-full")
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
                        "outlined rows=16"
                    )
                    edit_flow_body = edit_flow_body_field
                    edit_flow_md_help = ui.row().classes("items-center gap-1 -mt-1")
                    with edit_flow_md_help:
                        ui.label("Markdown supported").classes("text-xs text-gray-400")
                        markdown_help_button()
                    edit_flow_schedule = ui.input(
                        "Publish at (optional — blank = publish manually)"
                    ).props("outlined type=datetime-local").classes("w-full")
                    with ui.row().classes("items-center gap-3 w-full"):
                        edit_flow_image_preview = ui.image().classes(
                            "w-20 h-20 rounded-lg object-cover"
                        )
                        edit_flow_image_preview.set_visibility(False)
                        edit_flow_upload = ui.upload(
                            on_upload=handle_edit_flow_image, auto_upload=True, max_files=1,
                            label="Replace image",
                        ).props('accept="image/*" flat hide-upload-btn').classes("upload-btn")
                        edit_flow_image_remove = ui.button(
                            "Remove image", icon="close", on_click=remove_edit_flow_image
                        ).props("flat no-caps dense color=red")
                        edit_flow_image_remove.set_visibility(False)
                    with ui.row().classes("justify-end w-full mt-3 gap-2"):
                        ui.button("Cancel", on_click=edit_flow_dialog.close).props("flat no-caps")
                        ui.button("Save", on_click=save_flow_item).props("unelevated no-caps")

            await load_flow(preserve_scroll=False)

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
                    ui.label("Avatar").classes("text-sm font-medium text-gray-600 mt-1")
                    with ui.row().classes("items-center gap-3 w-full"):
                        edit_persona_avatar_preview = ui.image().classes(
                            "w-16 h-16 rounded-full object-cover"
                        )
                        edit_persona_avatar_preview.set_visibility(False)
                        with ui.column().classes("gap-1"):
                            edit_persona_upload = ui.upload(
                                on_upload=handle_edit_persona_avatar, auto_upload=True, max_files=1,
                                label="Upload photo",
                            ).props('accept="image/*" flat hide-upload-btn').classes("upload-btn")
                            ui.button(
                                "Remove", icon="close",
                                on_click=lambda: (
                                    edit_persona_avatar.__setitem__(0, ""),
                                    edit_persona_avatar_preview.set_visibility(False),
                                    edit_persona_upload.reset(),
                                ),
                            ).props("flat no-caps dense size=sm color=grey")
                    with ui.row().classes("justify-end w-full mt-3 gap-2"):
                        ui.button("Cancel", on_click=edit_persona_dialog.close).props("flat no-caps")
                        ui.button("Save", on_click=save_persona).props("unelevated no-caps")

            with ui.dialog() as link_persona_dialog:
                with ui.card().classes("w-96 p-4"):
                    ui.label("Link Persona").classes("text-lg font-bold text-gray-800 mb-3")
                    ui.label("Link an existing global persona to this exercise.").classes(
                        "text-sm text-gray-500 -mt-2 mb-2"
                    )
                    link_persona_select = ui.select(
                        {}, label="Select persona",
                        on_change=lambda _: show_link_persona_bio(),
                    ).props("outlined").classes("w-full")
                    link_persona_bio_label = ui.label("").classes(
                        "text-gray-500 text-sm italic mt-2 whitespace-pre-wrap"
                    )
                    link_persona_bio_label.set_visibility(False)
                    with ui.row().classes("justify-end w-full mt-3 gap-2"):
                        ui.button("Cancel", on_click=link_persona_dialog.close).props("flat no-caps")
                        ui.button("Link", on_click=link_persona).props("unelevated no-caps")

            with ui.dialog() as go_live_dialog:
                with ui.card().classes("w-96 p-4"):
                    with ui.row().classes("items-center gap-2 mb-3"):
                        ui.icon("play_arrow", size="sm").classes("text-green-500")
                        ui.label("Go Live").classes("text-lg font-bold text-gray-800")
                    ui.label(
                        f'Start "{exercise.name}"? Participants will see the feed refresh live and scheduled posts will publish as they fall due.'
                    ).classes("text-gray-600")
                    with ui.row().classes("justify-end w-full mt-4 gap-2"):
                        ui.button("Cancel", on_click=go_live_dialog.close).props("flat no-caps")
                        ui.button(
                            "Go Live", on_click=lambda: change_state(ExerciseState.live)
                        ).props("unelevated no-caps color=green")

            with ui.dialog() as back_to_draft_dialog:
                with ui.card().classes("w-96 p-4"):
                    with ui.row().classes("items-center gap-2 mb-3"):
                        ui.icon("undo", size="sm").classes("text-gray-500")
                        ui.label("Back to Draft").classes("text-lg font-bold text-gray-800")
                    ui.label(
                        f'Return "{exercise.name}" to draft? The feed stops auto-refreshing and '
                        "scheduled posts only publish when someone opens it. Posts already "
                        "published stay published."
                    ).classes("text-gray-600")
                    with ui.row().classes("justify-end w-full mt-4 gap-2"):
                        ui.button("Cancel", on_click=back_to_draft_dialog.close).props("flat no-caps")
                        ui.button(
                            "Back to Draft", on_click=lambda: change_state(ExerciseState.draft)
                        ).props("unelevated no-caps")

            with ui.dialog() as delete_exercise_dialog:
                with ui.card().classes("w-96 p-4"):
                    with ui.row().classes("items-center gap-2 mb-3"):
                        ui.icon("warning", size="sm").classes("text-red-500")
                        ui.label("Delete Exercise").classes("text-lg font-bold text-gray-800")
                    ui.label(
                        f'Delete "{exercise.name}"? All posts, flow items, and memberships will be permanently removed. Personas remain in the global registry.'
                    ).classes("text-gray-600")
                    with ui.row().classes("justify-end w-full mt-4 gap-2"):
                        ui.button("Cancel", on_click=delete_exercise_dialog.close).props("flat no-caps")
                        ui.button("Delete", on_click=delete_exercise).props("unelevated no-caps color=red")
