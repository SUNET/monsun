# Monsun

Monsun is a web-based simulation platform that recreates social media and news environments for training exercises. Built for [Sunet](https://www.sunet.se), it lets exercise administrators craft realistic information flows — scheduled social media posts, breaking news articles, persona-driven narratives — while participants interact with the feeds as they would on real platforms.

## Features

**Feeds**
- Twitter/X-style social media timeline with posts, replies, reposts, and likes
- News feed with article cards, headlines, summaries, and full Markdown article bodies
- Image attachments on any post or article
- Live auto-refresh during active exercises

**Scenario management**
- Pre-defined scenario flow — ordered sequence of social posts and news articles
- Step-through publishing: publish the next inject manually or one at a time
- Reorder, edit, and delete flow items before or during an exercise
- Image attachments on flow items
- Clone exercises to reuse scenarios (copies personas, members, and full flow)

**Personas**
- Create fictional social media accounts and news sources per exercise
- Admins post as personas to simulate real accounts
- Each persona has a handle, display name, bio, and type (social/news/both)

**Users and roles**
- Superadmin: full access — user management, all exercises
- Admin: create and run exercises, manage personas/members/flows, post as personas
- Participant: view feeds, post as themselves, like, reply, repost
- Avatar photos for user accounts

**Search**
- Global search from the header on any page
- Searches across posts, news articles, users (admin), and exercises (admin)
- Case-insensitive full-text matching

**Participant experience**
- Streamlined UI — participants see only the feed, no admin controls
- Auto-redirect to active exercise feed on login
- Clean header with just search, name, and logout

## Quick start

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
| `CLAW_MEDIA_DIR` | `./media` | Directory for uploaded images |
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
    exercise.py        # Exercise, ExerciseMembership, ExerciseState
    persona.py         # Persona, PersonaType
    post.py            # Post, PostInteraction, FeedType
  pages/
    layout.py          # Nav header, search dialog, theme
    login.py           # Login page
    exercises.py       # Exercise list (admin: manage, participant: pick)
    exercise_detail.py # Exercise config: personas, members, scenario flow, clone
    feed.py            # Social + news feed with interactions and editing
    users.py           # User management with avatars (superadmin)
  services/
    auth.py            # Password hashing (bcrypt), authentication
static/
  theme.css            # Global bright theme styles
  sunet-logo.svg       # Sunet brand logo (header + login)
  favicon.png          # Browser tab icon
```

## Data model

```
User          1──N  ExerciseMembership  N──1  Exercise
                                                 │
Exercise      1──N  Persona                      │
                       │                         │
Post ─────────────────►│ (persona_id, nullable)  │
  │ exercise_id ──────────────────────────────────┘
  │ author_user_id ──► User
  │ parent_post_id ──► Post (replies)
  │ repost_of_id ───► Post (reposts)
  │
PostInteraction (like/repost per user per post)
```

## Tech stack

- **[NiceGUI](https://nicegui.io)** — Python web UI framework (Quasar/Vue)
- **[SQLAlchemy](https://www.sqlalchemy.org)** 2.0 async with asyncpg
- **PostgreSQL** 16
- **[uv](https://docs.astral.sh/uv/)** — Python package manager
- **Docker** — containerized deployment

## License

Apache License 2.0 — see [LICENSE](LICENSE).
