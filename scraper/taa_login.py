"""TAA (TC-webΣ) login manager."""

import asyncio
from playwright.async_api import BrowserContext

LOGIN_URL = "https://taacaa.jp/index-e.html"


async def taa_login(context: BrowserContext, number: str, user_id: str, password: str) -> bool:
    """Login to TAA. Returns True on success."""
    page = await context.new_page()
    try:
        await page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        await page.fill("#kainNo", number)
        await page.fill("#kainTantoId", user_id)
        await page.fill("#password", password)
        await page.evaluate("() => loginAction()")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(3)

        # Handle force-login
        body = await page.inner_text("body")
        if "already logged" in body.lower():
            await page.evaluate("() => compulsionLogin()")
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(3)

        # Keep page open — scraper will use it
        return "mypage" in page.url.lower() or "MypageTop" in page.url
    except Exception as e:
        print(f"  [taa] Login error: {e}")
        await page.close()
        return False
