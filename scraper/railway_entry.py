"""Railway entry point: reads SCRAPER_TYPE env var to run the correct scraper."""

import os
import sys

print(f"[railway] Starting scraper entry point...")
print(f"[railway] SCRAPER_TYPE = '{os.getenv('SCRAPER_TYPE', '')}'")
print(f"[railway] DATABASE_URL = {'set' if os.getenv('DATABASE_URL') else 'NOT SET'}")

SCRAPER_TYPE = os.getenv("SCRAPER_TYPE", "").lower()

if SCRAPER_TYPE == "aucnet":
    print("[railway] Loading aucnet scraper...")
    from run_aucnet import main
elif SCRAPER_TYPE == "ninja":
    print("[railway] Loading ninja scraper (all makers)...")
    from run_ninja import main
elif SCRAPER_TYPE == "ninja-jp-popular":
    print("[railway] Loading ninja JP popular scraper...")
    from run_ninja_jp_popular import main
elif SCRAPER_TYPE == "ninja-jp-other":
    print("[railway] Loading ninja JP other scraper...")
    from run_ninja_jp_other import main
elif SCRAPER_TYPE == "ninja-imported":
    print("[railway] Loading ninja imported scraper...")
    from run_ninja_imported import main
elif SCRAPER_TYPE == "taa":
    print("[railway] Loading taa scraper...")
    from run_taa import main
elif SCRAPER_TYPE == "iauc":
    print("[railway] Loading iauc scraper...")
    from run_iauc import main
else:
    print(f"ERROR: SCRAPER_TYPE must be one of: aucnet, ninja, ninja-jp-popular, ninja-jp-other, ninja-imported, taa, iauc. Got: '{SCRAPER_TYPE}'")
    sys.exit(1)

import asyncio
print(f"[railway] Running {SCRAPER_TYPE} scraper...")
asyncio.run(main())
