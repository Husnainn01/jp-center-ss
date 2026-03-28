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


PLACEHOLDER_PATTERNS = ["now_printing", "noimage", "no_image", "dummy", "blank", "placeholder"]

async def _download_and_upload_bf(page: Page, url: str, prefix: str) -> str | None:
    """Download image via authenticated browser and upload to R2. Skips placeholders."""
    if any(p in url.lower() for p in PLACEHOLDER_PATTERNS):
        return None
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
                await asyncio.sleep(5)  # Wait longer for images to render

                if "detail" not in new_page.url:
                    return False

                # Skip "Not Found" pages — vehicle may have been removed from iAUC
                page_text = await new_page.evaluate("() => document.body.innerText.substring(0, 300)")
                if "Not Found" in page_text:
                    return False

                # Extract images (filter out placeholder/now_printing images)
                imgs = await new_page.evaluate("""() => {
                    const placeholders = ['now_printing', 'noimage', 'no_image', 'dummy', 'blank', 'placeholder'];
                    return Array.from(document.querySelectorAll('img'))
                        .filter(i => {
                            if (!i.src || !i.src.includes('iauc_pic') || i.naturalWidth <= 100) return false;
                            const lower = i.src.toLowerCase();
                            return !placeholders.some(p => lower.includes(p));
                        })
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

    Opens detail pages via form submission to fetch exhibit sheet images.
    item_id format: uss-{bidNo}-{times}
    """
    missing = get_vehicles_missing_assets("uss")
    if not missing:
        print("[backfill] NINJA: all vehicles have images + sheets")
        return {"attempted": 0, "fixed": 0}

    sheets_missing = [v for v in missing if v["missing_sheet"]]
    images_missing = [v for v in missing if v["missing_image"]]
    print(f"[backfill] NINJA: {len(missing)} need backfill ({len(sheets_missing)} sheets, {len(images_missing)} images)")

    # Focus on vehicles missing sheets (most common gap for NINJA)
    to_fix = sheets_missing[:MAX_BACKFILL_PER_RUN]
    if not to_fix:
        print("[backfill] NINJA: no sheet backfill needed")
        return {"attempted": 0, "fixed": 0}

    # Make sure we're on a page with form1 (search results)
    has_form = await page.evaluate("() => !!document.getElementById('form1')")
    if not has_form:
        print("[backfill] NINJA: no form1 on page, cannot backfill sheets")
        return {"attempted": 0, "fixed": 0}

    fixed = 0
    errors = 0

    for vehicle in to_fix:
        if errors >= 5:
            print("[backfill] NINJA: too many errors, stopping")
            break

        # Parse item_id: uss-{bidNo}-{times}
        parts = vehicle["item_id"].split("-", 2)
        if len(parts) < 3:
            continue
        bid_no = parts[1]
        times = parts[2]

        try:
            # Submit form1 to open detail page in new tab
            new_page_promise = context.wait_for_event("page", timeout=10000)
            await page.evaluate("""(v) => {
                document.getElementById('carKindType').value = '1';
                document.getElementById('bidNo').value = v.bidNo;
                document.getElementById('auctionCount').value = v.times;
                document.getElementById('zaikoNo').value = '';
                document.getElementById('action').value = 'init';
                var form = document.getElementById('form1');
                form.setAttribute('action', './cardetail.action');
                form.setAttribute('target', '_blank');
                form.submit();
            }""", {"bidNo": bid_no, "times": times})

            detail_page = await new_page_promise
            await detail_page.wait_for_load_state("networkidle", timeout=10000)
            await asyncio.sleep(0.5)

            # Extract exhibit sheet
            sheet_url = await detail_page.evaluate("""() => {
                for (const img of document.querySelectorAll('img')) {
                    if (img.src && img.src.includes('get_ex_image')) return img.src;
                }
                return '';
            }""")

            await detail_page.close()

            if sheet_url:
                uploaded = await _download_and_upload_bf(page, sheet_url, "ninja-images")
                if uploaded:
                    update_vehicle_assets(vehicle["item_id"], None, [], uploaded)
                    fixed += 1
                    errors = 0
            else:
                errors = 0  # No sheet available, not an error

        except Exception as e:
            errors += 1
            # Close any extra pages
            for extra in context.pages[1:]:
                try:
                    await extra.close()
                except:
                    pass

    # Reset form target
    try:
        await page.evaluate("() => document.getElementById('form1')?.setAttribute('target', '')")
    except:
        pass

    print(f"[backfill] NINJA: {fixed}/{len(to_fix)} sheets fixed")
    return {"attempted": len(to_fix), "fixed": fixed}
