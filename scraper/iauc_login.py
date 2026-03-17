"""iAUC login manager."""

import asyncio
from playwright.async_api import Page


LOGIN_URL = "https://www.iauc.co.jp/service/"


async def _safe_wait(page: Page, timeout=15000):
    """Wait for networkidle, ignore timeout (SPA may never idle)."""
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout)
    except:
        pass


async def iauc_login(page: Page, user_id: str, password: str) -> bool:
    """Login to iAUC. Handles force-login. Returns True on success."""
    try:
        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # Click LOGIN link
        await page.evaluate("""() => {
            document.querySelectorAll('a').forEach(el => {
                if ((el.textContent || '').trim().includes('LOGIN')) el.click();
            });
        }""")
        await asyncio.sleep(3)

        # Fill credentials
        await page.fill('input[name="id"]', user_id)
        await page.fill('input[name="password"]', password)
        await page.evaluate("""() => {
            document.querySelectorAll('button, input, a').forEach(el => {
                if ((el.value || el.textContent || '').trim().includes('LOGIN')) el.click();
            });
        }""")
        await _safe_wait(page, 15000)
        await asyncio.sleep(3)

        # Handle force-login
        body = await page.inner_text("body")
        if "はい Yes" in body:
            print("  [iauc] Force login — disconnecting existing sessions...")
            await page.click(".button-yes")
            await _safe_wait(page, 15000)
            await asyncio.sleep(5)

        # Switch to English
        await page.evaluate("() => { const el = document.querySelector('a.jp'); if (el) el.click(); }")
        await _safe_wait(page, 10000)
        await asyncio.sleep(3)

        return "vehicle" in page.url

    except Exception as e:
        print(f"  [iauc] Login error: {e}")
        return False


async def iauc_logout(page: Page):
    """Logout from iAUC to avoid force-login next time."""
    try:
        await page.evaluate("""() => {
            document.querySelectorAll('a').forEach(a => {
                if (a.textContent.trim().includes('Logout')) a.click();
            });
        }""")
        await asyncio.sleep(3)
    except:
        pass
