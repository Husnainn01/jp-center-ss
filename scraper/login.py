"""Login manager: handles authentication and session cookies."""

import os
import json
import asyncio
from playwright.async_api import async_playwright, BrowserContext, Page

LOGIN_URL = "https://www.aucneostation.com/"
COOKIES_PATH = os.path.join(os.path.dirname(__file__), "session.json")


async def fresh_login(context: BrowserContext, user_id: str, password: str) -> str | None:
    """Perform a fresh login. Returns the buy_href URL or None on failure."""
    page = await context.new_page()

    try:
        await page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
        await page.fill("#userid-pc", user_id)
        await page.fill("#password-pc", password)
        await page.click("button[type='submit']")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(2)

        # Handle force-login (existing session conflict)
        if "login-error-force" in page.url:
            force_btn = await page.query_selector("input[name='force_login']")
            if force_btn:
                await force_btn.click()
                await page.wait_for_load_state("networkidle", timeout=30000)
                await asyncio.sleep(3)

        if "login-error" in page.url or "timeout" in page.url:
            return None

        # Extract the Buy Menu URL (contains auth token)
        buy_href = await page.evaluate("""() => {
            for (const a of document.querySelectorAll('a')) {
                if (a.textContent.trim().includes('買いメニュー')) return a.href;
            }
            return null;
        }""")

        # Save cookies
        cookies = await context.cookies()
        with open(COOKIES_PATH, "w") as f:
            json.dump(cookies, f)

        return buy_href

    finally:
        await page.close()


async def load_cookies(context: BrowserContext) -> bool:
    """Load saved cookies into the browser context. Returns True if cookies exist."""
    if not os.path.exists(COOKIES_PATH):
        return False

    try:
        with open(COOKIES_PATH) as f:
            cookies = json.load(f)
        await context.add_cookies(cookies)
        return True
    except (json.JSONDecodeError, FileNotFoundError):
        return False


async def ensure_session(context: BrowserContext, user_id: str, password: str) -> str | None:
    """Ensure we have a valid session. Returns buy_href URL."""
    # Try loading cookies first
    has_cookies = await load_cookies(context)

    if has_cookies:
        # Try to access the member page with existing cookies
        page = await context.new_page()
        try:
            await page.goto(LOGIN_URL + "member", wait_until="networkidle", timeout=15000)
            await asyncio.sleep(2)

            if "/member" in page.url and "login" not in page.url.replace("/member", ""):
                # Session is valid — extract buy URL
                buy_href = await page.evaluate("""() => {
                    for (const a of document.querySelectorAll('a')) {
                        if (a.textContent.trim().includes('買いメニュー')) return a.href;
                    }
                    return null;
                }""")
                if buy_href:
                    return buy_href
        except Exception:
            pass
        finally:
            await page.close()

    # Cookies expired or missing — do fresh login
    return await fresh_login(context, user_id, password)
