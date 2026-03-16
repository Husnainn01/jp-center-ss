"""Independent entry point for NINJA/USS scraper."""

import os
import asyncio
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()

from ninja_sync import run_ninja_sync


async def main():
    interval = int(os.getenv("NINJA_INTERVAL_MINUTES", "30"))

    print(f"[ninja] Starting NINJA/USS scraper (interval: {interval}m)")
    print("[ninja] Running initial sync...")
    await run_ninja_sync()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_ninja_sync, "interval", minutes=interval, id="ninja_sync")
    scheduler.start()

    print(f"[ninja] Scheduler running. Next sync in {interval} minutes.")

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        print("\n[ninja] Shutting down...")
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
