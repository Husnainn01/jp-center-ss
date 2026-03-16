"""Independent entry point for TAA scraper."""

import os
import asyncio
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()

from taa_sync import run_taa_sync


async def main():
    interval = int(os.getenv("TAA_INTERVAL_MINUTES", "30"))

    print(f"[taa] Starting TAA scraper (interval: {interval}m)")
    print("[taa] Running initial sync...")
    await run_taa_sync()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_taa_sync, "interval", minutes=interval, id="taa_sync")
    scheduler.start()

    print(f"[taa] Scheduler running. Next sync in {interval} minutes.")

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        print("\n[taa] Shutting down...")
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
