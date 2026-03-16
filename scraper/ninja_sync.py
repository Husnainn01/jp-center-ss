"""USS/NINJA sync: login → scrape → DB."""

import time
import asyncio
import os
from playwright.async_api import async_playwright
from ninja_login import ninja_login
from ninja_scraper import ninja_search_and_extract
from db import log_sync, get_site_credentials


async def run_ninja_sync():
    start = time.time()
    print("[ninja-sync] Starting USS/NINJA sync...")

    user_id, password = get_site_credentials("uss")
    if not user_id or not password:
        error = "USS credentials not configured"
        print(f"[ninja-sync] ERROR: {error}")
        log_sync(0, 0, 0, 0, 0, error, source="ninja")
        return

    headless = os.getenv("HEADLESS", "true").lower() == "true"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )

        try:
            print("[ninja-sync] Logging in...")
            ok = await ninja_login(context, user_id, password)
            if not ok:
                error = "NINJA login failed"
                print(f"[ninja-sync] ERROR: {error}")
                log_sync(0, 0, 0, 0, int((time.time() - start) * 1000), error, source="ninja")
                return

            print("[ninja-sync] Scraping...")
            scraped_ids = await ninja_search_and_extract(context)

            total = len(scraped_ids)
            duration_ms = int((time.time() - start) * 1000)
            log_sync(0, 0, 0, total, duration_ms, source="ninja")
            print(f"[ninja-sync] Complete in {duration_ms/1000:.1f}s — {total} vehicles")

        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            error_msg = str(e)[:500]
            print(f"[ninja-sync] ERROR: {error_msg}")
            log_sync(0, 0, 0, 0, duration_ms, error_msg, source="ninja")
            raise
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run_ninja_sync())
