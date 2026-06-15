from nicegui import app, ui

from app.pages.layout import nav_header

# (image filename, alt/caption) for the walkthrough.
def _shot(src: str, caption: str):
    with ui.column().classes("w-full gap-1 my-2"):
        ui.image(f"/static/help/{src}").classes(
            "w-full rounded-lg border border-gray-200 shadow-sm"
        )
        ui.label(caption).classes("text-xs text-gray-400 italic")


def _section(number: int, title: str):
    with ui.row().classes("items-center gap-3 mt-8 mb-1"):
        ui.label(str(number)).classes(
            "flex items-center justify-center w-8 h-8 rounded-full "
            "bg-primary text-white font-bold text-sm"
        )
        ui.label(title).classes("text-xl font-bold text-gray-800")


def _p(text: str):
    ui.markdown(text).classes("text-gray-600 leading-relaxed max-w-none")


def help_page():
    @ui.page("/help")
    async def help_view():
        user_id = app.storage.user.get("user_id")
        if not user_id:
            return ui.navigate.to("/login")
        role = app.storage.user.get("role", "")
        if role not in ("superadmin", "admin"):
            return ui.navigate.to("/")
        await nav_header()

        with ui.column().classes("w-full max-w-3xl mx-auto p-6 gap-0"):
            ui.label("How Monsun works").classes(
                "text-3xl font-bold text-gray-800"
            )
            _p(
                "Monsun simulates a social-media and news environment for training "
                "exercises. As an admin you build an exercise, populate it with "
                "fictional **personas** and a scripted **scenario flow**, then run "
                "the live **feed** that participants interact with. This guide walks "
                "the full flow from start to finish."
            )

            _section(1, "Log in")
            _p(
                "Sign in at the login page. The default superadmin is `admin` / "
                "`admin` — change it in production. Your role decides what you see: "
                "**superadmin** (everything, incl. user management), **admin** (build "
                "and run exercises), **participant** (feed only)."
            )
            _shot("01-login.png", "The login page.")

            _section(2, "Create an exercise")
            _p(
                "From **Exercises** in the header, click **New Exercise**. Each "
                "exercise has a name, description, and a state: "
                "`draft → ready → live → ended → archived`. Participants only see a "
                "feed once the exercise is `live` (or `ready`)."
            )
            _shot("02-exercises.png", "The exercises list (admin view).")

            _section(3, "Configure personas, members and the scenario flow")
            _p(
                "Open an exercise to configure it.\n\n"
                "- **Personas** — the fictional accounts you post as (social source, "
                "news outlet, or both). Each has a handle, display name, bio, and an "
                "optional avatar.\n"
                "- **Members** — the participants who can see this exercise's feed.\n"
                "- **Scenario Flow** — an ordered list of pre-written posts and news "
                "articles (\"injects\"). Reorder them, edit them, and release them "
                "with **Publish next** (one at a time) or the play button on a single "
                "item. Items with a scheduled time publish automatically.\n"
                "- **Clone** copies the whole exercise — personas, members, and flow — "
                "so you can reuse a scenario."
            )
            _shot(
                "03-exercise-detail.png",
                "Exercise configuration: scenario flow (with step-through publishing "
                "and a scheduled item), personas, and members.",
            )

            _section(4, "Run the feed")
            _p(
                "The **feed** is the live view participants use — a social timeline on "
                "the left, news on the right. As an admin you can:\n\n"
                "- **Post** as any persona, attach images, reply and repost.\n"
                "- **Go viral** — boost a social post so it pins to the top of the "
                "feed with a highlight and a *Viral* badge.\n"
                "- See **scheduled** posts you've queued, marked with a badge "
                "(participants don't see them until they publish).\n\n"
                "During a live exercise the feed auto-refreshes every 10 seconds."
            )
            _shot(
                "04-feed.png",
                "The live feed: a boosted \"Viral\" post, a scheduled post badge, and "
                "the news column.",
            )

            _section(5, "Schedule a post")
            _p(
                "When creating any post or article, use **Publish at** to set a future "
                "date and time. Leave it blank to publish immediately. Scheduled items "
                "publish automatically once their time passes and someone views the "
                "feed."
            )
            _shot("05-schedule-post.png", "The new-post dialog with the Publish at field.")

            _section(6, "Write news articles in Markdown")
            _p(
                "News article bodies support Markdown — headings, bold/italic, links, "
                "images, lists, blockquotes, code blocks, and tables. Every article "
                "field has a **?** button with a live cheat-sheet showing the syntax "
                "next to its rendered result."
            )
            _shot("06-markdown-help.png", "The Markdown reference dialog.")

            _section(7, "Manage users and your profile")
            _p(
                "**Superadmins** manage all accounts under **Users** — create users, "
                "set roles, and set or remove anyone's avatar. Every user can set "
                "their own profile picture from **Profile** (click your name in the "
                "header)."
            )
            _shot("07-users.png", "User management (superadmin).")
            _shot("08-profile.png", "Your own profile picture.")

            ui.separator().classes("my-8")
            ui.label(
                "Tip: participants get a streamlined view — just the feed, search, "
                "and their profile. All the admin controls above are hidden from them."
            ).classes("text-sm text-gray-500 italic")
