"""Sync engine: orchestrates scraping with chunk-based DB writes."""

import time
import asyncio
import os
from playwright.async_api import async_playwright

from login import ensure_session
from scraper import search_and_extract_all
from db import mark_expired, log_sync, get_credentials


async def run_sync():
    """Run a full scrape → sync cycle. Data is saved per-chunk inside the scraper."""
    start = time.time()
    print("[sync] Starting sync cycle...")

    user_id, password = get_credentials()
    if not user_id or not password:
        error = "No credentials configured"
        print(f"[sync] ERROR: {error}")
        log_sync(0, 0, 0, 0, 0, error, source="aucnet")
        return

    headless = os.getenv("HEADLESS", "true").lower() == "true"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )

        try:
            print("[sync] Logging in...")
            buy_href = await ensure_session(context, user_id, password)
            if not buy_href:
                error = "Login failed"
                print(f"[sync] ERROR: {error}")
                log_sync(0, 0, 0, 0, int((time.time() - start) * 1000), error, source="aucnet")
                return

            print("[sync] Scraping (chunk-based, saving to DB per page)...")
            page = await context.new_page()
            scraped_ids = await search_and_extract_all(page, buy_href)
            await page.close()

            total_scraped = len(scraped_ids) if isinstance(scraped_ids, (list, set)) else 0

            # Mark expired
            active_ids = set(str(i) for i in scraped_ids) if scraped_ids else set()
            expired_count = mark_expired(active_ids, source="aucnet") if active_ids else 0

            duration_ms = int((time.time() - start) * 1000)
            log_sync(0, 0, expired_count, total_scraped, duration_ms, source="aucnet")
            print(f"[sync] Complete in {duration_ms/1000:.1f}s — {total_scraped} scraped, {expired_count} expired")

        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            error_msg = str(e)[:500]
            print(f"[sync] ERROR: {error_msg}")
            log_sync(0, 0, 0, 0, duration_ms, error_msg, source="aucnet")
            raise
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run_sync())
