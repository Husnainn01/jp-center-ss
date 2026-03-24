"""Backfill missing images and exhibit sheets for vehicles already in DB.

Runs AFTER the main scrape, in the same authenticated browser session.
Fetches detail pages for vehicles that have no image_url or no exhibit_sheet,
extracts images, uploads to R2, and updates the DB record.
"""

import asyncio
import base64
import re
from playwright.async_api import Page, BrowserContext
from db import get_vehicles_missing_assets, update_vehicle_assets
from storage import upload_image

MAX_BACKFILL_PER_RUN = 200  # cap per run to avoid overloading the site
CONCURRENT_TABS = 5


async def _download_and_upload_bf(page: Page, url: str, prefix: str) -> str | None:
    """Download image via authenticated browser and upload to R2."""
    try:
        result = await page.evaluate("""async (url) => {
            try {
                const res = await fetch(url, { credentials: 'include' });
                if (!res.ok) return null;
                const blob = await res.blob();
                const reader = new FileReader();
                return new Promise(r => { reader.onloadend = () => r(reader.result); reader.readAsDataURL(blob); });
            } catch { return null; }
        }""", url)
        if result and result.startswith("data:"):
            b64 = result.split(",", 1)[1]
            img_bytes = base64.b64decode(b64)
            if len(img_bytes) > 500:
                return upload_image(img_bytes, prefix, url)
        return None
    except:
        return None


# ── iAUC Backfill ───────────────────────────────────────────────────────────

