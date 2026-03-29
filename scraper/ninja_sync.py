"""USS/NINJA sync: login → scrape → DB → cleanup expired → invalidate cache."""

import time
import asyncio
import os
import urllib.request
from playwright.async_api import async_playwright
from ninja_login import ninja_login
from ninja_scraper import ninja_search_and_extract
from db import log_sync, get_site_credentials, is_site_enabled

BACKEND_URL = os.getenv("BACKEND_URL", "https://skillful-grace-production-377c.up.railway.app")


def invalidate_cache():
    """Tell backend to clear its in-memory cache after sync."""
    try:
        req = urllib.request.Request(f"{BACKEND_URL}/api/cache/invalidate", method="POST",
                                     data=b"", headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
        print("[ninja-sync] Cache invalidated")
    except Exception as e:
        print(f"[ninja-sync] Cache invalidation failed (non-fatal): {e}")


async def run_ninja_sync(makers: list[str] | None = None):
    if not is_site_enabled("uss"):
        print("[ninja-sync] USS/NINJA scraper is DISABLED. Skipping.")
        return

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

            # ── Phase 1: Get ALL vehicle data + photos (no detail pages) ──
            print("[ninja-sync] Phase 1: Scraping all vehicle data...")
            phase1_start = time.time()
            scraped_ids = await ninja_search_and_extract(context, makers=makers)
            total = len(scraped_ids)
            phase1_time = time.time() - phase1_start
            print(f"[ninja-sync] Phase 1 done: {total} vehicles in {phase1_time/60:.1f} min")

            # Invalidate cache so customers see vehicles immediately
            invalidate_cache()

            # ── Phase 2: Backfill exhibit sheets (detail pages with re-login) ──
            print("[ninja-sync] Phase 2: Backfilling exhibit sheets...")
            phase2_start = time.time()
            try:
                from backfill import backfill_ninja
                page = context.pages[-1] if context.pages else await context.new_page()
                bf_result = await backfill_ninja(page, context)
                phase2_time = time.time() - phase2_start
                print(f"[ninja-sync] Phase 2 done: {bf_result['fixed']}/{bf_result['attempted']} sheets in {phase2_time/60:.1f} min")
            except Exception as be:
                print(f"[ninja-sync] Phase 2 error (non-fatal): {be}")

            # Invalidate cache again after sheets are added
            invalidate_cache()

            # Verify completeness
            try:
                from verify import get_db_counts, log_completeness
                log_completeness("uss", get_db_counts("uss"))
            except Exception as ve:
                print(f"[ninja-sync] Verify error (non-fatal): {ve}")

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
