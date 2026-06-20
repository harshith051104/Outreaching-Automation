"""
Live Playwright test - opens a VISIBLE browser so you can watch what happens.
Takes screenshots at each step.
"""
import os
import asyncio
import base64
from datetime import datetime
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as pw:
        # 1) Launch CHROME (your real browser, not Chromium) in VISIBLE mode
        browser = await pw.chromium.launch(
            headless=False,
            channel="chrome",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--start-maximized",
            ],
            slow_mo=300,
        )

        # 2) Get cookies from your stored LinkedIn session
        import json
        from app.config.mongodb_config import get_database, mongodb_client
        await mongodb_client.connect()
        db = await get_database()
        session_doc = await db.linkedin_sessions.find_one(
            {"user_id": "74a8aadf-905b-46fd-9142-1b83cc0fcf80"}
        )

        if not session_doc:
            print("No session found! Please reconnect LinkedIn via dashboard first.")
            return

        # Decrypt cookies
        from app.services.linkedin_outreach_service import _decrypt_cookies
        cookies_json = _decrypt_cookies(session_doc["cookies_encrypted"])
        cookies = json.loads(cookies_json)
        print(f"Loaded {len(cookies)} cookies from stored session")

        # 3) Create a SINGLE browser context with YOUR ORIGINAL cookies
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        )

        # Inject the exact stealth script
        await context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = {
              app: { isInstalled: false },
              runtime: {}
            };
            """
        )

        # Add YOUR stored cookies (so LinkedIn thinks you are still logged in)
        await context.add_cookies(cookies)
        print("Cookies injected into fresh browser context")

        # 4) Open a new page and try visiting LinkedIn feed (logged in home)
        page = await context.new_page()

        print("Going to LinkedIn feed...")
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        # Check if we got redirected to login
        if "linkedin.com/login" in page.url:
            print(f"PROBLEM: Redirected to {page.url} - LinkedIn invalidated your session!")
            await _save_screenshot(pw, page, "01_feed_redirected_to_login")
        else:
            print(f"SUCCESS: Stayed on {page.url}")
            await _save_screenshot(pw, page, "01_feed_loaded")

            # Now try visiting a profile
            url = "https://www.linkedin.com/in/pooja-gandhi-06a91916a/"
            print(f"\nNavigating to profile: {url}")
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(4000)
            print(f"Current URL: {page.url}")
            await _save_screenshot(pw, page, "02_profile_loaded")

            # Check for login redirect again
            if "linkedin.com/login" in page.url:
                print("PROBLEM: Profile visit redirected to LOGIN page!")
                print("This means LinkedIn detects the new browser as suspicious.")
            else:
                # Look for the Connect button
                btns = await page.query_selector_all("button, [role='button']")
                print(f"\nFound {len(btns)} interactive elements on page:")
                for btn in btns[:15]:  # limit to first 15
                    try:
                        text = await btn.inner_text()
                        aria = await btn.get_attribute("aria-label") or ""
                        if text.strip() or aria.strip():
                            print(f"  - '{text.strip()[:40]}' (aria-label: {aria[:40]})")
                    except:
                        pass
                await _save_screenshot(pw, page, "03_buttons_scanned")

                # Try to find and click the Connect button
                for sel in [
                    "button:has-text('Connect')",
                    "[aria-label='Connect']",
                    "button:has-text('Invite')",
                    "span:has-text('Connect')",
                ]:
                    try:
                        el = page.locator(sel).first
                        if await el.is_visible(timeout=2000):
                            print(f"\nFound Connect button via: {sel}")
                            await _save_screenshot(pw, page, f"04_found_connect_{sel[:20]}")
                            await el.click(timeout=5000)
                            print("Clicked Connect... waiting 4s for modal")
                            await page.wait_for_timeout(4000)
                            await _save_screenshot(pw, page, "05_after_connect_click")

                            # Now look for the Send/Add note buttons in the modal
                            modal_btns = await page.query_selector_all("button, [role='button']")
                            print(f"\n  Modal has {len(modal_btns)} buttons:")
                            for b in modal_btns[:10]:
                                try:
                                    t = await b.inner_text()
                                    a = await b.get_attribute("aria-label") or ""
                                    if t.strip():
                                        print(f"    - '{t.strip()[:40]}' (aria: {a[:30]})")
                                except:
                                    pass

                            # Try to click Send
                            for send_sel in [
                                "button:has-text('Send')",
                                "button:has-text('Send without a note')",
                                "button:has-text('Done')",
                                "[aria-label*='Send']",
                            ]:
                                try:
                                    s = page.locator(send_sel).first
                                    if await s.is_visible(timeout=2000):
                                        print(f"\nTrying Send button: {send_sel}")
                                        await s.click(timeout=5000)
                                        print("CLICKED SEND!")
                                        await page.wait_for_timeout(3000)
                                        await _save_screenshot(pw, page, "06_after_send_clicked")
                                        break
                                except Exception as e:
                                    print(f"  {send_sel} failed: {e}")
                            break
                    except Exception as e:
                        print(f"  Selector {sel} failed: {e}")

        await browser.close()
        print(f"\nScreenshots saved to: {os.getcwd()}")

async def _save_screenshot(pw, page, name):
    """Save a screenshot with timestamped filename"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"screenshot_{name}_{ts}.png"
    await page.screenshot(path=filename, full_page=True)
    print(f"  Screenshot: {filename}")

if __name__ == "__main__":
    asyncio.run(main())
