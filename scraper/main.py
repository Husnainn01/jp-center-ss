"""Entry point: runs ALL scrapers on a schedule (local dev convenience)."""

import os
import asyncio
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()

from sync import run_sync
from ninja_sync import run_ninja_sync
from taa_sync import run_taa_sync
from iauc_sync import run_iauc_sync
from cleanup import run_cleanup


async def run_all():
    """Run all 4 scrapers sequentially."""
    print("[main] --- Running Aucnet ---")
    try:
        await run_sync()
    except Exception as e:
        print(f"[main] Aucnet failed: {e}")

    print("[main] --- Running NINJA/USS ---")
    try:
        await run_ninja_sync()
    except Exception as e:
        print(f"[main] NINJA failed: {e}")

    print("[main] --- Running TAA ---")
    try:
        await run_taa_sync()
    except Exception as e:
        print(f"[main] TAA failed: {e}")

    print("[main] --- Running iAUC ---")
    try:
        await run_iauc_sync()
    except Exception as e:
        print(f"[main] iAUC failed: {e}")

    print("[main] --- All scrapers done ---")


async def main():
    interval = int(os.getenv("POLL_INTERVAL_MINUTES", "30"))

    print(f"[main] Starting ALL scrapers (interval: {interval}m)")
    print("[main] Running initial sync...")
    await run_all()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_all, "interval", minutes=interval, id="sync_all")

    # Weekday cleanup — 11:00 JST Mon-Thu, skip weekends (no auctions)
    scheduler.add_job(
        run_cleanup,
        "cron",
        day_of_week="mon-fri",
        hour=11,
        minute=0,
        timezone="Asia/Tokyo",
        id="daily_cleanup",
    )

    scheduler.start()

    print(f"[main] Scheduler running. Next sync in {interval} minutes.")
    print(f"[main]   Cleanup → 11:00 JST daily (delete expired auctions)")
    print("[main] Press Ctrl+C to stop.\n")

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        print("\n[main] Shutting down...")
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
