"""
STANDALONE DESKTOP SCRIPT — Run this from your Windows Command Prompt (not the IDE).
This will open a REAL Chrome window so you can watch what happens live.

HOW TO RUN:
    1. Open Windows Command Prompt (cmd) or PowerShell
    2. cd into your project folder
    3. python run_linkedin_visible.py
    4. A Chrome window will appear -- watch it!
"""
import asyncio
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.async_api import async_playwright
from app.config.mongodb_config import mongodb_client, get_database


async def main():
    await mongodb_client.connect()
    db = await get_database()

    session_doc = await db.linkedin_sessions.find_one(
        {"user_id": "74a8aadf-905b-46fd-9142-1b83cc0fcf80"}
    )
    if not session_doc:
        print("ERROR: No LinkedIn session found. Please reconnect via dashboard first.")
        return

    from app.services.linkedin_outreach_service import _decrypt_cookies

    try:
        cookies_json = _decrypt_cookies(session_doc["cookies_encrypted"])
        cookies = json.loads(cookies_json)
        print(f"Loaded {len(cookies)} cookies from MongoDB\n")
    except Exception as e:
        print(f"ERROR: Could not decrypt cookies: {e}")
        print("You may need to reconnect LinkedIn via dashboard.")
        return

    async with async_playwright() as pw:
        print("Launching Chrome in visible mode...")
        browser = await pw.chromium.launch(
            headless=False,
            channel="chrome",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--start-maximized",
            ],
            slow_mo=200,
        )

        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        )

        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
            "window.chrome = { app: { isInstalled: false }, runtime: {} };"
        )

        await context.add_cookies(cookies)
        print("Cookies injected into browser context\n")

        page = await context.new_page()

        print("TEST 1: Visiting https://www.linkedin.com/feed/ ...")
        try:
            await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"  Feed load issue: {e}")

        print(f"  Current URL: {page.url}")
        await page.screenshot(path="diag_01_feed.png", full_page=True)

        if "linkedin.com/login" in page.url:
            print("  RESULT: Redirected to LOGIN page! Session invalidated in new browser.\n")
        else:
            print("  RESULT: Feed loaded OK -- cookies working!\n")

        target_url = "https://www.linkedin.com/in/pooja-gandhi-06a91916a/"
        print(f"TEST 2: Visiting profile: {target_url}")
        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(4000)
        except Exception as e:
            print(f"  Profile load issue: {e}")

        print(f"  Current URL: {page.url}")
        await page.screenshot(path="diag_02_profile.png", full_page=True)

        if "linkedin.com/login" in page.url:
            print("  RESULT: Profile redirected to LOGIN!\n")
        else:
            print("  Profile loaded OK. Scanning for interactive elements...\n")

            buttons = await page.query_selector_all("button, [role='button']")
            print(f"  Found {len(buttons)} interactive elements. Relevant ones:")
            for btn in buttons:
                try:
                    text = (await btn.inner_text()).strip()[:50]
                    aria = await btn.get_attribute("aria-label") or ""
                    if text and len(text) > 1:
                        print(f"    '{text}' [aria-label: {aria[:50]}]")
                except:
                    pass

            print("\nTEST 3: Looking for Connect button...")
            for sel in [
                "button:has-text('Connect')",
                "[aria-label*='Connect']",
                "button:has-text('Invite')",
                "span:has-text('Connect')",
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=2000):
                        print(f"  FOUND via: {sel}")
                        await page.screenshot(path="diag_03_connect_found.png", full_page=True)
                        print("  Clicking Connect...")
                        await el.click(timeout=5000)
                        await page.wait_for_timeout(3000)
                        await page.screenshot(path="diag_04_after_click.png", full_page=True)
                        break
                except:
                    pass
            else:
                print("  'Connect' not found. Checking for Message/Pending...")
                await page.screenshot(path="diag_03_no_connect.png", full_page=True)

        print("\nDone. Browser will stay open for 30 seconds.")
        print("Screenshots saved to:", os.getcwd())
        await asyncio.sleep(30)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
