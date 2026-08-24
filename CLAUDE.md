# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Monsun is a media simulation platform for training exercises (built for Sunet). Admins create exercises with fictional personas and pre-scripted content flows — scheduled social posts, breaking news articles, persona-driven narratives. Participants see a simulated Twitter/X-style feed and a news feed and interact with them (like, reply, repost).

## Commands

```bash
# Start Postgres
docker compose up db -d

# Install deps (Python 3.14+, uv-managed)
uv sync

# Set env and run
export CLAW_DATABASE_URL="postgresql+asyncpg://claw:claw@localhost:5432/claw"
uv run python -m app.main

# Full stack via Docker Compose
docker compose up --build

# Seed demo data / capture help screenshots (dev scripts).
# Both need PYTHONPATH set and CLAW_DATABASE_URL exported; capture_help.py also
# needs the app running on :8081, the demo data seeded, and playwright
# (one-time: uv run --with playwright python -m playwright install chromium).
PYTHONPATH=. uv run python scripts/seed_demo.py
PYTHONPATH=. uv run --with playwright python scripts/capture_help.py
```

App runs at http://localhost:8081. Default login: `admin` / `admin`.

No test suite, linter, or formatter is configured — verify changes by running the app and testing manually in the browser.

## Architecture

Single-process NiceGUI app. All UI is server-rendered Python — no separate frontend build step. Each page is a function in `app/pages/` that registers routes via `@ui.page`. State is managed per-session via `app.storage.user`. `app/routers/` and `app/schemas/` are empty stub packages — not currently used.

**Database**: PostgreSQL with SQLAlchemy 2.0 async (asyncpg driver). Schema is managed by `Base.metadata.create_all` at startup, with `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` statements in `app/main.py:startup()` for columns/tables added after initial schema creation — this is the de facto migration log, read it to see schema history. `alembic` and `apscheduler` are in `pyproject.toml` but unused — there are no migration scripts and no background scheduler; don't assume either is wired up.

**Config**: `app/config.py` reads env vars prefixed `CLAW_` (e.g. `CLAW_DATABASE_URL`, `CLAW_SECRET_KEY`, `CLAW_STORAGE_SECRET`, `CLAW_BASE_PATH`). `app/main.py` logs a warning at import time if secrets are left at weak defaults. `CLAW_BASE_PATH` supports running behind a reverse-proxy path prefix via `StripPrefixMiddleware`.

**Auth**: bcrypt password hashing, session stored in NiceGUI's encrypted browser storage. Three roles: superadmin, admin, participant.

**Files**: Uploaded images (post attachments, avatars) go to the `media/` directory, served as static files at `/media/`. Allowed extensions are whitelisted in `app/config.py` (`ALLOWED_IMAGE_EXTENSIONS`).

## Key patterns

- `apply_theme()` in `layout.py` is called at the top of every page to inject CSS and brand colors.
- `nav_header()` builds the header with search, navigation (admin-only links), and logout. It also calls `apply_theme()`.
- The login page calls `apply_theme()` directly since it has no header.
- Participant-facing pages skip admin UI: exercise detail redirects to feed, exercises list links directly to feed, header shows only search + logout.
- Scenario flow items are Posts with `is_inject=True`, `sort_order != None`, and `is_published=False` until triggered.
- **Personas are a global registry**, not owned by one exercise: `Persona.exercise_id` is a legacy column kept nullable for backward compat; the real many-to-many link to exercises is the `PersonaExercise` junction table (`persona_exercises`). Query exercise personas via that junction, not `Persona.exercise_id`.
- **Avatars**: users manage their own via `/profile`; superadmin manages any user's via `/users`; personas get one in the create/edit dialogs on `/personas` and on `/exercise/{id}`. Stored under `media/` as `avatar_<uuid>.<ext>`, rendered as `ui.image` (rounded) with a letter `ui.avatar` fallback. `User.avatar_url` is nullable; `Persona.avatar_url` is NOT NULL (use `""`, not `None`).
- **Scheduling**: admins set a future `scheduled_at` (sets `is_scheduled=True`, `is_published=False`) on any new post — social, news, or scenario-flow item. There is no background worker: `publish_due_posts()` in `feed.py` publishes due posts lazily, called on every feed load and from the live-exercise 10s poll. Admins see pending scheduled posts with a badge; participants don't.
- **Go viral**: admins boost a social post by setting `Post.boosted_at`; the feed orders `boosted_at desc nullslast, published_at desc`, so boosted posts pin to the top with a highlight + "Viral" badge.
- **Markdown help**: article bodies render via `ui.markdown` (markdown2, extras `fenced-code-blocks` + `tables`). `markdown_help_button()` in `layout.py` is the shared `?`-button + cheat-sheet placed next to every article-body field.
- **Exercise cloning**: cloning an exercise copies its personas (via `persona_links`), members, and full scenario flow; see `cloned_from_id` on `Exercise`.

## Models

| Model | Table | Purpose |
|-------|-------|---------|
| `User` | `users` | Accounts with role and optional avatar |
| `Exercise` | `exercises` | A simulation exercise with state machine (draft/ready/live/ended/archived) |
| `ExerciseMembership` | `exercise_memberships` | Links users to exercises with a role (admin/participant) |
| `PersonaExercise` | `persona_exercises` | Junction linking global personas to exercises |
| `Persona` | `personas` | Global fictional accounts admins post as; type social/news/both; optional avatar |
| `Post` | `posts` | Social posts and news articles; also scenario flow items and replies/reposts. Supports scheduling (`scheduled_at`/`is_scheduled`) and "Go viral" boosting (`boosted_at`) |
| `PostInteraction` | `post_interactions` | Likes and reposts per user per post |

## Pages

| Route | File | Who sees it |
|-------|------|-------------|
| `/login` | `login.py` | Everyone |
| `/` | `main.py` | Redirects based on role |
| `/exercises` | `exercises.py` | Admin: manage list. Participant: pick exercise |
| `/exercise/{id}` | `exercise_detail.py` | Admin only (participants redirect to feed) |
| `/feed/{id}` | `feed.py` | Everyone — the main simulation view |
| `/users` | `users.py` | Superadmin only |
| `/profile` | `profile.py` | Everyone — manage your own profile picture |
| `/personas` | `personas.py` | Admin — manage the global persona registry |
| `/help` | `help.py` | Admin — in-app documentation (participants redirect to `/`) |

## Conventions

- Use `ui.colors(primary=BRAND_COLOR)` via `apply_theme()` — don't hardcode the brand color in individual components.
- Buttons: `props("unelevated no-caps")` for primary actions, `props("outlined no-caps")` for secondary, `props("flat no-caps")` for tertiary.
- Inputs in dialogs: always use `.props("outlined")`.
- Upload components use the `.upload-btn` CSS class to look compact (see `theme.css`).
- Text colors: `text-gray-800` for headings, `text-gray-500` for secondary text, `text-gray-400` for timestamps/hints.
- Cards: no extra classes needed — `theme.css` handles border-radius, shadow, and hover.

## Adding a new page

1. Create `app/pages/my_page.py` with a function that registers `@ui.page`.
2. Call `nav_header()` at the top (or `apply_theme()` if no header needed).
3. Import and call the function in `app/main.py` before `ui.run()`.

## Adding a model column

Since there are no Alembic migrations, add both:
1. The column to the SQLAlchemy model.
2. An `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` in `main.py:startup()`.
