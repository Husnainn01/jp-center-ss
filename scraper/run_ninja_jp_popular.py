"""Entry point for NINJA/USS scraper — JP popular makers."""

import os
import asyncio
import traceback
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()

from ninja_sync import run_ninja_sync

MAKERS = ["TOYOTA", "NISSAN", "HONDA", "MAZDA", "SUBARU"]

MAX_RETRIES = 3
RETRY_DELAY = 60


async def run_with_retry():
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            await run_ninja_sync(makers=MAKERS)
            print("[ninja-jp-popular] Sync completed successfully")
            return
        except Exception as e:
            print(f"[ninja-jp-popular] Attempt {attempt}/{MAX_RETRIES} failed: {e}")
            traceback.print_exc()
            if attempt < MAX_RETRIES:
                print(f"[ninja-jp-popular] Retrying in {RETRY_DELAY}s...")
                await asyncio.sleep(RETRY_DELAY)
            else:
                print("[ninja-jp-popular] All retries exhausted.")


async def main():
    interval = int(os.getenv("NINJA_INTERVAL_MINUTES", "30"))

    print(f"[ninja-jp-popular] Starting (interval: {interval}m, makers: {MAKERS})")
    print("[ninja-jp-popular] Running initial sync...")
    await run_with_retry()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_with_retry, "interval", minutes=interval, id="ninja_jp_popular_sync")
    scheduler.start()

    print(f"[ninja-jp-popular] Scheduler running. Next sync in {interval} minutes.")

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        print("\n[ninja-jp-popular] Shutting down...")
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
