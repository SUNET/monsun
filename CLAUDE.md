# Monsun — Development Guide

## What this is

Monsun is a media simulation platform for training exercises. Admins create exercises with fictional personas and pre-scripted content flows. Participants see a simulated social media + news feed and interact with it.

## Running locally

```bash
# Start Postgres
docker compose up db -d

# Set env and run
export CLAW_DATABASE_URL="postgresql+asyncpg://claw:claw@localhost:5432/claw"
uv run python -m app.main
```

App runs at http://localhost:8081. Default login: admin / admin.

## Architecture

Single-process NiceGUI app. All UI is server-rendered Python — no separate frontend build step. Each page is a function in `app/pages/` that registers routes via `@ui.page`. State is managed per-session via `app.storage.user`.

**Database**: PostgreSQL with SQLAlchemy 2.0 async (asyncpg driver). Schema is managed by `Base.metadata.create_all` at startup, with ALTER TABLE statements in `main.py:startup()` for columns added after initial schema creation. No Alembic migrations are used.

**Auth**: bcrypt password hashing, session stored in NiceGUI's encrypted browser storage. Three roles: superadmin, admin, participant.

**Files**: Uploaded images (post attachments, avatars) go to the `media/` directory, served as static files at `/media/`.

## Key patterns

- `apply_theme()` in `layout.py` is called at the top of every page to inject CSS and brand colors.
- `nav_header()` builds the header with search, navigation (admin-only links), and logout. It also calls `apply_theme()`.
- The login page calls `apply_theme()` directly since it has no header.
- Participant-facing pages skip admin UI: exercise detail redirects to feed, exercises list links directly to feed, header shows only search + logout.
- Scenario flow items are Posts with `is_inject=True`, `sort_order != None`, and `is_published=False` until triggered.

## Models

| Model | Table | Purpose |
|-------|-------|---------|
| `User` | `users` | Accounts with role and optional avatar |
| `Exercise` | `exercises` | A simulation exercise with state machine (draft/ready/live/ended/archived) |
| `ExerciseMembership` | `exercise_memberships` | Links users to exercises with a role |
| `Persona` | `personas` | Fictional accounts that admins post as |
| `Post` | `posts` | Social posts and news articles; also scenario flow items and replies |
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

## Testing

No test suite yet. Manual testing via the browser. For live exercises, the feed auto-polls every 10 seconds.
