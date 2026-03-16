"""Independent entry point for Aucnet scraper."""

import os
import asyncio
import traceback
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()

from sync import run_sync

MAX_RETRIES = 3
RETRY_DELAY = 60  # seconds


async def run_with_retry():
    """Run sync with retry logic."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            await run_sync()
            print("[aucnet] Sync completed successfully")
            return
        except Exception as e:
            print(f"[aucnet] Attempt {attempt}/{MAX_RETRIES} failed: {e}")
            traceback.print_exc()
            if attempt < MAX_RETRIES:
                print(f"[aucnet] Retrying in {RETRY_DELAY}s...")
                await asyncio.sleep(RETRY_DELAY)
            else:
                print("[aucnet] All retries exhausted. Will try again at next scheduled interval.")


async def main():
    interval = int(os.getenv("AUCNET_INTERVAL_MINUTES", "30"))

    print(f"[aucnet] Starting Aucnet scraper (interval: {interval}m)")
    print("[aucnet] Running initial sync...")
    await run_with_retry()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_with_retry, "interval", minutes=interval, id="aucnet_sync")
    scheduler.start()

    print(f"[aucnet] Scheduler running. Next sync in {interval} minutes.")

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        print("\n[aucnet] Shutting down...")
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
