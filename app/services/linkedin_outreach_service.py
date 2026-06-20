"""
LinkedIn Outreach Service — Playwright Browser Automation Layer.

Handles all Playwright browser interactions with LinkedIn:
- Session management (login, cookie persistence, validation)
- Profile scraping
- Connection requests
- Messaging
- Invitation monitoring

Contains ZERO AI logic and ZERO workflow logic.
Only browser automation.
"""

import asyncio
import json
import logging
import random
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from app.config.settings import settings
LINKEDIN_HEADLESS = settings.LINKEDIN_HEADLESS


async def _safe_query_selector_text(page, selectors: List[str], default: str = "") -> str:
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                if text:
                    return text
        except Exception:
            pass
    return default


async def _take_playwright_screenshot(page, prefix: str) -> str:
    """Takes a screenshot of the page and returns the absolute local path to it."""
    try:
        if not page:
            return ""
        import os
        import time
        # Save to app/uploads directory
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        filename = f"error_{prefix}_{int(time.time())}.png"
        file_path = os.path.join(upload_dir, filename)
        await page.screenshot(path=file_path)
        logger.info("Playwright error screenshot captured at %s", file_path)
        return file_path
    except Exception as e:
        logger.warning("Failed to take Playwright screenshot: %s", e)
        return ""

# Playwright is imported lazily to avoid import errors if not installed
_browser_instance = None
_browser_context = None


async def _get_playwright():
    """Lazy-import Playwright to avoid hard dependency at module load."""
    try:
        from playwright.async_api import async_playwright
        return async_playwright
    except ImportError:
        logger.error("Playwright is not installed. Run: pip install playwright && playwright install chromium")
        raise ImportError("Playwright is not installed. Run: pip install playwright && playwright install chromium")


async def _random_delay(min_sec: float = 2.0, max_sec: float = 5.0):
    """Human-like random delay between actions."""
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)


def proactor_isolated(func):
    """
    Decorator that runs an async function in a dedicated thread
    with a ProactorEventLoop on Windows to support subprocesses (required by Playwright).
    """
    from functools import wraps
    import asyncio
    import sys

    def run_in_proactor_loop(*args, **kwargs):
        if sys.platform == "win32":
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            except Exception:
                pass
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(func(*args, **kwargs))
        finally:
            pending = []
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
            except Exception:
                pass
            if pending:
                try:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception:
                    pass
            try:
                loop.close()
            except Exception:
                pass

    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(run_in_proactor_loop, *args, **kwargs)

    return wrapper


async def _launch_stealth_browser(pw, headless: bool = False, slow_mo: int = 0):
    """Launch Chromium browser with stealth parameters to bypass bot detection."""
    args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-infobars",
        "--disable-dev-shm-usage",
        "--disable-gpu",
    ]
    try:
        logger.info("Attempting to launch Playwright with channel='chrome'...")
        return await pw.chromium.launch(
            headless=headless,
            slow_mo=slow_mo,
            channel="chrome",
            args=args,
            ignore_default_args=["--enable-automation"]
        )
    except Exception as exc:
        logger.warning("Failed to launch with channel='chrome', falling back to default chromium: %s", exc)
        return await pw.chromium.launch(
            headless=headless,
            slow_mo=slow_mo,
            args=args,
            ignore_default_args=["--enable-automation"]
        )


async def _create_stealth_context(browser, cookies=None, user_agent=None):
    """Create browser context with stealth properties like custom UA and spoofed navigator.webdriver."""
    default_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ua = user_agent or default_ua
    
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=ua,
    )
    
    if cookies:
        await context.add_cookies(cookies)
        
    # Inject script to override navigator.webdriver, languages, plugins, and spoof chrome APIs
    await context.add_init_script(
        """
        // Delete webdriver property from prototype to bypass 'webdriver in navigator' checks
        try {
            const newProto = Object.getPrototypeOf(navigator);
            delete newProto.webdriver;
            Object.setPrototypeOf(navigator, newProto);
        } catch (e) {}
        
        // Define webdriver as undefined on navigator directly
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        
        // Spoof chrome object to mimic real Google Chrome
        window.chrome = {
          app: {
            isInstalled: false,
            InstallState: {
              DISABLED: 'disabled',
              INSTALLED: 'installed',
              NOT_INSTALLED: 'not_installed'
            },
            RunningState: {
              CANNOT_RUN: 'cannot_run',
              RUNNING: 'running',
              READY_TO_RUN: 'ready_to_run'
            }
          },
          runtime: {
            OnInstalledReason: {
              CHROME_UPDATE: 'chrome_update',
              INSTALL: 'install',
              SHARED_MODULE_UPDATE: 'shared_module_update',
              UPDATE: 'update'
            },
            OnRestartRequiredReason: {
              APP_UPDATE: 'app_update',
              OS_UPDATE: 'os_update',
              PERIODIC: 'periodic'
            },
            PlatformArch: {
              ARM: 'arm',
              ARM64: 'arm64',
              MIPS: 'mips',
              MIPS64: 'mips64',
              X86_32: 'x86_32',
              X86_64: 'x86_64'
            },
            PlatformNaclArch: {
              ARM: 'arm',
              MIPS: 'mips',
              MIPS64: 'mips64',
              X86_32: 'x86_32',
              X86_64: 'x86_64'
            },
            PlatformOs: {
              ANDROID: 'android',
              CROS: 'cros',
              LINUX: 'linux',
              MAC: 'mac',
              OPENBSD: 'openbsd',
              WIN: 'win'
            },
            RequestUpdateCheckStatus: {
              NO_UPDATE: 'no_update',
              THROTTLED: 'throttled',
              UPDATE_AVAILABLE: 'update_available'
            }
          }
        };

        // Spoof plugins
        Object.defineProperty(navigator, 'plugins', {
          get: () => [1, 2, 3, 4, 5]
        });

        // Spoof languages
        Object.defineProperty(navigator, 'languages', {
          get: () => ['en-US', 'en']
        });
        """
    )
    return context


# ── Session Management ─────────────────────────────────────────────────────


@proactor_isolated
async def _start_session_pw() -> Dict[str, Any]:
    """Launch Playwright Chromium and extract cookies after manual login."""
    pw = None
    browser = None
    try:
        async_playwright = await _get_playwright()
        pw = await async_playwright().start()
        browser = await _launch_stealth_browser(pw, headless=False, slow_mo=100)
        context = await _create_stealth_context(browser)
        page = await context.new_page()
        try:
            await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=20000)
        except Exception as e:
            logger.warning("page.goto login timed out: %s", e)
        try:
            await page.wait_for_selector("input#username, input#password", timeout=5000)
        except Exception:
            pass

        # Wait for user to complete login (max 120 seconds)
        try:
            await page.wait_for_url("**/feed/**", timeout=120000)
        except Exception:
            # Check if we're on any authenticated page
            current_url = page.url
            if "linkedin.com/feed" not in current_url and "linkedin.com/in/" not in current_url:
                return {"status": "login_timeout", "cookies": None}

        # Extract profile details
        account_name = None
        avatar_url = None
        try:
            await page.wait_for_selector(".feed-identity-module__name, .feed-identity-module__actor-meta a, img.global-nav__me-photo", timeout=8000)
            name_el = await page.query_selector(".feed-identity-module__name, a.feed-identity-module__actor-link, .feed-identity-module__actor-meta a")
            if name_el:
                account_name = (await name_el.inner_text()).strip()
            if not account_name:
                me_photo = await page.query_selector("img.global-nav__me-photo, .global-nav__me-photo")
                if me_photo:
                    account_name = await me_photo.get_attribute("alt")
                    if account_name:
                        account_name = account_name.strip()
            if account_name:
                account_name = account_name.split('\n')[0].strip()
            me_photo = await page.query_selector("img.global-nav__me-photo, .global-nav__me-photo")
            if me_photo:
                avatar_url = await me_photo.get_attribute("src")
        except Exception as profile_exc:
            logger.warning("Failed to extract logged-in profile name/avatar in login: %s", profile_exc)

        # Extract cookies
        cookies = await context.cookies()
        return {
            "status": "success", 
            "cookies": cookies,
            "account_name": account_name,
            "avatar_url": avatar_url,
        }
    except Exception as exc:
        logger.exception("Failed to start LinkedIn browser session: %s", exc)
        err_msg = str(exc) if str(exc) else f"{type(exc).__name__}"
        return {"status": "error", "message": err_msg, "cookies": None}
    finally:
        try:
            if browser:
                await browser.close()
        except Exception:
            pass
        try:
            if pw:
                await pw.stop()
        except Exception:
            pass


async def run_linkedin_action_in_subprocess(
    action: str,
    user_id: str,
    linkedin_url: Optional[str] = None,
    message: Optional[str] = None,
) -> Dict[str, Any]:
    """Runs a LinkedIn Playwright action in a separate Python process to prevent event loop crashes on Windows."""
    import sys
    import subprocess

    action_timeouts = {
        "send_connection_request": 300,
        "send_message": 90,
        "send_message_by_name": 120,
        "scrape_profile": 120,
        "get_pending_invitations": 120,
        "follow_profile": 120,
        "start_session": 180,
        "validate_session": 60,
    }
    timeout_seconds = action_timeouts.get(action, 240)
    
    def _run():
        cmd = [
            sys.executable,
            "-m", "app.services.linkedin_runner",
            "--action", action,
            "--user-id", user_id,
        ]
        if linkedin_url:
            cmd.extend(["--linkedin-url", linkedin_url])
        if message:
            cmd.extend(["--message", message])
            
        logger.info(f"Spawning child process for LinkedIn action '{action}': {' '.join(cmd)}")
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            )
            try:
                stdout, stderr = process.communicate(timeout=timeout_seconds)
                return type('obj', (object,), {'returncode': process.returncode, 'stdout': stdout, 'stderr': stderr})()
            except subprocess.TimeoutExpired:
                logger.error(f"Subprocess timed out after {timeout_seconds}s for action '{action}'")
                try:
                    process.kill()
                except Exception:
                    pass
                stdout, stderr = process.communicate()
                return type('obj', (object,), {'returncode': -1, 'stdout': stdout, 'stderr': f'Subprocess timed out after {timeout_seconds}s. Stderr: {stderr}'})()
        except Exception as e:
            logger.error(f"Failed to spawn subprocess: {e}")
            return type('obj', (object,), {'returncode': -1, 'stdout': '', 'stderr': str(e)})()
    
    try:
        res = await asyncio.wait_for(asyncio.to_thread(_run), timeout=timeout_seconds + 10)
        
        if res.returncode != 0:
            logger.error(f"Subprocess failed with code {res.returncode}. Stderr: {res.stderr}")
            return {
                "success": False,
                "error": f"Process error (exit code {res.returncode}): {res.stderr.strip()[:500]}"
            }
            
        stdout = res.stdout.strip()
        if not stdout:
            return {"success": False, "error": "Empty response from subprocess"}
            
        marker = "__RESULT__="
        if marker in stdout:
            json_str = stdout.split(marker)[1].strip()
        else:
            json_str = stdout
            
        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, dict) and not parsed.get("success", True):
                logger.error(f"LinkedIn subprocess action '{action}' failed. Subprocess Stderr: {res.stderr}")
            return parsed
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse subprocess JSON output: {e}. Output was: {stdout[:500]}. Stderr was: {res.stderr}")
            return {
                "success": False,
                "error": f"Invalid response from subprocess: {stdout[:200]}"
            }
            
    except asyncio.TimeoutError:
        logger.error(f"Async wait timeout for action '{action}'")
        return {"success": False, "error": f"Request timeout after {timeout_seconds}s"}
    except Exception as e:
        logger.exception(f"Exception running LinkedIn subprocess action '{action}'")
        err_msg = str(e) if str(e) else f"{type(e).__name__}"
        return {"success": False, "error": err_msg}


