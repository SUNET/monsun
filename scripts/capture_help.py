"""Capture help-page screenshots with Playwright. App must be running on
localhost:8081 with the demo data seeded. Saves PNGs to static/help/."""
import asyncio
import os

from sqlalchemy import select

from app.database import async_session
from app.models import Exercise

from playwright.async_api import async_playwright

BASE = "http://localhost:8081"
OUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "help")


async def get_exercise_id():
    async with async_session() as s:
        ex = (await s.execute(
            select(Exercise).where(Exercise.name == "Operation Nordlys")
        )).scalar_one()
        return str(ex.id)


async def shot(page, name):
    path = os.path.join(OUT, name)
    await page.screenshot(path=path)
    print("saved", name)


async def settle(page, ms=1200):
    try:
        await page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass
    await page.wait_for_timeout(ms)


async def main():
    os.makedirs(OUT, exist_ok=True)
    ex_id = await get_exercise_id()
    print("exercise", ex_id)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await ctx.new_page()

        # 1. Login page
        await page.goto(f"{BASE}/login")
        await settle(page)
        await shot(page, "01-login.png")

        # Log in as admin
        await page.fill('input[aria-label="Username"]', "admin")
        await page.fill('input[aria-label="Password"]', "admin")
        await page.get_by_role("button", name="Log in").click()
        await settle(page, 1800)
        await shot(page, "02-exercises.png")

        # 3. Exercise detail
        await page.goto(f"{BASE}/exercise/{ex_id}")
        await settle(page)
        await shot(page, "03-exercise-detail.png")

        # 4. Feed
        await page.goto(f"{BASE}/feed/{ex_id}")
        await settle(page, 1800)
        await shot(page, "04-feed.png")

        # 5. Schedule dialog (New social post)
        try:
            await page.get_by_role("button", name="Post", exact=True).first.click()
            await settle(page, 800)
            await shot(page, "05-schedule-post.png")
            await page.keyboard.press("Escape")
            await settle(page, 400)
        except Exception as e:
            print("schedule dialog failed:", e)

        # 6. Markdown help dialog (open News article dialog, click help)
        try:
            await page.get_by_role("button", name="Article", exact=True).first.click()
            await settle(page, 800)
            await page.locator(
                '.q-dialog button:has(i:text-is("help_outline"))'
            ).first.click(force=True)
            await settle(page, 600)
            await shot(page, "06-markdown-help.png")
            await page.keyboard.press("Escape")
            await settle(page, 400)
        except Exception as e:
            print("markdown help failed:", e)

        # 7. Users (superadmin)
        await page.goto(f"{BASE}/users")
        await settle(page)
        await shot(page, "07-users.png")

        # 8. Profile
        await page.goto(f"{BASE}/profile")
        await settle(page)
        await shot(page, "08-profile.png")

        # 9. Persona registry
        await page.goto(f"{BASE}/personas")
        await settle(page)
        await shot(page, "09-personas.png")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
