"""USS/NINJA login manager."""

import asyncio
from playwright.async_api import BrowserContext

LOGIN_URL = "https://www.ninja-cartrade.jp/ninja/"


async def ninja_login(context: BrowserContext, user_id: str, password: str) -> bool:
    """Login to NINJA. Returns True on success."""
    page = await context.new_page()
    try:
        await page.goto(LOGIN_URL, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(2)
        await page.fill("#loginId", user_id)
        await page.fill("#password", password)
        await page.evaluate("() => login()")
        await asyncio.sleep(5)
        await page.wait_for_load_state("networkidle", timeout=15000)

        body = await page.inner_text("body")
        if "different user" in body.lower():
            await page.evaluate("""() => {
                for (const a of document.querySelectorAll('a'))
                    if (a.textContent.trim() === 'Login') { a.click(); return; }
            }""")
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(3)

        return "searchcondition" in page.url
    except Exception as e:
        print(f"  [ninja] Login error: {e}")
        await page.close()
        return False
