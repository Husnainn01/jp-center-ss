"""iAUC sync: login → scrape → DB."""

import time
import asyncio
import os
from playwright.async_api import async_playwright
from iauc_login import iauc_login, iauc_logout
from iauc_scraper import iauc_search_and_extract
from db import log_sync, get_site_credentials, is_site_enabled


async def run_iauc_sync():
    """Full iAUC scrape cycle."""
    if not is_site_enabled("iauc"):
        print("[iauc-sync] iAUC scraper is DISABLED. Skipping.")
        return

    start = time.time()
    print("[iauc-sync] Starting iAUC sync...")

    user_id, password = get_site_credentials("iauc")
    if not user_id or not password:
        error = "iAUC credentials not configured"
        print(f"[iauc-sync] ERROR: {error}")
        log_sync(0, 0, 0, 0, 0, error, source="iauc")
        return

    headless = os.getenv("HEADLESS", "true").lower() == "true"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )

        try:
            page = await context.new_page()

            print("[iauc-sync] Logging in...")
            ok = await iauc_login(page, user_id, password)
            if not ok:
                error = "iAUC login failed"
                print(f"[iauc-sync] ERROR: {error}")
                log_sync(0, 0, 0, 0, int((time.time() - start) * 1000), error, source="iauc")
                return

            print("[iauc-sync] Scraping...")
            scraped_ids = await iauc_search_and_extract(page, context)

            total = len(scraped_ids)
            duration_ms = int((time.time() - start) * 1000)
            log_sync(0, 0, 0, total, duration_ms, source="iauc")
            print(f"[iauc-sync] Complete in {duration_ms/1000:.1f}s — {total} vehicles")

            # Logout to avoid force-login next time
            await iauc_logout(page)

        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            error_msg = str(e)[:500]
            print(f"[iauc-sync] ERROR: {error_msg}")
            log_sync(0, 0, 0, 0, duration_ms, error_msg, source="iauc")
            # Try to logout even on error
            try:
                await iauc_logout(context.pages[0] if context.pages else await context.new_page())
            except:
                pass
            raise
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run_iauc_sync())
