"""Post deletion helpers.

No foreign key in this schema uses ON DELETE CASCADE, so anything referencing a
post must be cleared in application code before the post row goes away.
"""

import uuid

from sqlalchemy import delete as sa_delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InteractionType, Post, PostInteraction


async def collect_dependent_post_ids(
    session: AsyncSession, post_id: uuid.UUID
) -> list[uuid.UUID]:
    """Return post_id plus every reply and repost hanging off it, transitively.

    Reposts can themselves be reposted, so this walks the tree rather than
    looking one level down.
    """
    all_ids = [post_id]
    frontier = [post_id]
    while frontier:
        result = await session.execute(
            select(Post.id).where(
                or_(
                    Post.parent_post_id.in_(frontier),
                    Post.repost_of_id.in_(frontier),
                )
            )
        )
        found = [row[0] for row in result.all() if row[0] not in all_ids]
        if not found:
            break
        all_ids.extend(found)
        frontier = found
    return all_ids


async def delete_post_cascade(session: AsyncSession, post_id: uuid.UUID) -> int:
    """Delete a post with its replies, reposts and interactions. Caller commits.

    Returns the number of post rows removed.
    """
    post_ids = await collect_dependent_post_ids(session, post_id)

    # A repost also owns a "repost" interaction on the post it quotes. Drop those
    # so repost counts stay accurate and the author can repost again.
    result = await session.execute(
        select(Post.repost_of_id, Post.author_user_id).where(
            Post.id.in_(post_ids), Post.repost_of_id != None
        )
    )
    for original_id, author_id in result.all():
        if original_id in post_ids:
            continue  # its interactions go away with the original anyway
        await session.execute(
            sa_delete(PostInteraction).where(
                PostInteraction.post_id == original_id,
                PostInteraction.user_id == author_id,
                PostInteraction.interaction == InteractionType.repost,
            )
        )

    await session.execute(
        sa_delete(PostInteraction).where(PostInteraction.post_id.in_(post_ids))
    )
    await session.execute(sa_delete(Post).where(Post.id.in_(post_ids)))
    return len(post_ids)
