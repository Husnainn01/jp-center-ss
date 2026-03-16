"""TAA sync: orchestrates login → scrape → DB updates."""

import time
import asyncio
import os
from playwright.async_api import async_playwright
from taa_login import taa_login
from taa_scraper import taa_search_and_extract
from db import mark_expired, log_sync, get_site_credentials, is_site_enabled


def get_taa_credentials():
    """Get TAA credentials. TAA needs 3 fields: number is stored in user_id as 'NUMBER:ID'."""
    user_id, password = get_site_credentials("taa")
    if not user_id:
        return "", "", ""
    parts = user_id.split(":")
    if len(parts) == 2:
        return parts[0], parts[1], password
    return user_id, "", password


async def run_taa_sync():
    """Full TAA scrape cycle."""
    if not is_site_enabled("taa"):
        print("[taa-sync] TAA scraper is DISABLED. Skipping.")
        return

    start = time.time()
    print("[taa-sync] Starting TAA sync...")

    number, user_id, password = get_taa_credentials()
    if not number or not password:
        error = "TAA credentials not configured"
        print(f"[taa-sync] ERROR: {error}")
        log_sync(0, 0, 0, 0, 0, error, source="taa")
        return

    headless = os.getenv("HEADLESS", "true").lower() == "true"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )

        try:
            # Login
            print("[taa-sync] Logging in...")
            ok = await taa_login(context, number, user_id, password)
            if not ok:
                error = "TAA login failed"
                print(f"[taa-sync] ERROR: {error}")
                log_sync(0, 0, 0, 0, int((time.time() - start) * 1000), error, source="taa")
                return

            print("[taa-sync] Login OK. Scraping...")

            # Scrape — data saved per-page inside scraper
            scraped_ids = await taa_search_and_extract(context)

            total = len(scraped_ids)
            duration_ms = int((time.time() - start) * 1000)
            log_sync(0, 0, 0, total, duration_ms, source="taa")
            print(f"[taa-sync] Complete in {duration_ms/1000:.1f}s — {total} vehicles")

        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            error_msg = str(e)[:500]
            print(f"[taa-sync] ERROR: {error_msg}")
            log_sync(0, 0, 0, 0, duration_ms, error_msg, source="taa")
            raise
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run_taa_sync())
