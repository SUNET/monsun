"""Seed demo data for help-page screenshots. Idempotent: skips if the demo
exercise already exists. Run with CLAW_DATABASE_URL set."""
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.database import async_session, engine
from app.models import (
    Base,
    Exercise,
    ExerciseMembership,
    ExerciseState,
    FeedType,
    InteractionType,
    MemberRole,
    Persona,
    PersonaExercise,
    PersonaType,
    Post,
    PostInteraction,
    User,
    UserRole,
)
from app.services.auth import create_default_admin, hash_password

DEMO_NAME = "Operation Nordlys"


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as s:
        await create_default_admin(s)

    now = datetime.now(timezone.utc)
    async with async_session() as s:
        existing = (await s.execute(
            select(Exercise).where(Exercise.name == DEMO_NAME)
        )).scalar_one_or_none()
        if existing:
            print("Demo exercise already present — skipping seed.")
            return

        admin = (await s.execute(
            select(User).where(User.username == "admin")
        )).scalar_one()

        lars = User(
            username="lars",
            display_name="Lars Eriksson",
            password_hash=hash_password("lars"),
            role=UserRole.participant,
        )
        s.add(lars)
        await s.flush()

        ex = Exercise(
            name=DEMO_NAME,
            description="Coordinated disinformation around a Baltic infrastructure incident.",
            state=ExerciseState.live,
        )
        s.add(ex)
        await s.flush()

        s.add(ExerciseMembership(
            exercise_id=ex.id, user_id=lars.id, role=MemberRole.participant,
        ))

        p_news = Persona(handle="svt_nyheter",
                         display_name="SVT Nyheter", persona_type=PersonaType.news,
                         bio="Public service news.")
        p_social = Persona(handle="nordvakt",
                           display_name="Nordvakt", persona_type=PersonaType.both,
                           bio="Citizen watchdog account.")
        p_anon = Persona(handle="baltic_truth",
                         display_name="Baltic Truth", persona_type=PersonaType.social,
                         bio="The stories they hide.")
        s.add_all([p_news, p_social, p_anon])
        await s.flush()

        # Personas are global; membership in an exercise is the junction table.
        for p in (p_news, p_social, p_anon):
            s.add(PersonaExercise(exercise_id=ex.id, persona_id=p.id))

        def social(persona, content, minutes_ago, boosted=False):
            return Post(
                exercise_id=ex.id, persona_id=persona.id, author_user_id=admin.id,
                content=content, feed_type=FeedType.social, is_published=True,
                published_at=now - timedelta(minutes=minutes_ago),
                boosted_at=(now if boosted else None),
            )

        posts = [
            social(p_social, "Reports of a cable outage in the southern Baltic. Officials silent so far. #Nordlys", 42),
            social(p_anon, "They KNEW about the outage hours before telling anyone. Wake up. 🧵", 28, boosted=True),
            social(p_social, "Update: traffic rerouted, no confirmed cause yet. Stay calm, verify sources.", 12),
        ]
        s.add_all(posts)

        # A scheduled (not-yet-published) inject — admins see it badged.
        sched = now + timedelta(days=2)
        s.add(Post(
            exercise_id=ex.id, persona_id=p_social.id, author_user_id=admin.id,
            content="Scheduled briefing: official statement expected shortly.",
            feed_type=FeedType.social, is_published=False, is_scheduled=True,
            scheduled_at=sched, published_at=sched,
        ))

        news = [
            Post(exercise_id=ex.id, persona_id=p_news.id, author_user_id=admin.id,
                 feed_type=FeedType.news, is_published=True, is_inject=True,
                 published_at=now - timedelta(minutes=35),
                 headline="Subsea cable damaged in southern Baltic",
                 content="Authorities investigate a fault affecting regional connectivity.",
                 article_body=(
                     "## What we know\n\n"
                     "A subsea communications cable was **damaged** overnight.\n\n"
                     "- Connectivity rerouted automatically\n"
                     "- No service outage reported\n\n"
                     "> Investigators have not ruled out external causes.\n")),
            Post(exercise_id=ex.id, persona_id=p_news.id, author_user_id=admin.id,
                 feed_type=FeedType.news, is_published=True, is_inject=True,
                 published_at=now - timedelta(minutes=8),
                 headline="Officials urge public to rely on verified sources",
                 content="Spread of unverified claims prompts an appeal for calm.",
                 article_body="Officials asked the public to **verify before sharing**.\n"),
        ]
        s.add_all(news)

        # Scenario flow: ordered injects, partly released. Flow items are the
        # posts with is_inject + sort_order set.
        def flow(order, persona, *, content, headline=None, body=None,
                 published=False, minutes_ago=0, scheduled_in=None):
            return Post(
                exercise_id=ex.id, persona_id=persona.id, author_user_id=admin.id,
                content=content, headline=headline, article_body=body,
                feed_type=FeedType.news if headline else FeedType.social,
                is_inject=True, sort_order=order,
                is_published=published,
                published_at=(now - timedelta(minutes=minutes_ago)) if published else None,
                is_scheduled=scheduled_in is not None,
                scheduled_at=(now + scheduled_in) if scheduled_in else None,
            )

        s.add_all([
            flow(1, p_social, published=True, minutes_ago=40,
                 content="Something is going on with the cable landing station. Anyone else seeing this?"),
            flow(2, p_news, published=True, minutes_ago=30,
                 headline="Cable fault confirmed by operator",
                 content="The operator confirms a fault on the southern link.",
                 body="The operator **confirmed** a fault and began an inspection.\n"),
            flow(3, p_anon,
                 content="Funny how the 'fault' happened the same night as the exercise. Coincidence? 🤔"),
            flow(4, p_news, scheduled_in=timedelta(hours=6),
                 headline="Investigation points to anchor damage",
                 content="Preliminary findings suggest a dragging anchor.",
                 body="Preliminary findings point to **anchor damage**, not sabotage.\n"),
            flow(5, p_social,
                 content="Official statement is out. Read it before sharing anything else."),
        ])

        await s.flush()

        # A couple of likes on the boosted post.
        for uid in (admin.id, lars.id):
            s.add(PostInteraction(post_id=posts[1].id, user_id=uid,
                                  interaction=InteractionType.like))

        await s.commit()
        print("Seeded demo exercise:", ex.id)


if __name__ == "__main__":
    asyncio.run(main())
