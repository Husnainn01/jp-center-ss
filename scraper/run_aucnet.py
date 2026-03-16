"""Independent entry point for Aucnet scraper."""

import os
import asyncio
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()

from sync import run_sync


async def main():
    interval = int(os.getenv("AUCNET_INTERVAL_MINUTES", "30"))

    print(f"[aucnet] Starting Aucnet scraper (interval: {interval}m)")
    print("[aucnet] Running initial sync...")
    await run_sync()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_sync, "interval", minutes=interval, id="aucnet_sync")
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
