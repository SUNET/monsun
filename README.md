# Monsun

Monsun is a web-based simulation platform that recreates social media and news environments for training exercises. Built for [Sunet](https://www.sunet.se), it lets exercise administrators craft realistic information flows — scheduled social media posts, breaking news articles, persona-driven narratives — while participants interact with the feeds as they would on real platforms.

![The simulated social and news feeds](static/help/04-feed.png)

## Features

**Feeds**
- Twitter/X-style social media timeline with posts, replies, reposts, and likes
- News feed with article cards, headlines, summaries, and full Markdown article bodies
- In-app Markdown reference (syntax + rendered result) next to every article field
- Image attachments on any post or article
- Schedule any post or article to publish at a set date and time
- Edit posts and articles after publishing, including replacing or removing the image
- Undo an accidental publish: move a published post back to scheduled at a new time
- "Go viral" — admins boost a social post to the top of the feed with a highlight
- Live auto-refresh during active exercises
- Each feed shows the 20 most recent items, with a "Load more" button for older ones

**Scenario management**
- Pre-defined scenario flow — ordered sequence of social posts and news articles
- Step-through publishing: publish the next inject in order, or release a single item (with a confirm step)
- Unpublish a released item to send it back to pending, or back on its schedule if its time is still ahead
- Schedule flow items to auto-publish at a set date and time
- Reorder flow items by drag-and-drop, or step them one position with the arrow buttons
- Image attachments on flow items
- Clone exercises to reuse scenarios (copies personas, members, and full flow)
- Exercise lifecycle: draft → live → ended → archived; a live exercise can go back to draft

![Exercise configuration with the scenario flow](static/help/03-exercise-detail.png)

**Personas**
- One global registry of fictional social media accounts and news sources, linked into each exercise that uses them
- Admins post as personas to simulate real accounts
- Each persona has a handle, display name, bio, type (social/news/both), and optional avatar

![The global persona registry](static/help/09-personas.png)

**Users and roles**
- Superadmin: full access — user management, all exercises
- Admin: create and run exercises, manage personas/members/flows, post as personas
- Participant: view feeds, post as themselves, like, reply, repost
- Profile pictures: every user manages their own at `/profile`; superadmin can set or remove any user's

**Search**
- Global search from the header on any page
- Searches across posts, news articles, users (admin), and exercises (admin)
- Case-insensitive full-text matching

**Participant experience**
- Streamlined UI — participants see only the feed, no admin controls
- Auto-redirect to active exercise feed on login
- Clean header with search, a Home link, their profile avatar, and logout

## More screenshots

<table>
  <tr>
    <td width="50%"><img src="static/help/05-schedule-post.png" alt="Scheduling a post"><br><sub><b>Scheduling</b> — any post or article can be set to publish at a given time.</sub></td>
    <td width="50%"><img src="static/help/06-markdown-help.png" alt="Markdown reference"><br><sub><b>Markdown help</b> — syntax and rendered result next to every article field.</sub></td>
  </tr>
  <tr>
    <td width="50%"><img src="static/help/02-exercises.png" alt="Exercise list"><br><sub><b>Exercises</b> — admins manage them, participants pick one to join.</sub></td>
    <td width="50%"><img src="static/help/07-users.png" alt="User management"><br><sub><b>Users</b> — roles and avatars, managed by the superadmin.</sub></td>
  </tr>
</table>

## Quick start

### Demo in one command

```bash
./launch_demo.sh
```

Builds the image if needed, starts PostgreSQL and the app, and seeds the demo exercise *Operation Nordlys* — a live exercise with personas, a populated feed and a scenario flow. Open [http://localhost:8081](http://localhost:8081) and log in as `admin` / `admin`. Seeding is skipped if the demo exercise already exists, so the script is safe to re-run.

Works with Docker or Podman (`docker compose`, `docker-compose`, `podman compose` or `podman-compose`, whichever is found first).

| Command | What it does |
|---------|--------------|
| `./launch_demo.sh` | Build (if needed), start, seed |
| `./launch_demo.sh --rebuild` | Force a fresh image build, e.g. after pulling new code |
| `./launch_demo.sh --stop` | Stop the stack; data is kept |
| `./launch_demo.sh --reset` | **Delete the database volume** and start clean — asks you to type `reset` first |

If a port is taken, pick others:

```bash
MONSUN_APP_PORT=9090 MONSUN_DB_PORT=5433 ./launch_demo.sh
```

Set `MONSUN_COMPOSE` to force a specific compose command, e.g. `MONSUN_COMPOSE="podman compose"`.

### Docker Compose (recommended)

```bash
docker compose up --build
```

This starts PostgreSQL and the app. Open [http://localhost:8081](http://localhost:8081).

### Local development

Requires Python 3.14+ and a running PostgreSQL instance.

```bash
# Install dependencies
uv sync

# Configure database
export CLAW_DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/claw"

# Run
uv run python -m app.main
```

The app starts on [http://localhost:8081](http://localhost:8081).

### Behind nginx (production)

Monsun uses WebSockets (Socket.IO). The nginx location block needs:

```nginx
location / {
    proxy_pass http://localhost:8081;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 86400s;
    proxy_send_timeout 86400s;
    client_max_body_size 20m;
}
```

## Default login

A default superadmin account is created on first startup:

| Username | Password |
|----------|----------|
| `admin`  | `admin`  |

Change the password immediately in production.

## Configuration

All settings are environment variables with the `CLAW_` prefix:

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAW_DATABASE_URL` | `postgresql+asyncpg://user:password@localhost:5432/claw` | Async PostgreSQL connection string |
| `CLAW_SECRET_KEY` | `change` | Application secret key |
| `CLAW_STORAGE_SECRET` | `storage` | NiceGUI storage encryption secret |
| `CLAW_MEDIA_DIR` | `<project root>/media` | Directory for uploaded images |
| `CLAW_BASE_PATH` | *(empty)* | URL prefix when behind a reverse proxy |

## Project structure

```
app/
  main.py              # Startup, routing, middleware, schema migrations
  config.py            # Settings from environment variables
  database.py          # SQLAlchemy async engine and session
  models/
    base.py            # DeclarativeBase, TimestampMixin
    user.py            # User, UserRole
    exercise.py        # Exercise, ExerciseMembership, PersonaExercise, ExerciseState, MemberRole
    persona.py         # Persona, PersonaType
    post.py            # Post, PostInteraction, FeedType, InteractionType
  pages/
    layout.py          # Nav header, search dialog, theme
    login.py           # Login page
    exercises.py       # Exercise list (admin: manage, participant: pick)
    exercise_detail.py # Exercise config: personas, members, scenario flow, clone
    feed.py            # Social + news feed: interactions, editing, scheduling, "Go viral"
    users.py           # User management with avatars (superadmin)
    profile.py         # Self-service profile picture (any user)
    personas.py        # Global persona registry
    help.py            # In-app documentation (admin)
  services/
    auth.py            # Password hashing (bcrypt), authentication
scripts/
  seed_demo.py         # Seeds the "Operation Nordlys" demo exercise (idempotent)
  capture_help.py      # Re-captures the screenshots in static/help/ (Playwright)
static/
  theme.css            # Global bright theme styles
  help/                # Screenshots for the in-app help and this README
  sunet-logo.svg       # Sunet brand logo (header + login)
  favicon.png          # Browser tab icon
  favicon.ico
launch_demo.sh         # Build, start and seed the demo stack (Docker or Podman)
docker-compose.yml     # PostgreSQL + app
Dockerfile
```

## Data model

```
User     1──N  ExerciseMembership  N──1  Exercise ◄── cloned_from_id (Exercise)
                                            │
Persona  1──N  PersonaExercise     N──1  ───┤   personas are global,
  ▲                                         │   linked per exercise
  │ persona_id (nullable: posts as self)    │
Post ── exercise_id ────────────────────────┘
  │ author_user_id ──► User
  │ parent_post_id ──► Post (replies)
  │ repost_of_id ────► Post (reposts)
  │
PostInteraction  N──1 User   (like / repost, one per user per post)
```

A post is one of three things, told apart by its columns:

- **Feed post** — a social post or news article (`feed_type`).
- **Scenario-flow inject** — `is_inject` with a `sort_order`; unpublished until released.
- **Scheduled post** — `is_scheduled` with a future `scheduled_at`; published when that time passes.

`Persona.exercise_id` is a legacy column kept for old data; use `PersonaExercise`.

## Tech stack

- **[NiceGUI](https://nicegui.io)** — Python web UI framework (Quasar/Vue)
- **[SQLAlchemy](https://www.sqlalchemy.org)** 2.0 async with asyncpg
- **PostgreSQL** 16
- **[uv](https://docs.astral.sh/uv/)** — Python package manager
- **Docker** — containerized deployment

## License

Apache License 2.0 — see [LICENSE](LICENSE).
