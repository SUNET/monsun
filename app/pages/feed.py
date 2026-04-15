import os
import uuid
from datetime import datetime, timezone

from nicegui import app, events, ui
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import async_session
from app.models import (
    Exercise,
    ExerciseState,
    FeedType,
    InteractionType,
    Persona,
    Post,
    PostInteraction,
)
from app.pages.layout import nav_header


def feed_page():
    @ui.page("/feed/{exercise_id}")
    async def feed(exercise_id: str):
        user_id = app.storage.user.get("user_id")
        if not user_id:
            return ui.navigate.to("/login")
        nav_header()
        user_uuid = uuid.UUID(user_id)
        ex_uuid = uuid.UUID(exercise_id)
        role = app.storage.user.get("role", "participant")
        display_name = app.storage.user.get("display_name", "User")
        username = app.storage.user.get("username", "user")
        is_admin = role in ("superadmin", "admin")

        async with async_session() as session:
            result = await session.execute(
                select(Exercise).where(Exercise.id == ex_uuid)
            )
            exercise = result.scalar_one_or_none()
            if not exercise:
                ui.label("Exercise not found")
                return

            result = await session.execute(
                select(Persona)
                .where(Persona.exercise_id == ex_uuid)
                .order_by(Persona.handle)
            )
            personas = result.scalars().all()

        persona_options = {str(p.id): f"@{p.handle} — {p.display_name}" for p in personas}

        # --- Image upload state ---
        uploaded_image_path = [None]

        async def handle_upload(e: events.UploadEventArguments):
            ext = os.path.splitext(e.file.name)[1].lower()
            filename = f"{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(settings.media_dir, filename)
            await e.file.save(filepath)
            uploaded_image_path[0] = f"/media/{filename}"
            image_preview.set_source(uploaded_image_path[0])
            image_preview.set_visibility(True)
            ui.notify("Image attached", type="positive")

        def clear_image():
            uploaded_image_path[0] = None
            image_preview.set_visibility(False)

        news_uploaded_image_path = [None]

        async def handle_news_upload(e: events.UploadEventArguments):
            ext = os.path.splitext(e.file.name)[1].lower()
            filename = f"{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(settings.media_dir, filename)
            await e.file.save(filepath)
            news_uploaded_image_path[0] = f"/media/{filename}"
            news_image_preview.set_source(news_uploaded_image_path[0])
            news_image_preview.set_visibility(True)
            ui.notify("Image attached", type="positive")

        def clear_news_image():
            news_uploaded_image_path[0] = None
            news_image_preview.set_visibility(False)

        # --- Helpers ---
        def get_selected_persona_id():
            if is_admin and social_persona_select.value:
                return uuid.UUID(social_persona_select.value)
            return None

        # --- Post creation (social) ---
        async def create_post():
            if not post_content.value.strip() and not uploaded_image_path[0]:
                ui.notify("Write something or attach an image", type="warning")
                return
            if is_admin and not social_persona_select.value:
                ui.notify("Select a persona", type="warning")
                return

            persona_id = None
            if is_admin and social_persona_select.value:
                persona_id = uuid.UUID(social_persona_select.value)

            async with async_session() as session:
                post = Post(
                    exercise_id=ex_uuid,
                    persona_id=persona_id,
                    author_user_id=user_uuid,
                    content=post_content.value.strip(),
                    feed_type=FeedType.social,
                    published_at=datetime.now(timezone.utc),
                    image_url=uploaded_image_path[0],
                )
                session.add(post)
                await session.commit()

            post_content.value = ""
            clear_image()
            social_upload.reset()
            social_dialog.close()
            await refresh_social_feed()

        # --- Post creation (news) ---
        async def create_news_post():
            if not news_headline.value.strip():
                ui.notify("Headline is required", type="warning")
                return
            if not news_persona_select.value:
                ui.notify("Select a news source persona", type="warning")
                return

            async with async_session() as session:
                post = Post(
                    exercise_id=ex_uuid,
                    persona_id=uuid.UUID(news_persona_select.value),
                    author_user_id=user_uuid,
                    content=news_summary.value.strip(),
                    headline=news_headline.value.strip(),
                    article_body=news_body.value.strip(),
                    feed_type=FeedType.news,
                    published_at=datetime.now(timezone.utc),
                    is_inject=True,
                    image_url=news_uploaded_image_path[0],
                )
                session.add(post)
                await session.commit()

            news_headline.value = ""
            news_summary.value = ""
            news_body.value = ""
            clear_news_image()
            news_upload.reset()
            news_dialog.close()
            await refresh_news_feed()
            ui.notify("News article published", type="positive")

        # --- Interactions ---
        async def toggle_like(post_id: uuid.UUID):
            async with async_session() as session:
                result = await session.execute(
                    select(PostInteraction).where(
                        PostInteraction.post_id == post_id,
                        PostInteraction.user_id == user_uuid,
                        PostInteraction.interaction == InteractionType.like,
                    )
                )
                existing = result.scalar_one_or_none()
                if existing:
                    await session.delete(existing)
                else:
                    session.add(
                        PostInteraction(
                            post_id=post_id,
                            user_id=user_uuid,
                            interaction=InteractionType.like,
                        )
                    )
                await session.commit()
            await refresh_social_feed()

        # --- Edit state ---
        edit_post_id = [None]
        edit_post_feed_type = [None]

        async def open_edit_social(post_id: uuid.UUID):
            async with async_session() as session:
                post = await session.get(Post, post_id)
                if not post:
                    return
                edit_social_content.value = post.content or ""
            edit_post_id[0] = post_id
            edit_social_dialog.open()

        async def save_edit_social():
            async with async_session() as session:
                post = await session.get(Post, edit_post_id[0])
                if post:
                    post.content = edit_social_content.value.strip()
                    await session.commit()
            edit_social_dialog.close()
            await refresh_social_feed()
            ui.notify("Post updated", type="positive")

        async def open_edit_news(post_id: uuid.UUID):
            async with async_session() as session:
                post = await session.get(Post, post_id)
                if not post:
                    return
                edit_news_headline.value = post.headline or ""
                edit_news_summary.value = post.content or ""
                edit_news_body.value = post.article_body or ""
            edit_post_id[0] = post_id
            edit_news_dialog.open()

        async def save_edit_news():
            if not edit_news_headline.value.strip():
                ui.notify("Headline is required", type="warning")
                return
            async with async_session() as session:
                post = await session.get(Post, edit_post_id[0])
                if post:
                    post.headline = edit_news_headline.value.strip()
                    post.content = edit_news_summary.value.strip()
                    post.article_body = edit_news_body.value.strip()
                    await session.commit()
            edit_news_dialog.close()
            await refresh_news_feed()
            ui.notify("Article updated", type="positive")

        async def delete_post(post_id: uuid.UUID, feed_type: FeedType):
            async with async_session() as session:
                # Delete interactions first
                await session.execute(
                    select(PostInteraction).where(PostInteraction.post_id == post_id)
                )
                for interaction in (await session.execute(
                    select(PostInteraction).where(PostInteraction.post_id == post_id)
                )).scalars().all():
                    await session.delete(interaction)
                # Delete replies
                for reply in (await session.execute(
                    select(Post).where(Post.parent_post_id == post_id)
                )).scalars().all():
                    await session.delete(reply)
                # Delete post
                post = await session.get(Post, post_id)
                if post:
                    await session.delete(post)
                await session.commit()
            if feed_type == FeedType.news:
                await refresh_news_feed()
            else:
                await refresh_social_feed()

        async def reply_to(post_id: uuid.UUID):
            if not reply_content.value.strip():
                ui.notify("Write a reply", type="warning")
                return

            async with async_session() as session:
                post = Post(
                    exercise_id=ex_uuid,
                    persona_id=get_selected_persona_id(),
                    author_user_id=user_uuid,
                    content=reply_content.value.strip(),
                    feed_type=FeedType.social,
                    parent_post_id=post_id,
                    published_at=datetime.now(timezone.utc),
                )
                session.add(post)
                await session.commit()

            reply_content.value = ""
            reply_dialog.close()
            await refresh_social_feed()

        async def do_repost(post_id: uuid.UUID):
            async with async_session() as session:
                post = Post(
                    exercise_id=ex_uuid,
                    persona_id=get_selected_persona_id(),
                    author_user_id=user_uuid,
                    content="",
                    feed_type=FeedType.social,
                    repost_of_id=post_id,
                    published_at=datetime.now(timezone.utc),
                )
                session.add(post)
                await session.commit()
            await refresh_social_feed()

        # --- Load replies for a post ---
        async def load_replies(post_id: uuid.UUID):
            async with async_session() as session:
                result = await session.execute(
                    select(Post)
                    .options(
                        selectinload(Post.persona),
                        selectinload(Post.author),
                    )
                    .where(
                        Post.parent_post_id == post_id,
                        Post.is_published == True,
                    )
                    .order_by(Post.published_at.asc())
                )
                return result.scalars().all()

        # --- Load posts helper ---
        async def load_posts(feed_type: FeedType):
            async with async_session() as session:
                result = await session.execute(
                    select(Post)
                    .options(
                        selectinload(Post.persona),
                        selectinload(Post.author),
                        selectinload(Post.interactions),
                    )
                    .where(
                        Post.exercise_id == ex_uuid,
                        Post.is_published == True,
                        Post.parent_post_id == None,
                        Post.feed_type == feed_type,
                    )
                    .order_by(Post.published_at.desc())
                    .limit(20)
                )
                posts = result.scalars().all()

                reply_counts = {}
                if posts:
                    post_ids = [p.id for p in posts]
                    rc_result = await session.execute(
                        select(Post.parent_post_id, func.count())
                        .where(Post.parent_post_id.in_(post_ids))
                        .group_by(Post.parent_post_id)
                    )
                    reply_counts = dict(rc_result.all())

            return posts, reply_counts

        # --- Render social feed ---
        async def refresh_social_feed():
            social_feed_container.clear()
            posts, reply_counts = await load_posts(FeedType.social)
            with social_feed_container:
                if not posts:
                    with ui.column().classes("items-center py-12 w-full"):
                        ui.icon("chat_bubble_outline", size="xl").classes("text-gray-300")
                        ui.label("No posts yet. Be the first!").classes("text-gray-400 mt-2")
                for post in posts:
                    render_social_post(post, reply_counts.get(post.id, 0))

        # --- Render news feed ---
        async def refresh_news_feed():
            news_feed_container.clear()
            posts, _ = await load_posts(FeedType.news)
            with news_feed_container:
                if not posts:
                    with ui.column().classes("items-center py-12 w-full"):
                        ui.icon("newspaper", size="xl").classes("text-gray-300")
                        ui.label("No news articles yet").classes("text-gray-400 mt-2")
                for post in posts:
                    render_news_post(post)

        last_post_count = [0, 0]  # [social, news]

        async def refresh_all():
            await refresh_social_feed()
            await refresh_news_feed()

        async def poll_for_changes():
            """Only refresh if post count changed — avoids huge WebSocket messages."""
            async with async_session() as session:
                for i, ft in enumerate([FeedType.social, FeedType.news]):
                    result = await session.execute(
                        select(func.count())
                        .select_from(Post)
                        .where(
                            Post.exercise_id == ex_uuid,
                            Post.is_published == True,
                            Post.feed_type == ft,
                        )
                    )
                    count = result.scalar()
                    if count != last_post_count[i]:
                        last_post_count[i] = count
                        if ft == FeedType.social:
                            await refresh_social_feed()
                        else:
                            await refresh_news_feed()

        def get_post_identity(post: Post):
            if post.persona:
                return post.persona.display_name, f"@{post.persona.handle}", post.persona.display_name[0].upper()
            return post.author.display_name, f"@{post.author.username}", post.author.display_name[0].upper()

        def render_reply(reply: Post):
            r_name, r_handle, r_initial = get_post_identity(reply)
            with ui.row().classes("items-start gap-2 w-full"):
                ui.avatar(r_initial, color="grey-4", text_color="grey-8", size="xs")
                with ui.column().classes("flex-1 gap-0"):
                    with ui.row().classes("items-center gap-2"):
                        ui.label(r_name).classes("font-semibold text-gray-700 text-sm")
                        ui.label(r_handle).classes("text-gray-400 text-xs")
                        if reply.published_at:
                            ui.label(reply.published_at.strftime("%H:%M")).classes(
                                "text-gray-400 text-xs"
                            )
                    if reply.content:
                        ui.label(reply.content).classes(
                            "whitespace-pre-wrap text-gray-600 text-sm"
                        )

        def render_social_post(post: Post, reply_count: int):
            post_display_name, post_handle, post_initial = get_post_identity(post)

            like_count = sum(
                1 for i in post.interactions if i.interaction == InteractionType.like
            )
            repost_count = sum(
                1 for i in post.interactions if i.interaction == InteractionType.repost
            )
            user_liked = any(
                i
                for i in post.interactions
                if i.interaction == InteractionType.like
                and str(i.user_id) == user_id
            )

            with ui.card().classes("w-full"):
                ui.element("div").classes("w-full h-1 bg-orange-600 rounded-t")
                if post.repost_of_id:
                    with ui.row().classes("items-center gap-1 px-3 pt-2"):
                        ui.icon("repeat", size="xs").classes("text-gray-400")
                        ui.label(f"Reposted by {post_handle}").classes("text-xs text-gray-400")

                with ui.row().classes("items-start gap-3 w-full p-3"):
                    ui.avatar(post_initial, color="primary", text_color="white")

                    with ui.column().classes("flex-1 gap-1"):
                        with ui.row().classes("items-center gap-2"):
                            ui.label(post_display_name).classes("font-semibold text-gray-800")
                            ui.label(post_handle).classes("text-gray-400 text-sm")
                            if post.published_at:
                                ui.label(
                                    post.published_at.strftime("%H:%M · %b %d")
                                ).classes("text-gray-400 text-sm")
                            if post.is_inject:
                                ui.badge("inject", color="orange").props("dense")

                        if post.content:
                            ui.label(post.content).classes("whitespace-pre-wrap text-gray-700")

                        if post.image_url:
                            ui.image(post.image_url).classes(
                                "w-full max-h-96 object-cover rounded-lg mt-2"
                            )

                        with ui.row().classes("items-center gap-6 mt-2"):
                            with ui.row().classes("items-center gap-1"):
                                ui.button(
                                    icon="chat_bubble_outline",
                                    on_click=lambda _, pid=post.id: open_reply(pid),
                                ).props("flat dense size=sm color=grey")
                                if reply_count:
                                    ui.label(str(reply_count)).classes("text-xs text-gray-500")
                            with ui.row().classes("items-center gap-1"):
                                ui.button(
                                    icon="repeat",
                                    on_click=lambda _, pid=post.id: do_repost(pid),
                                ).props("flat dense size=sm color=grey")
                                if repost_count:
                                    ui.label(str(repost_count)).classes("text-xs text-gray-500")
                            with ui.row().classes("items-center gap-1"):
                                ui.button(
                                    icon="favorite" if user_liked else "favorite_border",
                                    on_click=lambda _, pid=post.id: toggle_like(pid),
                                ).props(
                                    f"flat dense size=sm {'color=red' if user_liked else 'color=grey'}"
                                )
                                if like_count:
                                    ui.label(str(like_count)).classes("text-xs text-gray-500")
                            if is_admin or str(post.author_user_id) == user_id:
                                ui.button(
                                    icon="edit",
                                    on_click=lambda _, pid=post.id: open_edit_social(pid),
                                ).props("flat dense size=sm color=grey")
                                ui.button(
                                    icon="delete_outline",
                                    on_click=lambda _, pid=post.id: delete_post(pid, FeedType.social),
                                ).props("flat dense size=sm color=grey")

                # Expandable replies section
                if reply_count:
                    replies_container = ui.column().classes("w-full")
                    expanded = [False]

                    async def toggle_replies(pid=post.id, container=replies_container, exp=expanded):
                        if exp[0]:
                            container.clear()
                            exp[0] = False
                        else:
                            replies = await load_replies(pid)
                            container.clear()
                            with container:
                                ui.separator()
                                with ui.column().classes(
                                    "w-full gap-3 pl-6 pr-3 py-2 bg-gray-50 rounded-b-lg"
                                ):
                                    for r in replies:
                                        render_reply(r)
                            exp[0] = True

                    with ui.row().classes("px-3 pb-2"):
                        ui.button(
                            f"View {reply_count} {'reply' if reply_count == 1 else 'replies'}",
                            icon="forum",
                            on_click=toggle_replies,
                        ).props("flat dense no-caps size=sm color=grey").classes("text-xs")

        def render_news_post(post: Post):
            post_display_name, post_handle, post_initial = get_post_identity(post)

            def show_article():
                article_source.set_text(f"{post_display_name} {post_handle}")
                article_title.set_text(post.headline or "")
                article_time.set_text(
                    post.published_at.strftime("%H:%M · %b %d, %Y") if post.published_at else ""
                )
                article_content.set_content(post.article_body or post.content or "")
                article_dialog.open()

            with ui.card().classes("w-full cursor-pointer transition-shadow").on(
                "click", show_article
            ):
                ui.element("div").classes("w-full h-1 bg-red-500 rounded-t")
                with ui.column().classes("p-3 gap-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.avatar(post_initial, color="red", text_color="white", size="sm")
                        ui.label(post_display_name).classes("font-semibold text-red-700 text-sm")
                        if post.published_at:
                            ui.label(
                                post.published_at.strftime("%H:%M")
                            ).classes("text-gray-400 text-xs")
                    if post.headline:
                        ui.label(post.headline).classes("text-lg font-bold text-gray-800 leading-tight")
                    if post.content:
                        ui.label(post.content).classes("text-gray-500 text-sm line-clamp-2")
                    if post.image_url:
                        ui.image(post.image_url).classes(
                            "w-full max-h-48 object-cover rounded-lg mt-1"
                        )
                    with ui.row().classes("items-center justify-between w-full mt-1"):
                        ui.label("Read more").classes("text-red-600 text-sm font-semibold")
                        if is_admin or str(post.author_user_id) == user_id:
                            with ui.row().classes("gap-0"):
                                ui.button(icon="edit").props(
                                    "flat dense size=sm color=grey"
                                ).on("click.stop", lambda pid=post.id: open_edit_news(pid))
                                ui.button(icon="delete_outline").props(
                                    "flat dense size=sm color=grey"
                                ).on("click.stop", lambda pid=post.id: delete_post(pid, FeedType.news))

        reply_target_id = None

        def open_reply(post_id: uuid.UUID):
            nonlocal reply_target_id
            reply_target_id = post_id
            reply_content.value = ""
            reply_dialog.open()

        # --- Page Layout ---
        with ui.column().classes("w-full max-w-6xl mx-auto p-6"):
            # Top bar
            with ui.row().classes("items-center justify-between w-full mb-6"):
                with ui.row().classes("items-center gap-3"):
                    if is_admin:
                        ui.button(
                            icon="arrow_back",
                            on_click=lambda: ui.navigate.to(f"/exercise/{exercise_id}"),
                        ).props("flat round")
                    ui.label(exercise.name).classes("text-xl font-bold text-gray-800")
                    state_color = {
                        "draft": "gray", "ready": "blue", "live": "green",
                        "ended": "orange", "archived": "red",
                    }.get(exercise.state.value, "gray")
                    if is_admin:
                        ui.badge(exercise.state.value, color=state_color)

            # Two-column layout: Social feed | News feed
            with ui.row().classes("w-full gap-6 items-start flex-nowrap"):
                # === Left column: Social media feed ===
                with ui.column().classes("w-1/2 min-w-0"):
                    with ui.row().classes("items-center justify-between w-full mb-3"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("tag", size="sm").classes("text-orange-600")
                            ui.label("Social Media").classes("text-lg font-bold text-gray-800")
                        ui.button(
                            icon="add", text="Post",
                            on_click=lambda: social_dialog.open(),
                        ).props("unelevated no-caps dense color=primary")

                    social_feed_container = ui.column().classes("w-full gap-3")

                # === Right column: News feed ===
                with ui.column().classes("w-1/2 min-w-0"):
                    with ui.row().classes("items-center justify-between w-full mb-3"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("newspaper", size="sm").classes("text-red-500")
                            ui.label("News").classes("text-lg font-bold text-gray-800")
                        if is_admin:
                            ui.button(
                                icon="add", text="Article",
                                on_click=lambda: news_dialog.open(),
                            ).props("unelevated no-caps dense color=red")

                    news_feed_container = ui.column().classes("w-full gap-3")

            # Reply dialog
            with ui.dialog() as reply_dialog:
                with ui.card().classes("w-96 p-4"):
                    ui.label("Reply").classes("text-lg font-bold text-gray-800 mb-3")
                    reply_content = ui.textarea(placeholder="Write a reply...").classes(
                        "w-full"
                    ).props("autogrow outlined")
                    with ui.row().classes("justify-end w-full mt-3 gap-2"):
                        ui.button("Cancel", on_click=reply_dialog.close).props("flat no-caps")
                        ui.button(
                            "Reply",
                            on_click=lambda: reply_to(reply_target_id),
                        ).props("unelevated no-caps")

            # Social post creation dialog
            with ui.dialog() as social_dialog:
                with ui.card().classes("w-full max-w-xl p-4"):
                    ui.label("New Post").classes("text-lg font-bold text-gray-800 mb-3")
                    if is_admin and persona_options:
                        social_persona_select = ui.select(
                            persona_options,
                            value=str(personas[0].id) if personas else None,
                            label="Post as persona",
                        ).props("outlined").classes("w-full")
                    else:
                        social_persona_select = type("_", (), {"value": None})()
                        ui.label(f"Posting as {display_name} (@{username})").classes(
                            "text-gray-500 text-sm"
                        )
                    post_content = ui.textarea(placeholder="What's happening?").classes(
                        "w-full"
                    ).props("autogrow outlined rows=3")
                    image_preview = ui.image().classes(
                        "w-full max-h-32 object-cover rounded-lg mt-1"
                    )
                    image_preview.set_visibility(False)
                    social_upload = ui.upload(
                        on_upload=handle_upload,
                        auto_upload=True,
                        max_files=1,
                        label="Attach image",
                    ).props('accept="image/*" flat bordered').classes("w-full")
                    with ui.row().classes("justify-end w-full mt-3 gap-2"):
                        ui.button("Cancel", on_click=social_dialog.close).props("flat no-caps")
                        ui.button("Post", on_click=create_post).props("unelevated no-caps")

            # News article dialog (full article view)
            with ui.dialog() as article_dialog:
                with ui.card().classes("w-full max-w-2xl p-6"):
                    article_source = ui.label("").classes("text-red-600 font-semibold text-sm")
                    article_title = ui.label("").classes("text-2xl font-bold text-gray-800 mt-1")
                    article_time = ui.label("").classes("text-gray-400 text-sm mt-1")
                    ui.separator().classes("my-4")
                    article_content = ui.markdown("").classes("prose max-w-none")
                    with ui.row().classes("justify-end w-full mt-6"):
                        ui.button("Close", on_click=article_dialog.close).props("flat no-caps")

            # News post creation dialog (admin only)
            with ui.dialog() as news_dialog:
                with ui.card().classes("w-full max-w-xl p-4"):
                    ui.label("Publish News Article").classes("text-lg font-bold text-gray-800 mb-3")
                    news_persona_select = ui.select(
                        persona_options,
                        value=str(personas[0].id) if personas else None,
                        label="News source (persona)",
                    ).props("outlined").classes("w-full")
                    news_headline = ui.input("Headline").props("outlined").classes("w-full")
                    news_summary = ui.input("Summary (shown in feed)").props("outlined").classes("w-full")
                    news_body = ui.textarea("Full article (Markdown)").classes("w-full").props(
                        "autogrow outlined rows=8"
                    )
                    news_image_preview = ui.image().classes(
                        "w-full max-h-32 object-cover rounded-lg mt-1"
                    )
                    news_image_preview.set_visibility(False)
                    news_upload = ui.upload(
                        on_upload=handle_news_upload,
                        auto_upload=True,
                        max_files=1,
                        label="Attach image",
                    ).props('accept="image/*" flat bordered').classes("w-full")
                    with ui.row().classes("justify-end w-full mt-3 gap-2"):
                        ui.button("Cancel", on_click=news_dialog.close).props("flat no-caps")
                        ui.button("Publish", on_click=create_news_post).props("unelevated no-caps color=red")

            # Edit social post dialog
            with ui.dialog() as edit_social_dialog:
                with ui.card().classes("w-full max-w-xl p-4"):
                    ui.label("Edit Post").classes("text-lg font-bold text-gray-800 mb-3")
                    edit_social_content = ui.textarea(placeholder="Edit your post...").classes(
                        "w-full"
                    ).props("autogrow outlined rows=3")
                    with ui.row().classes("justify-end w-full mt-3 gap-2"):
                        ui.button("Cancel", on_click=edit_social_dialog.close).props("flat no-caps")
                        ui.button("Save", on_click=save_edit_social).props("unelevated no-caps")

            # Edit news article dialog
            with ui.dialog() as edit_news_dialog:
                with ui.card().classes("w-full max-w-xl p-4"):
                    ui.label("Edit Article").classes("text-lg font-bold text-gray-800 mb-3")
                    edit_news_headline = ui.input("Headline").props("outlined").classes("w-full")
                    edit_news_summary = ui.input("Summary (shown in feed)").props("outlined").classes("w-full")
                    edit_news_body = ui.textarea("Full article (Markdown)").classes("w-full").props(
                        "autogrow outlined rows=8"
                    )
                    with ui.row().classes("justify-end w-full mt-3 gap-2"):
                        ui.button("Cancel", on_click=edit_news_dialog.close).props("flat no-caps")
                        ui.button("Save", on_click=save_edit_news).props("unelevated no-caps")

        # Auto-refresh for live exercises
        if exercise.state == ExerciseState.live:
            ui.timer(10.0, poll_for_changes)

        await refresh_all()