async def start_session(user_id: str) -> Dict[str, Any]:
    """
    Start a new LinkedIn browser session.
    Delegates to the subprocess runner.
    """
    logger.info("Starting LinkedIn session for user %s via subprocess", user_id)
    return await run_linkedin_action_in_subprocess(
        action="start_session",
        user_id=user_id
    )


@proactor_isolated
async def _validate_session_pw(cookies: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate cookies inside a thread-isolated Playwright instance."""
    pw = None
    browser = None
    try:
        async_playwright = await _get_playwright()
        pw = await async_playwright().start()
        browser = await _launch_stealth_browser(pw, headless=True)
        context = await _create_stealth_context(browser, cookies=cookies)
        page = await context.new_page()
        try:
            await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15000)
        except Exception as e:
            logger.warning("page.goto feed timed out, checking URL anyway: %s", e)
        is_valid = "feed" in page.url and "login" not in page.url
        
        account_name = None
        avatar_url = None
        if is_valid:
            try:
                await page.wait_for_selector(".feed-identity-module__name, .feed-identity-module__actor-meta a, img.global-nav__me-photo", timeout=8000)
                name_el = await page.query_selector(".feed-identity-module__name, a.feed-identity-module__actor-link, .feed-identity-module__actor-meta a")
                if name_el:
                    account_name = (await name_el.inner_text()).strip()
                if not account_name:
                    me_photo = await page.query_selector("img.global-nav__me-photo, .global-nav__me-photo")
                    if me_photo:
                        account_name = await me_photo.get_attribute("alt")
                        if account_name:
                            account_name = account_name.strip()
                if account_name:
                    account_name = account_name.split('\n')[0].strip()
                me_photo = await page.query_selector("img.global-nav__me-photo, .global-nav__me-photo")
                if me_photo:
                    avatar_url = await me_photo.get_attribute("src")
            except Exception as profile_exc:
                logger.warning("Failed to extract logged-in profile name/avatar in validation: %s", profile_exc)
                
        return {
            "valid": is_valid,
            "account_name": account_name,
            "avatar_url": avatar_url,
        }
    except Exception as exc:
        logger.error("Playwright session validation failed: %s", exc)
        return {"valid": False, "account_name": None, "avatar_url": None}
    finally:
        try:
            if browser:
                await browser.close()
        except Exception:
            pass
        try:
            if pw:
                await pw.stop()
        except Exception:
            pass


async def validate_session(user_id: str) -> Dict[str, Any]:
    """
    Validate an existing LinkedIn session.
    Delegates to the subprocess runner.
    """
    logger.info("Validating LinkedIn session for user %s via subprocess", user_id)
    return await run_linkedin_action_in_subprocess(
        action="validate_session",
        user_id=user_id
    )


async def get_session_status(user_id: str) -> Dict[str, Any]:
    """Get the current session status from database."""
    from app.config.mongodb_config import get_database

    db = await get_database()
    session = await db.linkedin_sessions.find_one({"user_id": user_id}, {"_id": 0, "cookies_encrypted": 0})

    if not session:
        return {"status": "disconnected", "last_validated_at": None}

    return {
        "status": session.get("status", "disconnected"),
        "last_validated_at": session.get("last_validated_at"),
        "created_at": session.get("created_at"),
        "account_name": session.get("account_name"),
        "avatar_url": session.get("avatar_url"),
    }


async def disconnect_session(user_id: str) -> Dict[str, Any]:
    """Clear stored session cookies."""
    from app.config.mongodb_config import get_database

    db = await get_database()
    await db.linkedin_sessions.delete_one({"user_id": user_id})
    return {"status": "disconnected", "message": "Session cleared."}


# ── Profile Scraping ───────────────────────────────────────────────────────


async def _scrape_profile_pw(linkedin_url: str, cookies: List[Dict[str, Any]], page=None) -> Dict[str, Any]:
    """Scrape profile using Playwright."""
    pw = None
    browser = None
    try:
        if page is None:
            async_playwright = await _get_playwright()
            pw = await async_playwright().start()
            browser = await _launch_stealth_browser(pw, headless=LINKEDIN_HEADLESS)
            context = await _create_stealth_context(browser, cookies=cookies)
            page = await context.new_page()
        await _random_delay(1.0, 2.0)
        try:
            await page.goto(linkedin_url, wait_until="domcontentloaded", timeout=15000)
        except Exception as e:
            logger.warning("page.goto profile timed out, attempting to proceed anyway: %s", e)
        
        try:
            await page.locator("main.scaffold-layout__main, h1.text-heading-xlarge, div.pv-top-card-v2-section").first.wait_for(state="visible", timeout=8000)
            logger.info("Profile page layout detected as visible for scraping")
        except Exception as e:
            logger.warning("Timed out waiting for profile layout elements: %s", e)
        
        try:
            await page.locator("h1.text-heading-xlarge").first.wait_for(state="visible", timeout=5000)
            logger.info("Profile name heading detected as visible for scraping")
        except Exception as e:
            logger.warning("Timed out waiting for h1.text-heading-xlarge: %s", e)
        
        await _random_delay(1.0, 2.0)  # Let the rest of the profile sections load/render

        # Check if we are logged in / redirected to login
        current_url = page.url
        if "login" in current_url or "signup" in current_url or "checkpoint" in current_url:
            return {"error": "Session expired or invalid. Please reconnect your LinkedIn account."}

        try:
            global_nav = await page.query_selector("#global-nav, .global-nav")
            if not global_nav:
                sign_in_btn = await page.query_selector("a:has-text('Sign in'), button:has-text('Sign in')")
                if sign_in_btn:
                    return {"error": "Session expired or invalid. Please reconnect your LinkedIn account."}
        except Exception:
            pass

        profile_data = {}

        # Click any visible 'see more' or 'Show more' buttons to expand content
        try:
            more_buttons = await page.query_selector_all(
                "button:has-text('see more'), button:has-text('Show more'), .inline-show-more-text__button, button[aria-label*='see more']"
            )
            for btn in more_buttons:
                try:
                    if await btn.is_visible():
                        await btn.click(timeout=1000)
                        await asyncio.sleep(0.3)
                except Exception:
                    pass
        except Exception as e:
            logger.warning("Failed to click 'see more' buttons: %s", e)

        # Scroll down slowly to force lazy-loaded sections (Experience, Education) to render
        try:
            logger.info("Scrolling profile page slowly to trigger lazy loading of sections...")
            for step in range(1, 5):
                await page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {step/8})")
                await asyncio.sleep(0.8)
            
            exp_section = await page.query_selector("section#experience, div#experience, [data-section='experience']")
            if exp_section:
                await exp_section.scroll_into_view_if_needed()
                await asyncio.sleep(1.0)
                
            edu_section = await page.query_selector("section#education, div#education, [data-section='education']")
            if edu_section:
                await edu_section.scroll_into_view_if_needed()
                await asyncio.sleep(0.5)
                
            # Scroll back to top
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(1.0)
        except Exception as e:
            logger.warning("Failed to scroll profile page: %s", e)

        # Extract name using fallback selectors
        name_selectors = ["h1.text-heading-xlarge", ".pv-top-card-layout__title", "main h1", "li.inline.t-24.t-black.t-normal.break-words"]
        profile_data["name"] = await _safe_query_selector_text(page, name_selectors, "Unknown")
        if profile_data["name"] in ("Feed detail update", "Unknown"):
            logger.warning("Name resolved to %s, waiting and retrying name extraction...", profile_data["name"])
            await asyncio.sleep(2)
            profile_data["name"] = await _safe_query_selector_text(page, name_selectors, "Unknown")

        # Extract headline using fallback selectors
        headline_selectors = ["div.text-body-medium", ".text-body-medium.break-words", ".pv-top-card-layout__headline"]
        profile_data["headline"] = await _safe_query_selector_text(page, headline_selectors, "")

        # Extract location using fallback selectors
        location_selectors = ["span.text-body-small.inline", ".pb2.pv-text-details__left-panel span[aria-hidden='true']", ".pv-top-card-layout__secondary-item"]
        profile_data["location"] = await _safe_query_selector_text(page, location_selectors, "")

        # Extract about section using fallback selectors (up to 2000 chars)
        about_selectors = ["section.pv-about-section", "div#about ~ div", "#about ~ .pvs-list__outer-container .visually-hidden"]
        about_text = await _safe_query_selector_text(page, about_selectors, "")
        profile_data["about"] = about_text.strip()[:2000] if about_text else ""


        # Extract experience with robust selectors
        profile_data["experience"] = []
        try:
            # Locate the experience section container
            exp_container = await page.query_selector("section#experience, div#experience")
            if exp_container:
                # Find the main list inside the experience section
                exp_list = await exp_container.query_selector("div.pvs-list__outer-container > ul, ul.pvs-list")
                if exp_list:
                    outer_items = await exp_list.query_selector_all(":scope > li")
                    for item in outer_items[:5]:
                        # Check if this item has a nested list (representing multiple roles at same company)
                        nested_list = await item.query_selector("div.pvs-list__outer-container ul")
                        if nested_list:
                            # 1. Multiple roles at one company
                            # The company name is typically in the first bold span inside the item
                            company_span = await item.query_selector("div.display-flex.flex-column > span.t-bold span[aria-hidden='true'], span.t-bold span[aria-hidden='true']")
                            company_name = (await company_span.inner_text()).strip() if company_span else "Unknown"
                            
                            # Clean up company name (split by dot or newlines)
                            if company_name:
                                company_name = company_name.split("·")[0].strip()
                                company_name = company_name.split("\n")[0].strip()
                                
                            # Now parse each nested role
                            nested_items = await nested_list.query_selector_all(":scope > li")
                            for n_item in nested_items:
                                # Title of the role is in the first bold span inside the nested item
                                title_span = await n_item.query_selector("span.t-bold span[aria-hidden='true'], span[aria-hidden='true']")
                                title = (await title_span.inner_text()).strip() if title_span else ""
                                
                                # Duration can be found in the second line (t-14 t-normal t-black--light)
                                duration_span = await n_item.query_selector("span.t-14.t-normal span[aria-hidden='true']")
                                duration = (await duration_span.inner_text()).strip() if duration_span else ""
                                
                                if title:
                                    profile_data["experience"].append({
                                        "title": title,
                                        "company": company_name or "Unknown",
                                        "duration": duration,
                                    })
                        else:
                            # 2. Single role at a company
                            # Title is usually the first bold span
                            title_span = await item.query_selector("div.display-flex.flex-column > span.t-bold span[aria-hidden='true'], span.t-bold span[aria-hidden='true']")
                            title = (await title_span.inner_text()).strip() if title_span else ""
                            
                            # Company name is the second line (t-14 t-normal)
                            company_span = await item.query_selector("span.t-14.t-normal span[aria-hidden='true']")
                            company_raw = (await company_span.inner_text()).strip() if company_span else ""
                            
                            company_name = "Unknown"
                            duration = ""
                            if company_raw:
                                parts = company_raw.split("·")
                                company_name = parts[0].strip()
                                company_name = company_name.split("\n")[0].strip()
                            
                            # Duration is usually in the third line (t-14 t-normal t-black--light)
                            duration_span = await item.query_selector("span.t-14.t-normal.t-black--light span[aria-hidden='true']")
                            if duration_span:
                                duration = (await duration_span.inner_text()).strip()
                                
                            if title:
                                profile_data["experience"].append({
                                    "title": title,
                                    "company": company_name or "Unknown",
                                    "duration": duration,
                                })
                                
            # Fallback to flatter extraction if hierarchical extraction yielded nothing
            if not profile_data["experience"]:
                exp_items = await page.query_selector_all(
                    "li.artdeco-list__item[class*='experience'], "
                    "section#experience ~ div.pvs-list__outer-container ul.pvs-list > li, "
                    "section#experience ~ div li"
                )
                for item in exp_items[:5]:
                    title_el = await item.query_selector("span[aria-hidden='true'], div.display-flex.align-items-center span")
                    title = (await title_el.inner_text()).strip() if title_el else ""
                    
                    company_el = await item.query_selector(
                        "span.t-14.t-normal span[aria-hidden='true'], "
                        "span.t-14.t-normal:has-text(' · ') span[aria-hidden='true'], "
                        "div.pv-entity__summary-info p.pv-entity__secondary-title"
                    )
                    company = ""
                    if company_el:
                        company = (await company_el.inner_text()).strip()
                    else:
                        company_container = await item.query_selector("span.t-14.t-normal")
                        if company_container:
                            company = (await company_container.inner_text()).strip()
                    
                    if company:
                        company = company.split("·")[0].strip()
                        company = company.split("\n")[0].strip()
                    
                    if title and not company:
                        nested_company = await item.query_selector("span.t-14.t-normal.t-black--light span")
                        if nested_company:
                            company = (await nested_company.inner_text()).strip()
                    
                    if title:
                        profile_data["experience"].append({
                            "title": title,
                            "company": company or "Unknown",
                            "duration": "",
                        })
        except Exception as e:
            logger.warning("Failed to extract experience: %s", e)

        # Fallback for current company from top card details panel
        current_company_selectors = [
            "div.pv-text-details__right-panel button[aria-label*='company' i]",
            "div.pv-text-details__right-panel li",
            "button[data-field='experience_company']",
            ".pv-text-details__right-panel-item"
        ]
        current_company = ""
        for sel in current_company_selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    txt = (await el.inner_text()).strip()
                    if txt:
                        current_company = txt
                        break
            except Exception:
                pass
        
        # If no experience was scraped but we found a current company in the top card, populate it
        if not profile_data["experience"] and current_company:
            profile_data["experience"].append({
                "title": profile_data.get("headline", "Professional"),
                "company": current_company,
                "duration": ""
            })

        # Extract education
        profile_data["education"] = []
        try:
            edu_items = await page.query_selector_all("section#education ~ div li")
            for item in edu_items[:3]:
                school_el = await item.query_selector("span[aria-hidden='true']")
                school = (await school_el.inner_text()).strip() if school_el else ""
                if school:
                    profile_data["education"].append({"school": school, "degree": "", "field": ""})
        except Exception:
            pass

        profile_data["skills"] = []
        profile_data["connection_count"] = ""
        profile_data["profile_url"] = linkedin_url

        logger.info("Successfully scraped profile: %s", profile_data.get("name", "Unknown"))
        return profile_data

    except Exception as exc:
        logger.exception("Profile scraping failed: %s", exc)
        scr_path = ""
        try:
            scr_path = await _take_playwright_screenshot(page, "scrape")
        except Exception:
            pass
        err_msg = str(exc) if str(exc) else f"{type(exc).__name__}"
        return {
            "error": err_msg,
            "error_screenshot_path": scr_path,
            "name": "Unknown",
            "headline": "",
            "about": "",
            "location": "",
            "experience": [],
            "education": [],
            "skills": [],
            "connection_count": "",
            "profile_url": linkedin_url
        }
    finally:
        if pw:
            try:
                if browser:
                    await browser.close()
            except Exception:
                pass
            try:
                if pw:
                    await pw.stop()
            except Exception:
                pass


async def scrape_profile(linkedin_url: str, user_id: str) -> Dict[str, Any]:
    """
    Scrape a LinkedIn profile page.
    Delegates to the subprocess runner.
    """
    try:
        from app.config.mongodb_config import get_database
        db = await get_database()
        session = await db.linkedin_sessions.find_one({"user_id": user_id})
    except Exception as mongo_err:
        logger.warning("MongoDB unavailable for session lookup: %s", mongo_err)
        session = None

    if not session or session.get("status") != "connected":
        return {"error": "No active LinkedIn session. Please reconnect your LinkedIn account."}

    return await run_linkedin_action_in_subprocess(
        action="scrape_profile",
        user_id=user_id,
        linkedin_url=linkedin_url
    )


# ── Following Profiles & Companies ─────────────────────────────────────────


async def _find_and_click_follow_button(page, containers: List[str]) -> bool:
    """Helper to locate and click the 'Follow' button on a LinkedIn profile or company page."""
    import re
    follow_clicked = False

    # Strategy A: Use Playwright get_by_role Follow button
    for container in containers:
        try:
            if container:
                parent = page.locator(container).first
                if await parent.is_visible(timeout=2000):
                    loc = parent.get_by_role("button", name="Follow", exact=True).first
            else:
                loc = page.get_by_role("button", name="Follow", exact=True).first
            
            if loc and await loc.is_visible(timeout=2000):
                await loc.scroll_into_view_if_needed()
                await loc.click(force=True, timeout=3000)
                follow_clicked = True
                logger.info("Follow button clicked using Strategy A (get_by_role Follow, container: %s)", container)
                break
        except Exception:
            pass

    # Strategy B: Try get_by_role with regex Follow
    if not follow_clicked:
        for container in containers:
            try:
                if container:
                    parent = page.locator(container).first
                    if await parent.is_visible(timeout=2000):
                        loc = parent.get_by_role("button", name=re.compile(r"Follow", re.IGNORECASE)).first
                else:
                    loc = page.get_by_role("button", name=re.compile(r"Follow", re.IGNORECASE)).first
                
                if loc and await loc.is_visible(timeout=2000):
                    await loc.scroll_into_view_if_needed()
                    await loc.click(force=True, timeout=3000)
                    follow_clicked = True
                    logger.info("Follow button clicked using Strategy B (get_by_role regex Follow, container: %s)", container)
                    break
            except Exception:
                pass

    # Strategy C: Direct aria-label containing "Follow"
    if not follow_clicked:
        aria_pats = [
            "button[aria-label*='Follow']",
            "button[aria-label*='follow']",
        ]
        for container in containers:
            for aria_pat in aria_pats:
                selector = f"{container} {aria_pat}".strip() if container else aria_pat
                loc = page.locator(selector).first
                try:
                    await loc.wait_for(state="visible", timeout=2000)
                    await loc.scroll_into_view_if_needed()
                    await loc.click(force=True, timeout=3000)
                    follow_clicked = True
                    logger.info("Follow button clicked using Strategy C (aria-label: %s)", selector)
                    break
                except Exception:
                    continue
            if follow_clicked:
                break

    # Strategy D: Visible button whose text contains Follow
    if not follow_clicked:
        pats = [
            "button:has-text('Follow')",
            "span.artdeco-button__text:has-text('Follow')",
            "a:has-text('Follow')",
        ]
        for container in containers:
            for pat in pats:
                selector = f"{container} {pat}".strip() if container else pat
                loc = page.locator(selector).first
                try:
                    await loc.wait_for(state="visible", timeout=2000)
                    await loc.scroll_into_view_if_needed()
                    await loc.click(force=True, timeout=3000)
                    follow_clicked = True
                    logger.info("Follow button clicked using Strategy D (has-text: %s)", selector)
                    break
                except Exception:
                    continue
            if follow_clicked:
                break

    # Strategy E: "More actions" dropdown → "Follow" menu item
    if not follow_clicked:
        more_selectors = [
            "button[aria-label='More actions']",
            "button[aria-label='More']",
            "button[aria-label*='More actions']",
            "button[aria-label*='More']",
            "button[aria-label*='actions']",
            "button:has-text('More actions')",
            "button:has-text('More')",
            "button.pv-s-profile-actions__overflow-toggle",
            "button.artdeco-dropdown__trigger",
            "button.artdeco-button--2",
            "div.pvs-profile-actions button[aria-haspopup='menu']",
            "div.pvs-profile-actions button:has-text('More')"
        ]
        for container in containers:
            for selector in more_selectors:
                sel = f"{container} {selector}".strip() if container else selector
                more_loc = page.locator(sel).first
                try:
                    await more_loc.wait_for(state="visible", timeout=5000)
                    await more_loc.scroll_into_view_if_needed()
                    await more_loc.click(force=True, timeout=8000)
                    await _random_delay(2.0, 4.0)

                    menu_follow_selectors = [
                        "div[role='menu'] *[role='menuitem']:has-text('Follow')",
                        "div[role='menu'] button:has-text('Follow')",
                        "div[role='menu'] span:has-text('Follow')",
                        "div[role='menu'] div:has-text('Follow')",
                        "div.artdeco-dropdown__content *[role='menuitem']:has-text('Follow')",
                        "div.artdeco-dropdown__content button:has-text('Follow')",
                        "div.artdeco-dropdown__content span:has-text('Follow')",
                        "div.artdeco-dropdown__content div:has-text('Follow')",
                        "*[role='menuitem'] span:has-text('Follow')",
                        "*[role='menuitem'] button:has-text('Follow')",
                        "*[role='menuitem']:has-text('Follow')",
                        "span:has-text('Follow')",
                        "button:has-text('Follow')",
                        "div:has-text('Follow')"
                    ]
                    for menu_sel in menu_follow_selectors:
                        follow_item = page.locator(menu_sel).first
                        try:
                            if await follow_item.is_visible(timeout=5000):
                                await follow_item.scroll_into_view_if_needed()
                                await follow_item.click(force=True, timeout=5000)
                                follow_clicked = True
                                logger.info("Follow button clicked using Strategy E (%s)", menu_sel)
                                await _random_delay(1.5, 3.0)
                                break
                        except Exception as e:
                            logger.debug("Failed menu follow click for selector %s: %s", menu_sel, e)
                            continue

                    if follow_clicked:
                        break
                except Exception as e:
                    logger.debug("Failed 'More' button click flow: %s", e)
                    continue
            if follow_clicked:
                break

    # Strategy F: Try clicking any button with "Follow" in aria-label or title
    if not follow_clicked:
        for container in containers:
            try:
                sel = f"{container} button[title*='Follow']".strip() if container else "button[title*='Follow']"
                loc = page.locator(sel).first
                if await loc.is_visible(timeout=2000):
                    await loc.click(timeout=3000)
                    follow_clicked = True
                    logger.info("Follow button clicked using Strategy F (title attribute)")
                    break
            except Exception:
                pass

    return follow_clicked


async def _follow_profile_pw(linkedin_url: str, cookies: List[Dict[str, Any]], page=None) -> Dict[str, Any]:
    """Follow a profile or company using Playwright."""
    pw = None
    browser = None
    try:
        if page is None:
            async_playwright = await _get_playwright()
            pw = await async_playwright().start()
            browser = await _launch_stealth_browser(pw, headless=LINKEDIN_HEADLESS)
            context = await _create_stealth_context(browser, cookies=cookies)
            page = await context.new_page()
        await _random_delay(2, 4)
        try:
            await page.goto(linkedin_url, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            logger.warning("page.goto follow profile timed out, attempting to proceed anyway: %s", e)
        await _random_delay(2, 5)
        try:
            await page.locator("main.scaffold-layout__main, div.pv-top-card-v2-section, .pvs-profile-actions, .global-nav, .org-top-card").first.wait_for(state="visible", timeout=20000)
            logger.info("Page layout detected as visible for follow")
        except Exception as e:
            logger.warning("Timed out waiting for layout elements: %s", e)

        # Check if we are logged in / redirected to login
        current_url = page.url
        if "login" in current_url or "signup" in current_url or "checkpoint" in current_url:
            return {"success": False, "error": "Session expired or invalid. Please reconnect your LinkedIn account."}

        try:
            global_nav = await page.query_selector("#global-nav, .global-nav")
            if not global_nav:
                sign_in_btn = await page.query_selector("a:has-text('Sign in'), button:has-text('Sign in')")
                if sign_in_btn:
                    return {"success": False, "error": "Session expired or invalid. Please reconnect your LinkedIn account."}
        except Exception:
            pass

        # Check if already following
        already_following_selectors = [
            "button:has-text('Following')",
            "span:has-text('Following')",
            "button[aria-label*='Following']",
            "span.artdeco-button__text:has-text('Following')",
            "button:has-text('Unfollow')",
        ]
        for sel in already_following_selectors:
            try:
                loc = page.locator(sel).first
                if await loc.is_visible(timeout=1000):
                    logger.info("Already following profile/company")
                    return {
                        "success": True,
                        "action": "follow_profile",
                        "linkedin_url": linkedin_url,
                        "message": "Already following"
                    }
            except Exception:
                pass

        # Containers to search inside first, falling back to page-wide (empty string)
        containers = [
            "div.org-top-card-primary-actions__actions",
            ".org-top-card-actions",
            "div.pvs-profile-actions",
            "div.pv-top-card-v2-section__actions",
            "div.pv-top-card-layout__actions",
            ".pv-top-card-v2-section",
            "main.scaffold-layout__main section.artdeco-card",
            ""
        ]

        follow_clicked = await _find_and_click_follow_button(page, containers)

        if not follow_clicked:
            scr_path = ""
            try:
                scr_path = await _take_playwright_screenshot(page, "follow_failed")
            except Exception:
                pass
            return {
                "success": False,
                "error": "Follow button not found. User may already be followed/connected, or button selector mismatch.",
                "error_screenshot_path": scr_path
            }

        await _random_delay(2, 4)
        return {
            "success": True,
            "action": "follow_profile",
            "linkedin_url": linkedin_url,
            "message": "Successfully followed profile/company"
        }
    except Exception as exc:
        logger.exception("Playwright follow failed: %s", exc)
        err_msg = str(exc) if str(exc) else f"{type(exc).__name__}"
        return {"success": False, "error": err_msg}
    finally:
        if pw:
            try:
                if browser:
                    await browser.close()
            except Exception:
                pass
            try:
                if pw:
                    await pw.stop()
            except Exception:
                pass


async def follow_profile(linkedin_url: str, user_id: str) -> Dict[str, Any]:
    """
    Follow a LinkedIn profile or company.
    Delegates to the subprocess runner.
    """
    from app.config.mongodb_config import get_database

    db = await get_database()
    session = await db.linkedin_sessions.find_one({"user_id": user_id})

    if not session or session.get("status") != "connected":
        return {"success": False, "error": "No active LinkedIn session."}

    return await run_linkedin_action_in_subprocess(
        action="follow_profile",
        user_id=user_id,
        linkedin_url=linkedin_url
    )


# ── Connection Requests ────────────────────────────────────────────────────


async def _find_and_click_connect_button(page) -> tuple[bool, int | None, str | None]:
    """
    Locate and click the LinkedIn 'Connect' button, strictly scoped to the profile card.
    Supports Scenarios 1, 2, and 3.
    Returns:
        (connect_clicked, scenario, error_reason)
    """
    connect_clicked = False
    scenario = None
    error_reason = None

    # Find the first visible profile top card action area
    action_area_selectors = [
        "div.pvs-profile-actions",
        "div.pv-top-card-v2-section__actions",
        "div.pv-top-card-layout__actions",
        ".pv-top-card-v2-section",
        "main.scaffold-layout__main section.artdeco-card"
    ]
    
    active_area = None
    for area_sel in action_area_selectors:
        try:
            loc = page.locator(area_sel).first
            if await loc.is_visible(timeout=1000):
                active_area = loc
                logger.info("Found visible profile action area: %s", area_sel)
                break
        except Exception:
            pass

    # If no action area is found, fall back to page
    if not active_area:
        logger.warning("No profile action area found! Falling back to page-wide search.")
        active_area = page

    # Let's check for a direct 'Connect' button (Scenario 1)
    connect_btn = None
    connect_selectors = [
        "button[aria-label*='Invite'][aria-label*='connect']",
        "button[aria-label*='Connect']",
        "button[aria-label*='connect']",
        "button[aria-label*='Invite']",
        "button:has-text('Connect')",
        "button:has-text('Invite')",
    ]
    for sel in connect_selectors:
        try:
            loc = active_area.locator(sel).first
            if await loc.is_visible(timeout=500):
                connect_btn = loc
                break
        except Exception:
            pass

    # Let's check for a direct 'Follow' button (Scenario 2 candidate)
    follow_btn = None
    follow_selectors = [
        "button:has-text('Follow')",
        "button[aria-label*='Follow']",
        "button[aria-label*='follow']",
    ]
    for sel in follow_selectors:
        try:
            loc = active_area.locator(sel).first
            if await loc.is_visible(timeout=500):
                text = await loc.inner_text()
                if "following" not in text.lower():
                    follow_btn = loc
                    break
        except Exception:
            pass

    if connect_btn:
        # Scenario 1: Connect Button Visible
        scenario = 1
        logger.info("Scenario 1: Direct Connect button visible.")
        try:
            await _take_playwright_screenshot(page, "before_click_direct")
            await connect_btn.scroll_into_view_if_needed()
            await connect_btn.click(force=True, timeout=3000)
            await _random_delay(1.5, 2.5)
            await _take_playwright_screenshot(page, "after_click_direct")
            connect_clicked = True
            logger.info("Scenario 1: Connect button clicked directly.")
        except Exception as e:
            logger.exception("Failed to click direct Connect button: %s", e)
            error_reason = f"Scenario 1 click failed: {str(e)}"
    
    elif follow_btn:
        # Scenario 2: Follow Button Visible
        scenario = 2
        logger.info("Scenario 2: Follow button visible. Clicking Follow first...")
        try:
            await _take_playwright_screenshot(page, "before_click_follow")
            await follow_btn.scroll_into_view_if_needed()
            await follow_btn.click(force=True, timeout=3000)
            await _random_delay(2.0, 3.0)
            await _take_playwright_screenshot(page, "after_click_follow")

            # Click More menu
            more_btn = None
            more_selectors = [
                "button[aria-label='More actions']",
                "button:has-text('More')",
                "button[aria-label='More']",
            ]
            for more_sel in more_selectors:
                loc = active_area.locator(more_sel).first
                if await loc.is_visible(timeout=1000):
                    more_btn = loc
                    break
            
            if more_btn:
                await more_btn.click(force=True, timeout=3000)
                logger.info("Scenario 2: Clicked More dropdown.")
                await _random_delay(1.5, 2.5)
                await _take_playwright_screenshot(page, "after_more_click_scenario_2")

                # Find Connect option in the dropdown list
                dropdown_connect_selectors = [
                    "div[role='menu'] *:has-text('Connect')",
                    "div.artdeco-dropdown__content *:has-text('Connect')",
                    "ul.artdeco-dropdown__content-inner li:has-text('Connect')",
                    "*[role='menuitem']:has-text('Connect')",
                    "li:has-text('Connect')",
                    "span:has-text('Connect')",
                ]
                for conn_sel in dropdown_connect_selectors:
                    try:
                        conn_loc = page.locator(conn_sel).first
                        if await conn_loc.is_visible(timeout=1000):
                            await conn_loc.click(force=True, timeout=3000)
                            connect_clicked = True
                            logger.info("Scenario 2: Clicked Connect inside More dropdown (%s)", conn_sel)
                            await _random_delay(1.5, 2.5)
                            await _take_playwright_screenshot(page, "after_connect_click_scenario_2")
                            break
                    except Exception:
                        pass
                
                if not connect_clicked:
                    error_reason = "Connect option not found in More dropdown (Scenario 2)"
                    # Close dropdown if it didn't succeed
                    try:
                        await page.keyboard.press("Escape")
                        await _random_delay(0.3, 0.5)
                    except Exception:
                        pass
            else:
                error_reason = "More button not found (Scenario 2)"
        except Exception as e:
            logger.exception("Scenario 2 execution failed: %s", e)
            error_reason = f"Scenario 2 failed: {str(e)}"

    else:
        # Scenario 3: Connect Hidden in More Menu
        scenario = 3
        logger.info("Scenario 3: Connect hidden in More menu.")
        try:
            # Click More menu
            more_btn = None
            more_selectors = [
                "button[aria-label='More actions']",
                "button:has-text('More')",
                "button[aria-label='More']",
            ]
            for more_sel in more_selectors:
                loc = active_area.locator(more_sel).first
                if await loc.is_visible(timeout=1000):
                    more_btn = loc
                    break
            
            if more_btn:
                await more_btn.click(force=True, timeout=3000)
                logger.info("Scenario 3: Clicked More dropdown.")
                await _random_delay(1.5, 2.5)
                await _take_playwright_screenshot(page, "after_more_click_scenario_3")

                # Find Connect option in the dropdown list
                dropdown_connect_selectors = [
                    "div[role='menu'] *:has-text('Connect')",
                    "div.artdeco-dropdown__content *:has-text('Connect')",
                    "ul.artdeco-dropdown__content-inner li:has-text('Connect')",
                    "*[role='menuitem']:has-text('Connect')",
                    "li:has-text('Connect')",
                    "span:has-text('Connect')",
                ]
                for conn_sel in dropdown_connect_selectors:
                    try:
                        conn_loc = page.locator(conn_sel).first
                        if await conn_loc.is_visible(timeout=1000):
                            await conn_loc.click(force=True, timeout=3000)
                            connect_clicked = True
                            logger.info("Scenario 3: Clicked Connect inside More dropdown (%s)", conn_sel)
                            await _random_delay(1.5, 2.5)
                            await _take_playwright_screenshot(page, "after_connect_click_scenario_3")
                            break
                    except Exception:
                        pass
                
                if not connect_clicked:
                    error_reason = "Connect option not found in More dropdown"
                    # Close dropdown if it didn't succeed
                    try:
                        await page.keyboard.press("Escape")
                        await _random_delay(0.3, 0.5)
                    except Exception:
                        pass
            else:
                error_reason = "More button not found"
        except Exception as e:
            logger.exception("Scenario 3 execution failed: %s", e)
            error_reason = f"Scenario 3 failed: {str(e)}"

    return connect_clicked, scenario, error_reason





async def _send_connection_request_pw(linkedin_url: str, note: str, cookies: List[Dict[str, Any]], page=None) -> Dict[str, Any]:
    """Send connection request using Playwright."""
    # Force 'Send without a note' by clearing the note for the Playwright invitation dialog itself
    note = ""
    pw = None
    browser = None
    try:
        if page is None:
            logger.info("Playwright helper: starting async_playwright...")
            async_playwright = await _get_playwright()
            pw = await async_playwright().start()
            logger.info("Playwright helper: async_playwright started, launching browser...")
            browser = await _launch_stealth_browser(pw, headless=LINKEDIN_HEADLESS)
            logger.info("Playwright helper: browser launched, creating context...")
            context = await _create_stealth_context(browser, cookies=cookies)
            logger.info("Playwright helper: context created, creating new page...")
            page = await context.new_page()
            logger.info("Playwright helper: new page created successfully")
        await _random_delay(1, 2)
        try:
            logger.info("Playwright helper: navigating to profile URL %s ...", linkedin_url)
            await page.goto(linkedin_url, wait_until="domcontentloaded", timeout=45000)
            logger.info("Playwright helper: navigation completed")
        except Exception as e:
            logger.warning("page.goto connection profile timed out, attempting to proceed anyway: %s", e)
        await _random_delay(1, 2)
        try:
            await page.locator("main.scaffold-layout__main, div.pv-top-card-v2-section, .pvs-profile-actions, .global-nav").first.wait_for(state="visible", timeout=15000)
            logger.info("Profile page layout detected as visible")
        except Exception as e:
            logger.warning("Timed out waiting for profile layout elements: %s", e)

        # Check if we are logged in / redirected to login
        current_url = page.url
        if "login" in current_url or "signup" in current_url or "checkpoint" in current_url:
            return {"success": False, "error": "Session expired or invalid. Please reconnect your LinkedIn account."}

        try:
            global_nav = await page.query_selector("#global-nav, .global-nav")
            if not global_nav:
                sign_in_btn = await page.query_selector("a:has-text('Sign in'), button:has-text('Sign in')")
                if sign_in_btn:
                    return {"success": False, "error": "Session expired or invalid. Please reconnect your LinkedIn account."}
        except Exception:
            pass

        # --- Robust Connect button detection (Scenario 1, 2, and 3) ---
        connect_clicked, scenario, error_reason = await _find_and_click_connect_button(page)

        # Strategy G: Handle "Pending" connection status - request already sent
        if not connect_clicked:
            try:
                pending_selectors = [
                    "button:has-text('Pending')",
                    "span:has-text('Pending')",
                    "button[aria-label*='Pending']",
                ]
                for sel in pending_selectors:
                    loc = page.locator(sel).first
                    if await loc.is_visible(timeout=500):
                        logger.info("Connection already pending, treating as success")
                        return {
                            "success": True,
                            "action": "connection_sent",
                            "linkedin_url": linkedin_url,
                            "note_sent": False,
                            "note_content": "",
                            "message": "Connection request already pending"
                        }
            except Exception:
                pass

        # Strategy H: Explicit "already connected" check (1st degree or "Connected" button)
        if not connect_clicked:
            try:
                page_text = await page.inner_text("body")
                # Look for definitive connected signals
                connected_button = await page.query_selector(
                    "button:has-text('Connected'), span:has-text('· 1st ·'), span:has-text('· 1st·')"
                )
                is_first_degree = "· 1st ·" in page_text or "·1st·" in page_text or "\u00b7 1st \u00b7" in page_text
                if connected_button or is_first_degree:
                    logger.info("Profile confirmed as already connected (1st degree / Connected button).")
                    return {
                        "success": True,
                        "action": "already_connected",
                        "linkedin_url": linkedin_url,
                        "note_sent": False,
                        "note_content": "",
                        "message": "Already connected with this person"
                    }
            except Exception:
                pass

        # Strategy I: Try to Follow (if Connect is not available)
        if not connect_clicked:
            try:
                follow_selectors = [
                    "button:has-text('Follow')",
                    "button[aria-label*='Follow']",
                    "span:has-text('Follow')",
                ]
                for sel in follow_selectors:
                    try:
                        loc = page.locator(sel).first
                        if await loc.is_visible(timeout=2000):
                            await loc.click(timeout=5000)
                            return {
                                "success": True,
                                "action": "followed",
                                "linkedin_url": linkedin_url,
                                "note_sent": False,
                                "note_content": "",
                                "message": "Followed the profile (no Connect button available)"
                            }
                    except Exception:
                        pass
            except Exception:
                pass

        if not connect_clicked:
            scr_path = ""
            try:
                scr_path = await _take_playwright_screenshot(page, "connect_failed")
            except Exception:
                pass
            return {
                "success": False,
                "error": error_reason or "Connect button not found. User may already be connected or button selector mismatch.",
                "reason": "unavailable" if error_reason and ("Connect option not found in More dropdown" in error_reason or "More button not found" in error_reason) else "failed",
                "error_screenshot_path": scr_path
            }

        await _random_delay(1.5, 2.5)

        # Check for LinkedIn modals / dialogs (e.g. 'How do you know this person?', 'Premium upsell')
        out_of_notes = False
        send_clicked = False
        try:
            modal_loc = page.locator("div.artdeco-modal, div[role='dialog']").first
            if await modal_loc.is_visible(timeout=3000):
                await _take_playwright_screenshot(page, "modal_visible")
                modal_text = await modal_loc.inner_text()
                logger.info("LinkedIn modal text detected: %s", modal_text[:200])

                # 1. Handle 'How do you know' modal
                if "How do you know" in modal_text or "know each other" in modal_text or "Select a connection type" in modal_text:
                    logger.info("Handling 'How do you know this person' modal...")
                    other_selectors = [
                        "button:has-text('Other')",
                        "span:has-text('Other')",
                        "label:has-text('Other')",
                        "input[value='other']",
                    ]
                    clicked_option = False
                    for opt_sel in other_selectors:
                        try:
                            opt_loc = modal_loc.locator(opt_sel).first
                            if await opt_loc.is_visible(timeout=1000):
                                await opt_loc.click()
                                clicked_option = True
                                logger.info("Selected 'Other' option using: %s", opt_sel)
                                break
                        except Exception:
                            pass
                    
                    next_selectors = [
                        "button:has-text('Connect')",
                        "button:has-text('Next')",
                        "button.artdeco-button--primary",
                    ]
                    for next_sel in next_selectors:
                        try:
                            next_loc = modal_loc.locator(next_sel).first
                            if await next_loc.is_visible(timeout=1000):
                                await next_loc.click()
                                logger.info("Clicked Next/Connect button on 'How do you know' modal: %s", next_sel)
                                await _random_delay(2.0, 3.0)  # Wait for note modal to load
                                await _take_playwright_screenshot(page, "after_how_do_you_know_modal")
                                break
                        except Exception:
                            pass
                    
                    # Refresh modal ref after transition
                    modal_loc = page.locator("div.artdeco-modal, div[role='dialog']").first
                    if await modal_loc.is_visible(timeout=1000):
                        modal_text = await modal_loc.inner_text()

                # 2. Check for Premium upsell modal
                if "out of free custom notes" in modal_text or "personalized invites with Premium" in modal_text or "invites with Premium" in modal_text or "reached the limit" in modal_text:
                    logger.warning("LinkedIn Premium upsell modal detected before adding note. Attempting to send without a note directly...")
                    out_of_notes = True
                    
                    # Try to find and click "Send without note" / "Send without a note" button first
                    send_without_note_selectors = [
                        "button:has-text('Send without note')",
                        "button:has-text('Send without a note')",
                        "button[aria-label*='without note']",
                        "button[aria-label*='without a note']",
                        "div.artdeco-modal button:has-text('Send without note')",
                        "div.artdeco-modal button:has-text('Send without a note')"
                    ]
                    
                    clicked_direct = False
                    for selector in send_without_note_selectors:
                        btn = page.locator(selector).first
                        try:
                            if await btn.is_visible(timeout=1000):
                                await btn.click(timeout=1000)
                                send_clicked = True
                                clicked_direct = True
                                logger.info("Clicked 'Send without note' directly on Premium modal using: %s", selector)
                                break
                        except Exception:
                            continue
                            
                    if not clicked_direct:
                        logger.warning("Could not click 'Send without note' directly. Closing the Premium modal.")
                        try:
                            close_btn = modal_loc.locator("button[aria-label='Dismiss'], button[aria-label='Close'], button.artdeco-modal__dismiss").first
                            if await close_btn.is_visible(timeout=1000):
                                await close_btn.click()
                                await _random_delay(1, 2)
                        except Exception:
                            pass
        except Exception as e:
            logger.debug("Error checking modal dialogs: %s", e)

        # Scoped selectors for the send invitation modal/dialog
        add_note_selectors = [
            "button:has-text('Add a note')",
            "button:has-text('Add note')",
            "button[aria-label*='Add a note']",
            "button[aria-label*='Add note']",
            "button[aria-label*='note']",
            "div.artdeco-modal button:has-text('Add a note')",
            "div[role='dialog'] button:has-text('Add a note')",
            "button:has-text('Note')",
            "span:has-text('Add a note')"
        ]

        note_input_selectors = [
            "#custom-message",
            "#compose-form textarea",
            "div.artdeco-modal textarea",
            "div[role='dialog'] textarea",
            "textarea[name='message']",
            "textarea[placeholder*='note' i]",
            "textarea[placeholder*='message' i]",
            "textarea.send-invite__custom-message",
            "div.connection-note-input textarea",
            "section.invite-custom-note textarea",
            "textarea.invite-custom-note"
        ]

        send_selectors = [
            "button:has-text('Send without a note')",
            "button:has-text('Send without note')",
            "button:has-text('Send')",
            "button:has-text('Send now')",
            "button:has-text('Send invitation')",
            "button[aria-label*='Send']",
            "button[aria-label*='send']",
            "button[aria-label*='Send invitation']",
            "button[aria-label*='invitation']",
            "div.artdeco-modal button:has-text('Send')",
            "div.artdeco-modal button:has-text('Send now')",
            "div[role='dialog'] button:has-text('Send')",
            "div[role='dialog'] button:has-text('Send now')",
            "button[aria-label='Send']",
            "button[aria-label='Send now']",
            "button[aria-label='Send invitation']",
            "button[data-test-id='send-invite-button']",
            "button[data-control-name='send_invitation']",
            "button[data-control-name='invitation']",
            "button.artdeco-button--primary",
            "button[type='submit']",
            "button:has-text('Done')",
            "div.artdeco-modal button:has-text('Done')",
        ]

        if note and not out_of_notes:
            # Click "Add a note" if dialog is shown
            add_note_clicked = False
            for selector in add_note_selectors:
                loc = page.locator(selector).first
                try:
                    await loc.wait_for(state="visible", timeout=3000)
                    await _random_delay(0.3, 0.7)
                    await loc.click(timeout=3000)
                    add_note_clicked = True
                    logger.info("Clicked Add a note button using: %s", selector)
                    await _random_delay(1.0, 2.0)  # Wait for note textarea to appear
                    break
                except Exception:
                    continue

            if not add_note_clicked:
                logger.warning("Failed to locate and click 'Add a note' button inside the connection dialog. Setting out_of_notes = True to send without a note.")
                out_of_notes = True

            await _random_delay(0.5, 1.0)

            # Check if Premium upsell modal appeared instead of note input textarea
            try:
                modal_loc = page.locator("div.artdeco-modal").first
                if await modal_loc.is_visible(timeout=1500):
                    modal_text = await modal_loc.inner_text()
                    if "out of free custom notes" in modal_text or "invites with Premium" in modal_text or "personalized invites" in modal_text or "reached the limit" in modal_text:
                        logger.warning("LinkedIn Premium upsell modal detected after trying to add a note. Attempting to send without a note directly...")
                        out_of_notes = True
                        
                        # Try to find and click "Send without note" / "Send without a note" button first
                        send_without_note_selectors = [
                            "button:has-text('Send without note')",
                            "button:has-text('Send without a note')",
                            "button[aria-label*='without note']",
                            "button[aria-label*='without a note']",
                            "div.artdeco-modal button:has-text('Send without note')",
                            "div.artdeco-modal button:has-text('Send without a note')"
                        ]
                        
                        clicked_direct = False
                        for selector in send_without_note_selectors:
                            btn = page.locator(selector).first
                            try:
                                if await btn.is_visible(timeout=1000):
                                    await btn.click(timeout=1000)
                                    send_clicked = True
                                    clicked_direct = True
                                    logger.info("Clicked 'Send without note' directly on Premium modal using: %s", selector)
                                    break
                            except Exception:
                                continue
                                
                        if not clicked_direct:
                            logger.warning("Could not click 'Send without note' directly. Closing the Premium modal.")
                            close_btn = modal_loc.locator("button[aria-label='Dismiss'], button[aria-label='Close'], button.artdeco-modal__dismiss").first
                            if await close_btn.is_visible(timeout=1000):
                                await close_btn.click()
                                await _random_delay(1, 2)
            except Exception as e:
                logger.debug("Error checking/dismissing Premium modal in note block: %s", e)

            if not out_of_notes:
                # Type the connection note
                note_filled = False
                for selector in note_input_selectors:
                    loc = page.locator(selector).first
                    try:
                        await loc.wait_for(state="visible", timeout=5000)
                        await _random_delay(0.3, 0.7)
                        await loc.fill("")
                        await loc.type(note[:300], delay=random.randint(40, 100))  # Slightly slower typing
                        note_filled = True
                        logger.info("Filled connection note using: %s", selector)
                        await _random_delay(1.5, 3.0)  # Wait before clicking Send
                        break
                    except Exception:
                        continue

                if not note_filled:
                    scr_path = ""
                    try:
                        scr_path = await _take_playwright_screenshot(page, "fill_note_failed")
                    except Exception:
                        pass
                    return {
                        "success": False,
                        "error": "Failed to locate and fill the connection note textarea.",
                        "error_screenshot_path": scr_path
                    }

                await _random_delay(1, 2)

        # Click Send / Send now
        if not out_of_notes and not send_clicked:
            for selector in send_selectors:
                loc = page.locator(selector).first
                try:
                    await loc.wait_for(state="visible", timeout=5000)
                    await _random_delay(0.3, 0.7)
                    await loc.click(timeout=5000)
                    send_clicked = True
                    logger.info("Clicked Send connection button using: %s", selector)
                    await _random_delay(1.5, 2.5)  # Wait for send to complete
                    break
                except Exception:
                    continue

        # Fallback if out of notes (either Premium modal popped up or Add a note button wasn't found/clicked)
        if not send_clicked and out_of_notes:
            # 1. Try to click Send directly in the already open connection dialog
            logger.info("Attempting to click Send/Send without a note button in the active dialog first...")
            for selector in send_selectors:
                loc = page.locator(selector).first
                try:
                    if await loc.is_visible(timeout=2000):
                        await loc.click(timeout=3000)
                        send_clicked = True
                        logger.info("Clicked Send connection button directly (without note) in active dialog using: %s", selector)
                        await _random_delay(2, 4)
                        break
                except Exception:
                    continue

            # 2. If it is still not clicked, reload the page and try a clean connection request without a note
            if not send_clicked:
                logger.info("Connect dialog was closed or not responsive. Reloading page to reset state, then re-trying connection request without a note.")
                try:
                    await page.reload(wait_until="domcontentloaded", timeout=30000)
                    await _random_delay(3, 5)
                except Exception as e:
                    logger.warning("Page reload timed out or failed: %s", e)
                
                # Click Connect again using robust helper
                connect_clicked, _, _ = await _find_and_click_connect_button(page)
                
                if connect_clicked:
                    await _random_delay(2, 3)
                    # Now click Send directly (do not click Add a note)
                    for selector in send_selectors:
                        loc = page.locator(selector).first
                        try:
                            await loc.wait_for(state="visible", timeout=5000)
                            await loc.click(timeout=5000)
                            send_clicked = True
                            logger.info("Clicked Send connection button directly on retry: %s", selector)
                            break
                        except Exception:
                            continue

        if not send_clicked:
            scr_path = ""
            try:
                scr_path = await _take_playwright_screenshot(page, "send_failed")
            except Exception:
                pass
            return {
                "success": False,
                "error": "Failed to locate and click 'Send' button to dispatch the connection request.",
                "error_screenshot_path": scr_path
            }

        logger.info("Connection request sent to %s", linkedin_url)
        note_sent = note and not out_of_notes
        return {
            "success": True,
            "action": "connection_sent",
            "linkedin_url": linkedin_url,
            "note_sent": bool(note_sent),
            "note_content": note if note_sent else "",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as exc:
        logger.exception("Failed to send connection request via Playwright: %s", exc)
        scr_path = ""
        try:
            scr_path = await _take_playwright_screenshot(page, "connect")
        except Exception:
            pass
        err_msg = str(exc) if str(exc) else f"{type(exc).__name__}"
        return {"success": False, "error": err_msg, "error_screenshot_path": scr_path}
    finally:
        if pw:
            try:
                if browser:
                    await browser.close()
            except Exception:
                pass
            try:
                if pw:
                    await pw.stop()
            except Exception:
                pass


async def send_connection_request(linkedin_url: str, note: str, user_id: str) -> Dict[str, Any]:
    """
    Send a LinkedIn connection request with a personalized note.
    Delegates to the subprocess runner.
    """
    from app.config.mongodb_config import get_database

    db = await get_database()
    session = await db.linkedin_sessions.find_one({"user_id": user_id})

    if not session or session.get("status") != "connected":
        return {"success": False, "error": "No active LinkedIn session."}

    return await run_linkedin_action_in_subprocess(
        action="send_connection_request",
        user_id=user_id,
        linkedin_url=linkedin_url,
        message=note or ""
    )


# ── Messaging ──────────────────────────────────────────────────────────────


async def _send_message_pw(linkedin_url: str, message: str, cookies: List[Dict[str, Any]], page=None) -> Dict[str, Any]:
    """Send message using Playwright."""
    pw = None
    browser = None
    try:
        if page is None:
            async_playwright = await _get_playwright()
            pw = await async_playwright().start()
            browser = await _launch_stealth_browser(pw, headless=LINKEDIN_HEADLESS)
            context = await _create_stealth_context(browser, cookies=cookies)
            page = await context.new_page()
        await _random_delay(2, 4)
        try:
            await page.goto(linkedin_url, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            logger.warning("page.goto messaging profile timed out, attempting to proceed anyway: %s", e)
        await _random_delay(3, 6)
        try:
            await page.locator("main.scaffold-layout__main, div.pv-top-card-v2-section, .pvs-profile-actions, .global-nav").first.wait_for(state="visible", timeout=30000)
            logger.info("Profile page layout detected as visible for messaging")
        except Exception as e:
            logger.warning("Timed out waiting for profile layout elements for messaging: %s", e)

        # Check if we are logged in / redirected to login
        current_url = page.url
        if "login" in current_url or "signup" in current_url or "checkpoint" in current_url:
            return {"success": False, "error": "Session expired or invalid. Please reconnect your LinkedIn account."}

        try:
            global_nav = await page.query_selector("#global-nav, .global-nav")
            if not global_nav:
                sign_in_btn = await page.query_selector("a:has-text('Sign in'), button:has-text('Sign in')")
                if sign_in_btn:
                    return {"success": False, "error": "Session expired or invalid. Please reconnect your LinkedIn account."}
        except Exception:
            pass

        # Click the Message button on their profile
        message_clicked = False
        message_selectors = [
            "button:has-text('Message')",
            "a:has-text('Message')",
            "button[aria-label*='Message']",
            "button[aria-label*='message']",
        ]
        
        # Scoped containers to search inside first, falling back to page-wide (empty string)
        containers = [
            "div.pvs-profile-actions",
            "div.pv-top-card-v2-section__actions",
            "div.pv-top-card-layout__actions",
            ".pv-top-card-v2-section",
            "main.scaffold-layout__main section.artdeco-card",
            ""
        ]

        for container in containers:
            for selector in message_selectors:
                sel = f"{container} {selector}".strip() if container else selector
                message_btn = page.locator(sel).first
                try:
                    await message_btn.wait_for(state="visible", timeout=5000)
                    await _random_delay(0.5, 1.0)  # Brief pause before clicking
                    await message_btn.click(timeout=8000)
                    message_clicked = True
                    logger.info("Message button clicked using container-scoped selector: %s", sel)
                    await _random_delay(1, 2)  # Wait for messaging panel/dialog to open
                    break
                except Exception:
                    continue
            if message_clicked:
                break

        # Fallback Strategy: Look for Message inside More actions dropdown
        if not message_clicked:
            more_selectors = [
                "button[aria-label='More actions']",
                "button[aria-label*='More']",
                "button[aria-label*='actions']",
                "button:has-text('More')",
                "button.pv-s-profile-actions__overflow-toggle",
                "button.artdeco-dropdown__trigger",
            ]
            for container in containers:
                for selector in more_selectors:
                    sel = f"{container} {selector}".strip() if container else selector
                    more_loc = page.locator(sel).first
                    try:
                        await more_loc.wait_for(state="visible", timeout=5000)
                        await _random_delay(0.5, 1.0)
                        await more_loc.click(timeout=8000)
                        await _random_delay(1.5, 3.0)  # Wait for dropdown to fully open

                        # Try role menuitem or span has-text Message
                        import re
                        msg_item = page.get_by_role("menuitem", name=re.compile(r"Message", re.I)).first
                        if await msg_item.is_visible(timeout=3000):
                            await msg_item.click(timeout=5000)
                            message_clicked = True
                            logger.info("Message button clicked inside More actions dropdown (menuitem Message)")
                            await _random_delay(1, 2)  # Wait for messaging panel
                            break

                        # Try selector fallback for message item inside open menu
                        msg_menu_selectors = [
                            "span:has-text('Message')",
                            "div[role='button']:has-text('Message')",
                            "span.pv-s-profile-actions__label:has-text('Message')",
                            "button.pv-s-profile-actions__action:has-text('Message')"
                        ]
                        for item_sel in msg_menu_selectors:
                            item_loc = page.locator(item_sel).first
                            try:
                                if await item_loc.is_visible(timeout=3000):
                                    await item_loc.click(timeout=5000)
                                    message_clicked = True
                                    logger.info("Message button clicked inside More actions dropdown fallback -> %s", item_sel)
                                    await _random_delay(1, 2)
                                    break
                            except Exception:
                                continue
                        if message_clicked:
                            break
                    except Exception:
                        continue
                if message_clicked:
                    break

        if not message_clicked:
            scr_path = ""
            try:
                scr_path = await _take_playwright_screenshot(page, "message_btn_failed")
            except Exception:
                pass
            return {
                "success": False,
                "error": "Message button not found. You may not be connected.",
                "error_screenshot_path": scr_path
            }

        # Type the message
        msg_input_selectors = [
            ".msg-overlay-conversation-bubble div[role='textbox']",
            ".msg-overlay-conversation-bubble div.msg-form__contenteditable",
            "aside div[role='textbox']",
            "div[role='textbox']",
            "div.msg-form__contenteditable",
            "textarea.msg-form__contenteditable",
            "div.msg-form__message-texteditor div[contenteditable='true']",
        ]
        
        msg_input = None
        for selector in msg_input_selectors:
            try:
                loc = page.locator(selector).first
                await loc.wait_for(state="visible", timeout=4000)
                msg_input = loc
                logger.info("Message input found with selector: %s", selector)
                break
            except Exception:
                continue

        try:
            if not msg_input:
                raise ValueError("No matching message input selectors found")
            await _random_delay(0.3, 0.7)
            try:
                await msg_input.click(timeout=5000)
            except Exception as click_err:
                logger.warning("msg_input.click failed, trying focus fallback: %s", click_err)
                try:
                    await msg_input.focus()
                except Exception:
                    pass
            await msg_input.press_sequentially(message[:500], delay=random.randint(40, 80))
            await _random_delay(1, 2)  # Shorter wait before clicking send
        except Exception as e:
            scr_path = ""
            try:
                scr_path = await _take_playwright_screenshot(page, "msg_input_failed")
            except Exception:
                pass
            return {
                "success": False,
                "error": f"Message input textbox not found or not clickable: {e}",
                "error_screenshot_path": scr_path
            }

        # Send
        send_btn_selectors = [
            ".msg-overlay-conversation-bubble button.msg-form__send-button",
            ".msg-overlay-conversation-bubble button:has-text('Send')",
            "aside button.msg-form__send-button",
            "aside button:has-text('Send')",
            "button.msg-form__send-button",
            "button[type='submit'].msg-form__send-button",
            "button:has-text('Send')",
            "button[aria-label*='Send']",
        ]
        
        send_btn = None
        for selector in send_btn_selectors:
            try:
                loc = page.locator(selector).first
                await loc.wait_for(state="visible", timeout=4000)
                send_btn = loc
                logger.info("Send button found with selector: %s", selector)
                break
            except Exception:
                continue

        try:
            if not send_btn:
                raise ValueError("No matching send button selectors found")
            await _random_delay(0.3, 0.7)
            await send_btn.click(timeout=5000)
            await _random_delay(2, 3)  # Shorter wait for message to send
        except Exception as e:
            scr_path = ""
            try:
                scr_path = await _take_playwright_screenshot(page, "msg_send_failed")
            except Exception:
                pass
            return {
                "success": False,
                "error": f"Message Send button not found or not clickable: {e}",
                "error_screenshot_path": scr_path
            }

        logger.info("Message sent to %s", linkedin_url)
        return {
            "success": True,
            "action": "message_sent",
            "linkedin_url": linkedin_url,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as exc:
        logger.exception("Failed to send LinkedIn message via Playwright: %s", exc)
        scr_path = ""
        try:
            scr_path = await _take_playwright_screenshot(page, "message")
        except Exception:
            pass
        err_msg = str(exc) if str(exc) else f"{type(exc).__name__}"
        return {"success": False, "error": err_msg, "error_screenshot_path": scr_path}
    finally:
        if pw:
            try:
                if browser:
                    await browser.close()
            except Exception:
                pass
            try:
                if pw:
                    await pw.stop()
            except Exception:
                pass


async def send_message(linkedin_url: str, message: str, user_id: str) -> Dict[str, Any]:
    """
    Send a LinkedIn direct message.
    Delegates to the subprocess runner.
    """
    from app.config.mongodb_config import get_database

    db = await get_database()
    session = await db.linkedin_sessions.find_one({"user_id": user_id})

    if not session or session.get("status") != "connected":
        return {"success": False, "error": "No active LinkedIn session."}

    return await run_linkedin_action_in_subprocess(
        action="send_message",
        user_id=user_id,
        linkedin_url=linkedin_url,
        message=message
    )


# ── Connection Monitoring ──────────────────────────────────────────────────


async def _get_pending_invitations_pw(cookies: List[Dict[str, Any]], page=None) -> Dict[str, Any]:
    """Check for notifications and messages."""
    pw = None
    browser = None
    try:
        if page is None:
            async_playwright = await _get_playwright()
            pw = await async_playwright().start()
            browser = await _launch_stealth_browser(pw, headless=LINKEDIN_HEADLESS)
            context = await _create_stealth_context(browser, cookies=cookies)
            page = await context.new_page()
        await _random_delay(2, 4)

        # Check notifications for accepted connections
        accepted_connections = []
        try:
            await page.goto("https://www.linkedin.com/mynetwork/invite-connect/connections/", wait_until="domcontentloaded", timeout=30000)
            if "login" in page.url or "signin" in page.url or "uas/" in page.url or "signup" in page.url:
                raise ValueError("Session expired (redirected to login page)")
            await _random_delay(3, 5)
            
            # Scrape connection links
            connection_links = await page.query_selector_all(".mn-connection-card__link, a[href*='/in/']")
            for link in connection_links:
                href = await link.get_attribute("href")
                # Also get their name
                name_el = await link.query_selector(".mn-connection-card__name")
                name = (await name_el.inner_text()).strip() if name_el else ""
                if href:
                    clean_url = href.split("?")[0]
                    if not clean_url.startswith("http"):
                        clean_url = "https://www.linkedin.com" + clean_url
                    
                    if clean_url not in [c["linkedin_url"] for c in accepted_connections]:
                        accepted_connections.append({
                            "linkedin_url": clean_url,
                            "name": name or "Unknown"
                        })
            
            # For connections with unknown names, skip profile visits - LinkedIn detects stealth browser
            # and visits are too slow (~24s each). Try name from profile URL slug as last resort.
            import re
            for conn in accepted_connections:
                if conn["name"] == "Unknown":
                    slug = conn["linkedin_url"].rstrip("/").split("/")[-1]
                    # Remove trailing numbers (LinkedIn suffixes like -01b855388)
                    name_slug = re.sub(r'-\d+$', '', slug)
                    name_slug = re.sub(r'-+', '-', name_slug).strip('-')
                    # Only use if slug has at least 2 name-like parts (e.g., "john-smith" -> ["john", "smith"])
                    slug_parts = [p for p in name_slug.split("-") if p and len(p) > 1 and not re.match(r'^[a-z]{1,2}$', p)]
                    if len(slug_parts) >= 2:
                        guessed_name = " ".join(p.capitalize() for p in slug_parts)
                        conn["name"] = guessed_name
                        logger.info("Guessed name from URL slug: %s -> %s", slug, guessed_name)
            
            name_fail_count = sum(1 for c in accepted_connections if c["name"] == "Unknown")
            logger.info("get_pending_invitations: %d connections, %d unknown names after all enrichment", 
                       len(accepted_connections), name_fail_count)
                
        except Exception as e:
            if "Session expired" in str(e):
                raise
            logger.warning("Failed to scrape accepted connections: %s", e)

        # Check sent invitations page
        pending_invitations = []
        try:
            await page.goto("https://www.linkedin.com/mynetwork/invitation-manager/sent/", wait_until="domcontentloaded", timeout=30000)
            if "login" in page.url or "signin" in page.url or "uas/" in page.url or "signup" in page.url:
                raise ValueError("Session expired (redirected to login page)")
            await _random_delay(3, 5)
            
            # Scrape sent cards
            invitation_links = await page.query_selector_all(".invitation-card a[href*='/in/'], .mn-invitation-card a[href*='/in/']")
            for link in invitation_links:
                href = await link.get_attribute("href")
                if href:
                    clean_url = href.split("?")[0]
                    if not clean_url.startswith("http"):
                        clean_url = "https://www.linkedin.com" + clean_url
                    if clean_url not in pending_invitations:
                        pending_invitations.append(clean_url)
        except Exception as e:
            if "Session expired" in str(e):
                raise
            logger.warning("Failed to scrape pending sent invitations: %s", e)

        # Check messaging for new messages and ALL conversations (to get names for connections)
        new_messages = []
        all_conversations_names = {}  # profile_url -> name mapping
        try:
            await page.goto("https://www.linkedin.com/messaging/", wait_until="domcontentloaded", timeout=15000)
            if "login" in page.url or "signin" in page.url or "uas/" in page.url or "signup" in page.url:
                raise ValueError("Session expired (redirected to login page)")
            await _random_delay(2, 4)
            
            # Collect ALL conversations to build name map (not just unread)
            all_cards = await page.query_selector_all(".msg-conversation-card, .msg-conversation-listitem")
            for card in all_cards:
                name_el = await card.query_selector(".msg-conversation-card__participant-names, .msg-conversation-listitem__participant-names")
                name = (await name_el.inner_text()).strip() if name_el else ""
                
                profile_link = await card.query_selector("a[href*='/in/']")
                profile_url = ""
                if profile_link:
                    href_prof = await profile_link.get_attribute("href")
                    if href_prof:
                        profile_url = href_prof.split("?")[0]
                        if not profile_url.startswith("http"):
                            profile_url = "https://www.linkedin.com" + profile_url
                
                if profile_url and name and name not in ("", "Unknown"):
                    all_conversations_names[profile_url] = name
            
            # Unread conversations
            unread_cards = await page.query_selector_all(".msg-conversation-card--unread, .msg-conversation-listitem--unread")
            for card in unread_cards:
                href_el = await card.query_selector("a[href*='/messaging/thread/']")
                href = await href_el.get_attribute("href") if href_el else ""
                
                name_el = await card.query_selector(".msg-conversation-card__participant-names")
                name = (await name_el.inner_text()).strip() if name_el else "Unknown"
                
                preview_el = await card.query_selector(".msg-conversation-card__subtitle")
                preview = (await preview_el.inner_text()).strip() if preview_el else ""
                
                profile_link = await card.query_selector("a[href*='/in/']")
                profile_url = ""
                if profile_link:
                    href_prof = await profile_link.get_attribute("href")
                    if href_prof:
                        profile_url = href_prof.split("?")[0]
                        if not profile_url.startswith("http"):
                            profile_url = "https://www.linkedin.com" + profile_url
                
                new_messages.append({
                    "from_name": name,
                    "preview": preview,
                    "linkedin_url": profile_url,
                    "thread_url": href,
                })
        except Exception as e:
            if "Session expired" in str(e):
                raise
            logger.warning("Failed to scrape new messages: %s", e)
        
        # Enrich connection names from conversations name map
        for conn in accepted_connections:
            if conn["name"] == "Unknown" and conn["linkedin_url"] in all_conversations_names:
                conn["name"] = all_conversations_names[conn["linkedin_url"]]
        
        return {
            "accepted_connections": accepted_connections,
            "pending_invitations": pending_invitations,
            "new_messages": new_messages
        }

    except Exception as exc:
        logger.error("Failed to check invitations via Playwright: %s", exc)
        if "Session expired" in str(exc):
            return {"success": False, "error": "Session expired (redirected to login page)"}
        return {"accepted_connections": [], "pending_invitations": [], "new_messages": []}
    finally:
        try:
            if browser:
                await browser.close()
        except Exception:
            pass
        try:
            if pw:
                await pw.stop()
        except Exception:
            pass


async def get_pending_invitations(user_id: str) -> Dict[str, Any]:
    """
    Check for accepted connections and pending invitations.
    Delegates to the subprocess runner.
    """
    from app.config.mongodb_config import get_database

    db = await get_database()
    session = await db.linkedin_sessions.find_one({"user_id": user_id})

    if not session or session.get("status") != "connected":
        return {"accepted_connections": [], "pending_invitations": [], "new_messages": []}

    return await run_linkedin_action_in_subprocess(
        action="get_pending_invitations",
        user_id=user_id
    )


# ── Send Message by Name (Search Connections) ─────────────────────────────


@proactor_isolated
async def _send_message_by_name_pw(person_name: str, message: str, cookies: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Send a LinkedIn message by searching for a connection by name via the
    LinkedIn messaging compose UI.

    Flow:
    1. Navigate to https://www.linkedin.com/messaging/
    2. Click the compose / new message button
    3. Type the person's name in the "To:" field
    4. Wait for autocomplete suggestions and click the best match
    5. Type the message body
    6. Click Send

    This approach avoids needing a profile URL — it works with just a name.
    """
    pw = None
    browser = None
    page = None
    try:
        async_playwright = await _get_playwright()
        pw = await async_playwright().start()
        browser = await _launch_stealth_browser(pw, headless=LINKEDIN_HEADLESS)
        context = await _create_stealth_context(browser, cookies=cookies)
        page = await context.new_page()
        await _random_delay(2, 4)

        # Navigate to LinkedIn messaging
        try:
            await page.goto("https://www.linkedin.com/messaging/", wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            logger.warning("page.goto messaging timed out, proceeding anyway: %s", e)

        await _random_delay(3, 5)

        # Check if we are logged in
        current_url = page.url
        if "login" in current_url or "signup" in current_url or "checkpoint" in current_url:
            return {"success": False, "error": "Session expired or invalid. Please reconnect your LinkedIn account."}

        # Wait for the messaging page to load
        try:
            await page.locator(".msg-overlay-list-bubble, .messaging-container, .msg-conversations-container__title-row, aside.msg-overlay-list-bubble").first.wait_for(state="visible", timeout=15000)
            logger.info("Messaging page loaded")
        except Exception:
            logger.warning("Messaging container not found quickly, trying to proceed...")

        # Click the compose / new message button
        compose_clicked = False
        compose_selectors = [
            "a[href='/messaging/thread/new/']",
            "button[aria-label='Compose message']",
            "a[aria-label='Compose message']",
            "button:has-text('Compose message')",
            "a:has-text('New message')",
            "button.msg-overlay-bubble-header__control--new-convo-btn",
            ".msg-conversations-container__title-row a[href*='new']",
            "a.msg-overlay-bubble-header__button--new",
            "svg[data-test-icon='compose-small'] ~ span",
            # Floating compose button
            "button[data-control-name='overlay.compose_message']",
            "button.msg-overlay-bubble-header__button",
        ]

        for selector in compose_selectors:
            try:
                loc = page.locator(selector).first
                if await loc.is_visible(timeout=3000):
                    await loc.click(timeout=5000)
                    compose_clicked = True
                    logger.info("Compose button clicked using selector: %s", selector)
                    break
            except Exception:
                continue

        if not compose_clicked:
            # Fallback: try clicking any element with "compose" or "new message" text
            try:
                loc = page.get_by_role("link", name="Compose message").first
                if await loc.is_visible(timeout=3000):
                    await loc.click(timeout=5000)
                    compose_clicked = True
                    logger.info("Compose button clicked via get_by_role link")
            except Exception:
                pass

        if not compose_clicked:
            try:
                loc = page.get_by_role("button", name="Compose message").first
                if await loc.is_visible(timeout=3000):
                    await loc.click(timeout=5000)
                    compose_clicked = True
                    logger.info("Compose button clicked via get_by_role button")
            except Exception:
                pass

        if not compose_clicked:
            scr_path = await _take_playwright_screenshot(page, "compose_btn_not_found")
            return {
                "success": False,
                "error": "Could not find the compose/new message button on LinkedIn messaging page.",
                "error_screenshot_path": scr_path
            }

        await _random_delay(2, 3)

        # Wait for the new message compose overlay/dialog to appear
        # The "To:" input field should be visible
        to_input = None
        to_input_selectors = [
            "input[placeholder*='Type a name']",
            "input[placeholder*='type a name']",
            "input[aria-label*='Type a name']",
            "input.msg-connections-typeahead__search-field",
            "input.msg-compose-form__search-field",
            "input[role='combobox']",
            "input.msg-connections-typeahead__input",
        ]

        for selector in to_input_selectors:
            try:
                loc = page.locator(selector).first
                await loc.wait_for(state="visible", timeout=5000)
                to_input = loc
                logger.info("To-input found with selector: %s", selector)
                break
            except Exception:
                continue

        if not to_input:
            scr_path = await _take_playwright_screenshot(page, "to_input_not_found")
            return {
                "success": False,
                "error": "Could not find the 'To:' input field in the compose dialog.",
                "error_screenshot_path": scr_path
            }

        # Type the person's name in the To field
        await to_input.click()
        await _random_delay(0.3, 0.7)
        await to_input.press_sequentially(person_name, delay=random.randint(60, 120))
        await _random_delay(2, 4)  # Wait for autocomplete suggestions to appear

        # Click the first matching suggestion
        suggestion_clicked = False
        suggestion_selectors = [
            # LinkedIn's typeahead suggestion list items
            "ul.msg-connections-typeahead__search-results li button",
            "ul.msg-connections-typeahead__search-results li",
            "div.msg-connections-typeahead__search-results li button",
            "div.basic-typeahead__triggered-content li button",
            "div.basic-typeahead__triggered-content li",
            "ul[role='listbox'] li",
            "div[role='listbox'] div[role='option']",
            "ul.msg-connections-typeahead__results-list li",
            # General typeahead
            ".msg-connections-typeahead__result-item",
            "li.msg-connections-typeahead__search-result",
        ]

        for selector in suggestion_selectors:
            try:
                loc = page.locator(selector).first
                if await loc.is_visible(timeout=5000):
                    await loc.click(timeout=5000)
                    suggestion_clicked = True
                    logger.info("Suggestion clicked using selector: %s", selector)
                    break
            except Exception:
                continue

        if not suggestion_clicked:
            # Last resort: try clicking any visible option matching the name
            try:
                import re as _re
                name_parts = person_name.strip().split()
                # Try matching first name at minimum
                pattern = _re.compile(name_parts[0], _re.IGNORECASE)
                loc = page.get_by_role("option", name=pattern).first
                if await loc.is_visible(timeout=3000):
                    await loc.click(timeout=5000)
                    suggestion_clicked = True
                    logger.info("Suggestion clicked using get_by_role option with name regex")
            except Exception:
                pass

        if not suggestion_clicked:
            scr_path = await _take_playwright_screenshot(page, "suggestion_not_found")
            return {
                "success": False,
                "error": f"No connection found matching '{person_name}'. Make sure this person is in your LinkedIn connections.",
                "error_screenshot_path": scr_path
            }

        await _random_delay(1, 2)

        # Type the message in the message body
        msg_input_selectors = [
            ".msg-overlay-conversation-bubble div[role='textbox']",
            ".msg-overlay-conversation-bubble div.msg-form__contenteditable",
            "aside div[role='textbox']",
            "div[role='textbox']",
            "div.msg-form__contenteditable",
            "textarea.msg-form__contenteditable",
            "div.msg-form__message-texteditor div[contenteditable='true']",
        ]

        msg_input = None
        for selector in msg_input_selectors:
            try:
                loc = page.locator(selector).first
                await loc.wait_for(state="visible", timeout=4000)
                msg_input = loc
                logger.info("Message input found with selector: %s", selector)
                break
            except Exception:
                continue

        if not msg_input:
            scr_path = await _take_playwright_screenshot(page, "msg_input_not_found")
            return {
                "success": False,
                "error": "Could not find the message input field.",
                "error_screenshot_path": scr_path
            }

        try:
            await msg_input.click(timeout=5000)
        except Exception as e:
            logger.warning("msg_input.click failed, trying focus and keyboard typing fallback: %s", e)
            try:
                await msg_input.focus()
            except Exception:
                pass
        await _random_delay(0.3, 0.7)
        await msg_input.press_sequentially(message[:500], delay=random.randint(40, 80))
        await _random_delay(1, 2)

        # Click Send
        send_btn_selectors = [
            ".msg-overlay-conversation-bubble button.msg-form__send-button",
            ".msg-overlay-conversation-bubble button:has-text('Send')",
            "aside button.msg-form__send-button",
            "aside button:has-text('Send')",
            "button.msg-form__send-button",
            "button[type='submit'].msg-form__send-button",
            "button:has-text('Send')",
            "button[aria-label*='Send']",
        ]

        send_clicked = False
        for selector in send_btn_selectors:
            try:
                loc = page.locator(selector).first
                if await loc.is_visible(timeout=4000):
                    await _random_delay(0.3, 0.7)
                    await loc.click(timeout=5000)
                    send_clicked = True
                    logger.info("Send button clicked using selector: %s", selector)
                    break
            except Exception:
                continue

        if not send_clicked:
            scr_path = await _take_playwright_screenshot(page, "send_btn_not_found")
            return {
                "success": False,
                "error": "Could not find the Send button.",
                "error_screenshot_path": scr_path
            }

        await _random_delay(2, 4)

        logger.info("Message sent to '%s' via name search", person_name)
        return {
            "success": True,
            "action": "message_sent_by_name",
            "person_name": person_name,
            "message_preview": message[:100],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as exc:
        logger.exception("Failed to send LinkedIn message by name: %s", exc)
        scr_path = ""
        try:
            scr_path = await _take_playwright_screenshot(page, "msg_by_name")
        except Exception:
            pass
        err_msg = str(exc) if str(exc) else f"{type(exc).__name__}"
        return {"success": False, "error": err_msg, "error_screenshot_path": scr_path}
    finally:
        try:
            if browser:
                await browser.close()
        except Exception:
            pass
        try:
            if pw:
                await pw.stop()
        except Exception:
            pass


async def send_message_by_name(person_name: str, message: str, user_id: str) -> Dict[str, Any]:
    """
    Send a LinkedIn message by searching for a connection by name.
    Delegates to the subprocess runner.
    """
    from app.config.mongodb_config import get_database

    db = await get_database()
    session = await db.linkedin_sessions.find_one({"user_id": user_id})

    if not session or session.get("status") != "connected":
        return {"success": False, "error": "No active LinkedIn session. Please connect your LinkedIn account first."}

    return await run_linkedin_action_in_subprocess(
        action="send_message_by_name",
        user_id=user_id,
        linkedin_url=None,
        message=f"{person_name}|||{message}"  # Pack name and message together
    )


# ── Cookie Encryption ──────────────────────────────────────────────────────


def _get_encryption_key() -> bytes:
    """Get or generate the Fernet encryption key."""
    import base64
    import hashlib
    from app.config.settings import settings
    
    secret = settings.COOKIE_ENCRYPTION_KEY or settings.JWT_SECRET
    key = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(key)


def _encrypt_cookies(cookies_json: str) -> str:
    """Encrypt cookie data using Fernet symmetric encryption."""
    try:
        from cryptography.fernet import Fernet
        f = Fernet(_get_encryption_key())
        return f.encrypt(cookies_json.encode()).decode()
    except ImportError:
        logger.warning("cryptography package not installed, storing cookies as base64")
        import base64
        return base64.b64encode(cookies_json.encode()).decode()


def _decrypt_cookies(encrypted: str) -> str:
    """
    Decrypt stored cookie data.

    Tries multiple strategies in order:
      1. Current Fernet key (sha256 of COOKIE_ENCRYPTION_KEY or JWT_SECRET)
      2. JWT_SECRET used directly as Fernet key (legacy fallback)
      3. Base64 decode (old plain storage before encryption was added)
      4. Raw JSON passthrough (dev/test mode)

    If all strategies fail, raises ValueError with a clear user-facing message
    so callers can mark the session as expired rather than crash-looping.
    """
    import base64
    import json

    errors = []

    # Strategy 1: Current derived key
    try:
        from cryptography.fernet import Fernet
        f = Fernet(_get_encryption_key())
        return f.decrypt(encrypted.encode()).decode()
    except Exception as exc:
        errors.append(f"derived_key: {exc}")

    # Strategy 2: JWT_SECRET sha256 directly (if COOKIE_ENCRYPTION_KEY was added after cookies were saved)
    try:
        from cryptography.fernet import Fernet
        from app.config.settings import settings
        import hashlib
        fallback_key = base64.urlsafe_b64encode(hashlib.sha256(settings.JWT_SECRET.encode()).digest())
        f = Fernet(fallback_key)
        return f.decrypt(encrypted.encode()).decode()
    except Exception as exc:
        errors.append(f"jwt_secret_key: {exc}")

    # Strategy 3: Plain base64 (old storage before encryption was added)
    try:
        decoded = base64.b64decode(encrypted.encode()).decode("utf-8")
        json.loads(decoded)  # Verify it is valid JSON cookies
        return decoded
    except Exception as exc:
        errors.append(f"base64: {exc}")

    # Strategy 4: Already plain JSON (dev mode)
    try:
        json.loads(encrypted)
        return encrypted
    except Exception as exc:
        errors.append(f"raw_json: {exc}")

    # All strategies failed — session key has rotated or data is corrupted
    logger.error(
        "LinkedIn cookie decryption failed with all strategies. "
        "Session was encrypted with a different key. "
        "User must re-connect their LinkedIn session. Errors: %s",
        " | ".join(errors),
    )
    raise ValueError(
        "LinkedIn session cookies could not be decrypted — the encryption key has changed. "
        "Please re-connect your LinkedIn account via Settings → Integrations."
    )

