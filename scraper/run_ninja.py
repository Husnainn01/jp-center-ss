"""Independent entry point for NINJA/USS scraper."""

import os
import asyncio
import traceback
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()

from ninja_sync import run_ninja_sync
from cleanup import run_cleanup

MAX_RETRIES = 3
RETRY_DELAY = 60  # seconds


async def run_with_retry():
    """Run sync with retry logic."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            await run_ninja_sync()
            print("[ninja] Sync completed successfully")
            return
        except Exception as e:
            print(f"[ninja] Attempt {attempt}/{MAX_RETRIES} failed: {e}")
            traceback.print_exc()
            if attempt < MAX_RETRIES:
                print(f"[ninja] Retrying in {RETRY_DELAY}s...")
                await asyncio.sleep(RETRY_DELAY)
            else:
                print("[ninja] All retries exhausted. Will try again at next scheduled interval.")


async def main():
    interval = int(os.getenv("NINJA_INTERVAL_MINUTES", "30"))

    print(f"[ninja] Starting NINJA/USS scraper (interval: {interval}m)")
    print("[ninja] Running initial sync...")
    await run_with_retry()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_with_retry, "interval", minutes=interval, id="ninja_sync")

    # Daily cleanup — 11:00 JST, delete yesterday and older auctions + images
    scheduler.add_job(
        run_cleanup,
        "cron",
        hour=11,
        minute=0,
        timezone="Asia/Tokyo",
        id="ninja_cleanup",
    )

    scheduler.start()

    print(f"[ninja] Scheduler running. Next sync in {interval} minutes.")
    print(f"[ninja]   Cleanup → 11:00 JST daily (delete expired auctions)")

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        print("\n[ninja] Shutting down...")
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
