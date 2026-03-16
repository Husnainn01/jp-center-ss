"""Railway entry point: reads SCRAPER_TYPE env var to run the correct scraper."""

import os
import sys

SCRAPER_TYPE = os.getenv("SCRAPER_TYPE", "").lower()

if SCRAPER_TYPE == "aucnet":
    from run_aucnet import main
elif SCRAPER_TYPE == "ninja":
    from run_ninja import main
elif SCRAPER_TYPE == "taa":
    from run_taa import main
else:
    print(f"ERROR: SCRAPER_TYPE must be 'aucnet', 'ninja', or 'taa'. Got: '{SCRAPER_TYPE}'")
    sys.exit(1)

import asyncio
asyncio.run(main())
