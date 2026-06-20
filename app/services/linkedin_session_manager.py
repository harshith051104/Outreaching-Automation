"""
LinkedIn Playwright Session Registry Manager

Caches active LinkedInAccountSession instances in-memory to prevent starting
new Chromium processes for every action. Safely encrypts/decrypts cookies
using Fernet security keys, checks for session validity, and handles comply gates.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from app.config.mongodb_config import get_database
from app.services.linkedin_outreach_service import (
    _get_playwright,
    _launch_stealth_browser,
    _create_stealth_context,
    _decrypt_cookies,
    _encrypt_cookies,
    LINKEDIN_HEADLESS
)

logger = logging.getLogger(__name__)


class LinkedInAccountSession:
    def __init__(self, user_id: str):
        self.user_id = user_id
        
        # Playwright objects
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.last_used = time.time()
        self.lock = asyncio.Lock()
        
    async def ensure_browser(self) -> None:
        """Launch or recover the browser context. Restore cookies from DB."""
        self.last_used = time.time()
        if self.page and not self.page.is_closed():
            return

        logger.info("Initializing warm Playwright browser session for user: %s", self.user_id)
        db = await get_database()
        session_doc = await db.linkedin_sessions.find_one({"user_id": self.user_id})
        
        cookies = []
        if session_doc and session_doc.get("cookies_encrypted"):
            try:
                decrypted = _decrypt_cookies(session_doc["cookies_encrypted"])
                cookies = json.loads(decrypted)
            except Exception as e:
                logger.error("Failed to decrypt cookies in ensure_browser: %s", e)

        pw_func = await _get_playwright()
        self.playwright = await pw_func().start()
        self.browser = await _launch_stealth_browser(self.playwright, headless=LINKEDIN_HEADLESS)
        self.context = await _create_stealth_context(self.browser, cookies=cookies)
        self.page = await self.context.new_page()
        
        # Dismiss gates / comply overlay if cookies are loaded
        if cookies:
            try:
                await self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15000)
                await self.dismiss_comply_gate()
            except Exception as e:
                logger.warning("light navigation feed validation failed: %s", e)

    async def dismiss_comply_gate(self) -> None:
        """Dismiss common LinkedIn overlay blocks/cookie comply notices."""
        if not self.page:
            return
        try:
            # Look for comply gates or cookies consent overlay buttons
            consent_btn = await self.page.query_selector("button.artdeco-global-alert-action, button.cookie-consent__agree")
            if consent_btn:
                await consent_btn.click()
                logger.info("Dismissed comply/consent cookie alert gate.")
        except Exception:
            pass

    async def validate_session(self) -> bool:
        """Checks if the cookies session is valid by navigating to feed."""
        await self.ensure_browser()
        try:
            await self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=20000)
            # Check if login input is visible, which means session expired
            login_form = await self.page.query_selector("input#username, input#password")
            if login_form or "linkedin.com/feed" not in self.page.url:
                logger.warning("Session validation failed: Login form found or url mismatch (%s)", self.page.url)
                return False
            return True
        except Exception as e:
            logger.error("Validation error: %s", e)
            return False

    async def save_cookies(self) -> None:
        """Saves current browser context cookies to database."""
        if not self.context:
            return
        db = await get_database()
        cookies = await self.context.cookies()
        encrypted = _encrypt_cookies(json.dumps(cookies))
        await db.linkedin_sessions.update_one(
            {"user_id": self.user_id},
            {"$set": {
                "cookies_encrypted": encrypted,
                "status": "connected",
                "last_validated_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }},
            upsert=True
        )
        logger.info("Successfully updated & encrypted cookies in DB for user: %s", self.user_id)

    async def close(self) -> None:
        """Gracefully closes Playwright browser session."""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.debug("Failed closing browser: %s", e)
        finally:
            self.page = self.context = self.browser = self.playwright = None


# Active warm sessions cache
_active_sessions: dict[str, LinkedInAccountSession] = {}


async def get_user_session(user_id: str) -> LinkedInAccountSession:
    """Returns a warm AccountSession for the given user_id."""
    if user_id not in _active_sessions:
        _active_sessions[user_id] = LinkedInAccountSession(user_id)
    session = _active_sessions[user_id]
    await session.ensure_browser()
    return session


async def restore_sessions_on_startup() -> None:
    """
    Pre-registers connected sessions from MongoDB so they are lazily warmed
    on first use. Does NOT launch browsers at startup (which fails on Windows
    due to ProactorEventLoop not being set during ASGI lifespan startup).
    """
    try:
        db = await get_database()
        sessions = await db.linkedin_sessions.find({"status": "connected"}).to_list(length=100)
        logger.info("Pre-registering %d LinkedIn sessions (lazy init — browsers start on first use)...", len(sessions))
        for s in sessions:
            user_id = s.get("user_id")
            if user_id and user_id not in _active_sessions:
                _active_sessions[user_id] = LinkedInAccountSession(user_id)
                logger.info("Session slot registered for user: %s", user_id)
    except Exception as e:
        logger.warning("restore_sessions_on_startup: could not pre-register sessions: %s", e)


async def close_all_active_sessions() -> None:
    """Closes all active Playwright sessions on shutdown."""
    logger.info("Closing all active LinkedIn Playwright sessions...")
    for user_id, session in list(_active_sessions.items()):
        try:
            await session.close()
            logger.info("Closed session for user: %s", user_id)
        except Exception as e:
            logger.error("Error closing session for user %s: %s", user_id, e)
    _active_sessions.clear()
