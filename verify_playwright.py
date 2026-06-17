import asyncio
import os
import sys

# Ensure parent directory is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.linkedin_outreach_service import (
    _safe_query_selector_text,
    _take_playwright_screenshot,
    _get_playwright,
    _launch_stealth_browser,
    _create_stealth_context
)

async def test_screenshot_generation():
    print("Testing Playwright screenshot generation inside container...")
    pw_func = await _get_playwright()
    pw = None
    browser = None
    try:
        pw = await pw_func().start()
        browser = await _launch_stealth_browser(pw, headless=True)
        context = await _create_stealth_context(browser)
        page = await context.new_page()
        await page.goto("about:blank")
        
        # Capture error screenshot
        file_path = await _take_playwright_screenshot(page, "test_error")
        print(f"Captured screenshot to: {file_path}")
        
        assert file_path != ""
        assert os.path.exists(file_path)
        assert os.path.getsize(file_path) > 0
        
        # Cleanup test file
        if os.path.exists(file_path):
            os.remove(file_path)
            print("Successfully verified and cleaned up screenshot file.")
            
        return True
    except Exception as e:
        print(f"Failed screenshot test: {e}")
        return False
    finally:
        if browser:
            await browser.close()
        if pw:
            await pw.stop()

async def test_selector_fallback():
    print("Testing selector fallback parsing...")
    # Mock page class with query_selector
    class MockElement:
        async def inner_text(self):
            return "Parsed Headline"
            
    class MockPage:
        async def query_selector(self, selector):
            if selector == ".pv-top-card-layout__headline":
                return MockElement()
            return None
            
    page = MockPage()
    selectors = [".non-existent-class", ".pv-top-card-layout__headline"]
    text = await _safe_query_selector_text(page, selectors, "Default")
    
    print(f"Fallback text parsed: {text}")
    assert text == "Parsed Headline"
    print("Selector fallback matching works perfectly.")
    return True

async def main():
    s1 = await test_selector_fallback()
    s2 = await test_screenshot_generation()
    if s1 and s2:
        print("ALL PLAYWRIGHT TESTS PASSED INSIDE CONTAINER.")
        sys.exit(0)
    else:
        print("SOME PLAYWRIGHT TESTS FAILED INSIDE CONTAINER.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
