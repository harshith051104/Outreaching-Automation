"""
PERSISTENT CHROME PROFILE for LinkedIn automation.

This uses a REAL Chrome user data directory (like your normal Chrome).
Once you log in, the session persists on disk and survives browser restarts.
"""
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from playwright.async_api import async_playwright

# Where to store the persistent Chrome profile (like a real Chrome user)
USER_DATA_DIR = Path(os.path.expanduser("~/.linkedin_bot_profile"))


class LinkedInPersistentBrowser:
    """Manages a persistent Chrome browser for LinkedIn."""

    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None

    async def start(self, headless: bool = False):
        """Start or connect to existing persistent Chrome."""
        # Ensure the profile directory exists
        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

        self.playwright = await async_playwright().start()

        # Launch Chrome with a PERSISTENT profile (user data directory)
        # This is the SAME as your real Chrome - cookies, login sessions,
        # localStorage, IndexedDB, etc. all persist to disk
        self.browser = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            headless=headless,
            channel="chrome",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--start-maximized",
            ],
            ignore_default_args=["--enable-automation"],
            # Keep the browser open even when not active (like real Chrome)
            no_viewport=True,
        )

        # Get or create the first page
        if self.browser.pages:
            self.page = self.browser.pages[0]
        else:
            self.page = await self.browser.new_page()

        print(f"Browser started with persistent profile: {USER_DATA_DIR}")
        print(f"Active pages: {len(self.browser.pages)}")
        return self.page

    async def goto(self, url: str, wait_until: str = "domcontentloaded", timeout: int = 45000):
        """Navigate to a URL."""
        await self.page.goto(url, wait_until=wait_until, timeout=timeout)

    async def screenshot(self, name: str = "screenshot"):
        """Save a screenshot."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{ts}.png"
        await self.page.screenshot(path=filename, full_page=True)
        print(f"Screenshot: {filename}")
        return filename

    async def close(self):
        """Close browser (session stays saved on disk)."""
        await self.browser.close()
        await self.playwright.stop()

    async def check_login_state(self):
        """Check if we're logged in."""
        current_url = self.page.url
        if "linkedin.com/login" in current_url or "linkedin.com/authwall" in current_url:
            return False
        # Also check feed page
        return "linkedin.com/feed" in current_url or "linkedin.com/in/" in current_url


# ========== DEMO: Login and visit profile ==========

async def demo_login_and_visit():
    """Demo: Login once, then visit profiles (session persists)."""
    browser = LinkedInPersistentBrowser()
    page = await browser.start(headless=False)  # Visible so user can watch

    # Step 1: Check if already logged in from a previous run
    print("\n=== Checking if already logged in... ===")
    await browser.goto("https://www.linkedin.com/feed/")
    await asyncio.sleep(3)
    await browser.screenshot("01_feed_check")

    if "linkedin.com/login" in page.url or "linkedin.com/authwall" in page.url:
        print("NOT logged in. Please log in manually in the Chrome window.")
        print("Navigate to linkedin.com, enter your credentials, then press Enter here...")
        input("Press Enter after you've logged in...")
        await asyncio.sleep(2)
    else:
        print(f"Already logged in! URL: {page.url}")

    # Step 2: Visit a profile and look for Connect button
    print("\n=== Visiting profile... ===")
    await browser.goto("https://www.linkedin.com/in/pooja-gandhi-06a91916a/")
    await asyncio.sleep(4)
    await browser.screenshot("02_profile")
    print(f"Current URL: {page.url}")

    # Scan for buttons
    buttons = await page.query_selector_all("button, [role='button']")
    print(f"\nFound {len(buttons)} interactive elements. Relevant ones:")
    for btn in buttons:
        try:
            text = (await btn.inner_text()).strip()[:50]
            aria = await btn.get_attribute("aria-label") or ""
            if text and len(text) > 1:
                print(f"  '{text}' [aria-label: {aria[:50]}]")
        except:
            pass

    # Step 3: Keep alive for inspection
    print("\nBrowser staying open. You can interact with it.")
    print("Press Ctrl+C in this terminal to exit (or close the window).")
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass

    await browser.close()


async def demo_reuse_session():
    """Demo: Reuse existing session without logging in again."""
    browser = LinkedInPersistentBrowser()
    page = await browser.start(headless=False)

    print("\n=== Reusing existing session ===")
    await browser.goto("https://www.linkedin.com/feed/")
    await asyncio.sleep(3)
    await browser.screenshot("03_reuse_feed")

    if "linkedin.com/login" in page.url or "linkedin.com/authwall" in page.url:
        print("Session expired or not logged in. Run demo_login_and_visit() first.")
    else:
        print(f"Session still valid! URL: {page.url}")
        # Now try sending a connection request
        await browser.goto("https://www.linkedin.com/in/pooja-gandhi-06a91916a/")
        await asyncio.sleep(4)
        await browser.screenshot("04_reuse_profile")

    print("\nPress Ctrl+C to exit.")
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass

    await browser.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "reuse":
        asyncio.run(demo_reuse_session())
    else:
        print("Usage:")
        print("  python linkedin_persistent.py        # Login and visit profile")
        print("  python linkedin_persistent.py reuse  # Reuse existing session")
        print()
        asyncio.run(demo_login_and_visit())