async def backfill_iauc(page: Page, context: BrowserContext) -> dict:
    """Backfill missing images/sheets for iAUC vehicles using the current session."""
    missing = get_vehicles_missing_assets("iauc")
    if not missing:
        print("[backfill] iAUC: all vehicles have images + sheets")
        return {"attempted": 0, "fixed": 0}

    print(f"[backfill] iAUC: {len(missing)} vehicles need backfill (processing up to {MAX_BACKFILL_PER_RUN})")
    missing = missing[:MAX_BACKFILL_PER_RUN]

    # Get __tid from current page session
    tid = await page.evaluate("""() => {
        for (const a of document.querySelectorAll('a[href*="__tid"]')) {
            const m = a.href.match(/__tid=([^&#]+)/);
            if (m) return m[1];
        }
        return '';
    }""")

    if not tid:
        # Try to get tid from any link on the page
        tid = await page.evaluate("""() => {
            const m = document.body.innerHTML.match(/__tid=([a-f0-9]+)/);
            return m ? m[1] : '';
        }""")

    if not tid:
        print("[backfill] iAUC: no __tid found, cannot backfill")
        return {"attempted": 0, "fixed": 0}

    fixed = 0
    semaphore = asyncio.Semaphore(CONCURRENT_TABS)

    known_makers = [
        "TOYOTA", "LEXUS", "NISSAN", "HONDA", "MAZDA", "MITSUBISHI",
        "SUBARU", "DAIHATSU", "SUZUKI", "BMW", "MERCEDES-BENZ", "AUDI",
        "VOLKSWAGEN", "PORSCHE", "ISUZU", "HINO", "VOLVO", "JAGUAR",
        "FORD", "GM", "CHRYSLER", "ALFA ROMEO", "FIAT", "FERRARI",
        "MASERATI", "OPEL", "SMART", "ROVER", "BENTLEY", "TESLA",
        "PEUGEOT", "RENAULT", "CITROEN", "LAMBORGHINI", "BYD",
    ]

    async def backfill_one(vehicle: dict) -> bool:
        """Fetch images for one vehicle. Returns True if any asset was filled."""
        async with semaphore:
            vid = vehicle["item_id"].replace("iauc-", "")
            new_page = await context.new_page()
            try:
                detail_url = f"https://www.iauc.co.jp/detail/?vehicleId={vid}&owner_id=&from=vehicle&id=&__tid={tid}"
                await new_page.goto(detail_url, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(2)

                if "detail" not in new_page.url:
                    return False

                # Extract images
                imgs = await new_page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('img'))
                        .filter(i => i.src && i.src.includes('iauc_pic') && i.naturalWidth > 100)
                        .map(i => ({ src: i.src, filename: i.src.split('?')[0].split('/').pop().toUpperCase() }));
                }""")

                car_urls = []
                sheet_url = None
                seen_urls = set()
                for img in imgs:
                    base_url = img['src'].split('?')[0]
                    if base_url in seen_urls:
                        continue
                    seen_urls.add(base_url)
                    fn = img['filename']
                    if re.match(r'^A\d+\.JPG', fn) or '_scan.' in img['src'].lower():
                        if not sheet_url:
                            sheet_url = img['src']
                    else:
                        if len(car_urls) < 4:
                            car_urls.append(img['src'])

                # Upload what we found
                new_image_url = None
                new_images = []
                new_sheet = None

                if car_urls and vehicle["missing_image"]:
                    upload_results = await asyncio.gather(
                        *[_download_and_upload_bf(new_page, u, "iauc-images") for u in car_urls],
                        return_exceptions=True,
                    )
                    new_images = [r for r in upload_results if r and not isinstance(r, Exception)]
                    new_image_url = new_images[0] if new_images else None

                if sheet_url and vehicle["missing_sheet"]:
                    new_sheet = await _download_and_upload_bf(new_page, sheet_url, "iauc-images")

                if new_image_url or new_images or new_sheet:
                    update_vehicle_assets(
                        vehicle["item_id"],
                        new_image_url,
                        new_images,
                        new_sheet,
                    )
                    return True
                return False
            except Exception as e:
                print(f"[backfill] iAUC {vid}: error: {e}")
                return False
            finally:
                await new_page.close()

    results = await asyncio.gather(
        *[backfill_one(v) for v in missing],
        return_exceptions=True,
    )
    fixed = sum(1 for r in results if r is True)

    print(f"[backfill] iAUC: {fixed}/{len(missing)} vehicles fixed")
    return {"attempted": len(missing), "fixed": fixed}


# ── NINJA Backfill ──────────────────────────────────────────────────────────

async def backfill_ninja(page: Page, context: BrowserContext) -> dict:
    """Backfill missing exhibit sheets for NINJA/USS vehicles.

    NINJA exhibit sheets require form submission from a results page.
    We re-navigate to the detail page using the vehicle's bidNo and site info
    extracted from the item_id (format: uss-{bidNo}-{times}).
    """
    missing = get_vehicles_missing_assets("uss")
    if not missing:
        print("[backfill] NINJA: all vehicles have images + sheets")
        return {"attempted": 0, "fixed": 0}

    # NINJA list pages already extract thumbnails; most missing assets are exhibit sheets
    sheets_missing = [v for v in missing if v["missing_sheet"]]
    images_missing = [v for v in missing if v["missing_image"]]
    print(f"[backfill] NINJA: {len(missing)} vehicles need backfill ({len(sheets_missing)} sheets, {len(images_missing)} images)")

    # For NINJA, exhibit sheets require authenticated form submission which is complex.
    # The most reliable approach: re-open the detail page via seniCarDetail JS call.
    # However, this requires being on a results page with the vehicle listed.
    # A simpler approach: use the exhibit sheet URL pattern if we can derive it.

    # For now, focus on vehicles missing images (thumbnail from list page)
    # Sheet backfill for NINJA requires a more complex flow (future enhancement)
    to_fix = images_missing[:MAX_BACKFILL_PER_RUN]
    if not to_fix:
        print("[backfill] NINJA: no image backfill needed (sheets require detail page — skipped)")
        return {"attempted": 0, "fixed": 0}

    fixed = 0
    semaphore = asyncio.Semaphore(CONCURRENT_TABS)

    async def backfill_one(vehicle: dict) -> bool:
        async with semaphore:
            # NINJA images are fetched from the list page during scrape.
            # If the image was missed, we'd need to re-scrape that specific maker.
            # For now, just log it — the next scrape cycle will pick it up
            # since get_existing_item_ids no longer filters by image_url.
            return False

    results = await asyncio.gather(
        *[backfill_one(v) for v in to_fix],
        return_exceptions=True,
    )
    fixed = sum(1 for r in results if r is True)

    print(f"[backfill] NINJA: {fixed}/{len(to_fix)} vehicles fixed")
    return {"attempted": len(to_fix), "fixed": fixed}
