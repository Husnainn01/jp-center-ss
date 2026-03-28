"""Independent entry point for iAUC scraper.

Runs two modes automatically:
  Delta mode   — every 30 min during the day (small batches, gentle)
  Overnight    — cron at 23:00 JST, full pass with high concurrency
"""

import os
import asyncio
import traceback
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()

from iauc_sync import run_iauc_sync
from jst import is_overnight_window
from cleanup import run_cleanup

MAX_RETRIES = 3
RETRY_DELAY = 60


async def run_with_retry():
    """Run delta sync with retry logic (daytime mode)."""
    os.environ["IAUC_OVERNIGHT"] = "false"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            await run_iauc_sync()
            print("[iauc] Sync completed successfully")
            return
        except Exception as e:
            print(f"[iauc] Attempt {attempt}/{MAX_RETRIES} failed: {e}")
            traceback.print_exc()
            if attempt < MAX_RETRIES:
                print(f"[iauc] Retrying in {RETRY_DELAY}s...")
                await asyncio.sleep(RETRY_DELAY)
            else:
                print("[iauc] All retries exhausted. Will try again at next scheduled interval.")


async def run_overnight():
    """
    Full overnight pass — called by cron at 23:00 JST.
    Sets IAUC_OVERNIGHT=true so scraper uses high limits + parallel tabs.
    Resets to false when done so daytime delta resumes normally.
    """
    print("[iauc] ── Overnight full pass starting ──")
    os.environ["IAUC_OVERNIGHT"] = "true"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            await run_iauc_sync()
            print("[iauc] ── Overnight full pass complete ──")
            return
        except Exception as e:
            print(f"[iauc] Overnight attempt {attempt}/{MAX_RETRIES} failed: {e}")
            traceback.print_exc()
            if attempt < MAX_RETRIES:
                print(f"[iauc] Retrying overnight in {RETRY_DELAY}s...")
                await asyncio.sleep(RETRY_DELAY)
            else:
                print("[iauc] Overnight retries exhausted.")
    os.environ["IAUC_OVERNIGHT"] = "false"


async def main():
    interval = int(os.getenv("IAUC_INTERVAL_MINUTES", "30"))

    print(f"[iauc] Starting iAUC scraper (delta interval: {interval}m, overnight cron: 23:00 JST)")

    # If we start up during the overnight window, run a full pass immediately
    if is_overnight_window():
        print("[iauc] Starting inside overnight window — running full pass first...")
        await run_overnight()
    else:
        print("[iauc] Running initial delta sync...")
        await run_with_retry()

    scheduler = AsyncIOScheduler()

    # Delta sync — every N minutes during the day
    scheduler.add_job(
        run_with_retry,
        "interval",
        minutes=interval,
        id="iauc_delta",
    )

    # Overnight full pass — every day at 23:00 JST (11pm)
    # Scraper switches to high limits + 15 parallel tabs
    # All 40k vehicles done by ~03:30 JST, panel is fresh for morning
    scheduler.add_job(
        run_overnight,
        "cron",
        hour=23,
        minute=0,
        timezone="Asia/Tokyo",
        id="iauc_overnight",
    )

    # Daily cleanup — 11:00 JST, delete yesterday and older auctions + images
    scheduler.add_job(
        run_cleanup,
        "cron",
        hour=11,
        minute=0,
        timezone="Asia/Tokyo",
        id="iauc_cleanup",
    )

    scheduler.start()
    print(f"[iauc] Scheduler running.")
    print(f"[iauc]   Delta     → every {interval} min")
    print(f"[iauc]   Overnight → 23:00 JST daily (full 40k pass)")
    print(f"[iauc]   Cleanup   → 11:00 JST daily (delete expired auctions)")

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        print("\n[iauc] Shutting down...")
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
