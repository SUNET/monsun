import os

from nicegui import app, ui

from app.pages.layout import nav_header

_HELP_IMAGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "static",
    "help",
)


def _shot(src: str, caption: str):
    """Render a walkthrough screenshot. Skipped if the PNG hasn't been captured
    yet (see scripts/capture_help.py)."""
    if not os.path.exists(os.path.join(_HELP_IMAGE_DIR, src)):
        return
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


def _sub(title: str):
    ui.label(title).classes("text-base font-semibold text-gray-800 mt-4 mb-1")


def _p(text: str):
    ui.markdown(text).classes("text-gray-600 leading-relaxed max-w-none")


def _note(text: str):
    with ui.row().classes(
        "items-start gap-2 w-full my-3 p-3 rounded-lg bg-blue-50 border border-blue-100"
    ):
        ui.icon("info", size="sm").classes("text-blue-500 mt-1")
        ui.markdown(text).classes("text-sm text-gray-600 flex-1 max-w-none")


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
                "exercises. As an admin you build an **exercise**, staff it with "
                "fictional **personas** from the global registry, script a "
                "**scenario flow** of pre-written injects, then run the live "
                "**feed** that participants read and interact with.\n\n"
                "This guide walks the full flow from start to finish. Jump to a "
                "section, or read it top to bottom the first time."
            )

            _section(1, "Roles and who sees what")
            _p(
                "Your role is set on your user account and decides what the header "
                "shows and what you can do."
            )
            _p(
                "| | Superadmin | Admin | Participant |\n"
                "|---|---|---|---|\n"
                "| Read and interact with a feed | yes | yes | yes (own exercises) |\n"
                "| Post as a persona | yes | yes | no — posts as themselves |\n"
                "| Publish news articles | yes | yes | no |\n"
                "| Go viral, edit/delete any post | yes | yes | own posts only |\n"
                "| Build exercises and scenario flows | yes | yes | no |\n"
                "| Manage the persona registry | yes | yes | no |\n"
                "| Manage user accounts | yes | no | no |\n"
                "| See this help page | yes | yes | no |"
            )
            _p(
                "Participants get a streamlined view: the feed, search, and their own "
                "profile. Every admin control below is hidden from them. A participant "
                "who opens a feed for an exercise they are not a member of is refused."
            )

            _section(2, "Log in")
            _p(
                "Sign in at the login page. The default superadmin is `admin` / "
                "`admin` — change it in production. Roles are re-checked against the "
                "database on every page load, so a role change takes effect on the "
                "user's next navigation."
            )
            _shot("01-login.png", "The login page.")

            _section(3, "Create an exercise")
            _p(
                "From **Exercises** in the header, click **New Exercise** and give it "
                "a name and description. An exercise moves through five states:"
            )
            _p(
                "| State | Meaning |\n"
                "|---|---|\n"
                "| `draft` | Being built. Default for new and cloned exercises. |\n"
                "| `ready` | Prepared, waiting to start. |\n"
                "| `live` | Running — the feed auto-refreshes for everyone. |\n"
                "| `ended` | Finished. The feed stays readable. |\n"
                "| `archived` | Kept for the record. |"
            )
            _p(
                "The buttons on the exercise page walk the states forward: "
                "**Mark Ready → Go Live → End Exercise**. **Open Feed** is available "
                "once the exercise is live or ended."
            )
            _shot("02-exercises.png", "The exercises list (admin view).")

            _sub("Clone and delete")
            _p(
                "**Clone** copies an exercise into a new `draft`: its persona links, "
                "its members, and its whole scenario flow (unpublished, in order). "
                "Personas are global, so the copy points at the same personas rather "
                "than duplicating them. The copy records where it came from.\n\n"
                "**Delete** removes the exercise, its posts, interactions, memberships "
                "and persona links. Personas themselves survive — they belong to the "
                "registry, not to the exercise. This cannot be undone."
            )

            _section(4, "Manage personas (global registry)")
            _p(
                "Personas are the fictional accounts you post as. They live in a "
                "**global registry** under **Personas** in the header and are reused "
                "across exercises — they are not owned by any single one."
            )
            _p(
                "Each persona has a handle (e.g. `svt_nyheter`), a display name, a "
                "bio (shown under the name on every post), an optional avatar, and a "
                "type:\n\n"
                "- **social** — appears in the social-post persona picker\n"
                "- **news** — for news outlets\n"
                "- **both** — usable for either\n\n"
                "Editing a persona changes it **in every exercise that uses it**. "
                "Deleting one unlinks it from all exercises and leaves its existing "
                "posts authorless — they fall back to showing the admin who wrote them."
            )
            _shot("09-personas.png", "The global persona registry.")

            _section(5, "Set up an exercise: personas, members, flow")
            _p(
                "Open an exercise from the list to configure it. Three panels:\n\n"
                "- **Scenario Flow** — the scripted injects (see the next section).\n"
                "- **Personas** — which registry personas this exercise can post as. "
                "**Link** attaches an existing persona; **New** creates one in the "
                "registry and links it in one step; the unlink button detaches it "
                "from this exercise without deleting it.\n"
                "- **Members** — the participants who can open this exercise's feed. "
                "Anyone not a member is refused, even with a direct link."
            )
            _shot(
                "03-exercise-detail.png",
                "Exercise configuration: scenario flow (with step-through publishing "
                "and a scheduled item), personas, and members.",
            )

            _section(6, "Script the scenario flow")
            _p(
                "The scenario flow is an ordered list of pre-written injects — social "
                "posts and news articles — that stay hidden until you release them. "
                "Add them with **Social Post** or **News Article**. Each takes a "
                "persona, the content (headline, feed summary and Markdown body for "
                "articles), an optional image, and an optional publish time."
            )
            _p(
                "Once in the list you can:\n\n"
                "- **Reorder** with the up/down arrows — the order is the release "
                "order.\n"
                "- **Edit** an item's text, body or scheduled time.\n"
                "- **Publish next** — releases the next unpublished item in order. "
                "The counter above the list shows `published/total`.\n"
                "- **Play** on a single row — releases just that item, out of order.\n"
                "- **Delete** an item.\n\n"
                "Published rows turn green. A clock icon marks an item with a "
                "scheduled time; those publish on their own when the time passes. "
                "Released injects appear in the feed with an *inject* badge for admins."
            )

            _section(7, "Run the feed")
            _p(
                "The **feed** is the live view — a social timeline on the left, news "
                "on the right, the 20 most recent items in each. As an admin you can:"
            )
            _p(
                "- **Post** as any persona linked to the exercise, with an optional "
                "image attachment. Leave the persona picker empty to post as "
                "yourself.\n"
                "- **Article** — publish a news article with headline, feed summary "
                "and Markdown body.\n"
                "- **Reply** and **repost** any post, and **like** it.\n"
                "- **Go viral** — boost a social post so it pins to the top of the "
                "feed with an orange highlight and a *Viral* badge. Click again to "
                "un-boost.\n"
                "- **Edit** or **delete** any post; participants get those buttons "
                "only on their own posts.\n"
                "- See **scheduled** posts you have queued, marked with a blue badge. "
                "Participants don't see them until they publish.\n\n"
                "Replies are collapsed behind a *View N replies* button. The feed "
                "polls every 10 seconds and re-renders only when the post count "
                "changes, so an open feed keeps up with a running exercise."
            )
            _shot(
                "04-feed.png",
                "The live feed: a boosted \"Viral\" post, a scheduled post badge, and "
                "the news column.",
            )

            _section(8, "Schedule a post")
            _p(
                "Any new post — social, news article, or scenario-flow inject — has a "
                "**Publish at** field. Set a future date and time and the item is "
                "saved as scheduled and hidden from participants; leave it blank to "
                "publish immediately."
            )
            _note(
                "There is no background worker. Due posts are published lazily "
                "whenever someone loads the feed or the 10-second poll fires. If no "
                "one has the feed open, a scheduled post goes out the moment the next "
                "person opens it — keep a feed open during a live exercise."
            )
            _shot("05-schedule-post.png", "The new-post dialog with the Publish at field.")

            _section(9, "Write news articles in Markdown")
            _p(
                "Article bodies support Markdown — headings, bold/italic, links, "
                "images, lists, blockquotes, fenced code blocks and tables. The feed "
                "shows the headline and summary; clicking **Read more** opens the "
                "rendered article.\n\n"
                "Every article-body field has a **?** button with a cheat-sheet "
                "showing each piece of syntax next to its rendered result."
            )
            _shot("06-markdown-help.png", "The Markdown reference dialog.")

            _section(10, "Search")
            _p(
                "The magnifying glass in the header searches across users, exercises, "
                "social posts and news articles at once, from at least two characters. "
                "Results are grouped by kind and link straight to the matching feed or "
                "exercise. Only published content is searched."
            )

            _section(11, "Images and uploads")
            _p(
                "Post attachments, article images and avatars accept `.jpg`, `.jpeg`, "
                "`.png`, `.gif` and `.webp`; anything else is rejected on upload. "
                "Files are stored on the server under `media/` and served back at "
                "`/media/`."
            )

            _section(12, "Users and your profile")
            _p(
                "**Superadmins** manage all accounts under **Users** — create users, "
                "rename them, change roles, reset passwords (leave the password field "
                "blank to keep the current one), and set or remove anyone's avatar.\n\n"
                "Every user, whatever their role, can set their own profile picture "
                "from **Profile** — click your name in the header."
            )
            _shot("07-users.png", "User management (superadmin).")
            _shot("08-profile.png", "Your own profile picture.")

            ui.separator().classes("my-8")
            _sub("Quick reference")
            _p(
                "| I want to… | Go to |\n"
                "|---|---|\n"
                "| Create or run an exercise | **Exercises** |\n"
                "| Add or edit a fictional account | **Personas** |\n"
                "| Script injects, add members, change state | Open the exercise |\n"
                "| Post, boost, reply, publish an article | **Feed** |\n"
                "| Create an account or change a role | **Users** (superadmin) |\n"
                "| Change my own picture | **Profile** (your name in the header) |"
            )
