"""TAA scraper: search → paginate → open detail popups (parallel) → extract data + upload images.
Optimized: parallel popup extraction (3 concurrent), skip existing vehicles.
Chunk-based: saves each page of results to DB immediately."""

import asyncio
import os
import hashlib
import base64
import re
from playwright.async_api import Page, BrowserContext
from db import upsert_auctions, get_existing_item_ids
from storage import upload_image

MAX_CONCURRENT_POPUPS = 3


async def taa_search_and_extract(context: BrowserContext) -> list[str]:
    """Full TAA scrape flow. Returns list of scraped item_ids."""
    page = context.pages[0] if context.pages else await context.new_page()

    # Load existing vehicle IDs to skip re-scraping
    existing_ids = get_existing_item_ids("taa")
    print(f"  [taa] {len(existing_ids)} existing vehicles in DB (will skip)")

    # Navigate to search via nav image
    print("  [taa] Navigating to search...")
    await page.click('img[name="navi01"]')
    await page.wait_for_load_state("networkidle", timeout=30000)
    await asyncio.sleep(5)

    if "CarMakerSelect" not in page.url:
        print(f"  [taa] Failed to reach search page: {page.url}")
        return []

    # Check ALL day checkboxes (Mon-Sat)
    await page.evaluate("""() => {
        document.querySelectorAll('input[name="checkHallYobi"]').forEach(cb => {
            if (!cb.checked) cb.click();
        });
    }""")
    await asyncio.sleep(2)

    day_count = await page.evaluate("() => document.querySelectorAll('input[name=\"checkHallYobi\"]:checked').length")
    print(f"  [taa] Selected {day_count} days")

    # Select all makers
    await page.evaluate("() => document.querySelectorAll('input[name=\"carMakerArr\"]').forEach(cb => { if(!cb.checked) cb.click(); })")

    # Wait for models to load after maker selection
    model_count = 0
    for i in range(10):
        await asyncio.sleep(2)
        model_count = await page.evaluate("() => document.querySelectorAll('input[name=\"syasyu2\"]').length")
        if model_count > 0:
            break
        print(f"  [taa] Waiting for models to load... ({i+1})")

    maker_count = await page.evaluate("() => document.querySelectorAll('input[name=\"carMakerArr\"]:checked').length")
    print(f"  [taa] Selected {maker_count} makers, {model_count} models available")

    # Select all models
    await page.evaluate("() => document.querySelectorAll('input[name=\"syasyu2\"]').forEach(cb => { if(!cb.checked) cb.click(); })")
    await asyncio.sleep(2)

    checked_models = await page.evaluate("() => document.querySelectorAll('input[name=\"syasyu2\"]:checked').length")
    print(f"  [taa] Checked {checked_models} models")

    # Submit search
    await page.evaluate("""() => {
        var fm = document.getElementById("SearchForm");
        fm.action = "./CarListSpecification.do";
        if (typeof formAddKey === 'function') formAddKey(fm);
        fm.submit();
    }""")
    await page.wait_for_load_state("networkidle", timeout=60000)
    await asyncio.sleep(5)

    if "CarListSpecification" not in page.url:
        print(f"  [taa] Search failed: {page.url}")
        return []

    # Get total count
    total_text = await page.evaluate("""() => {
        const m = document.body.innerText.match(/(\\d[\\d,]*)\\s*Total/);
        return m ? m[1].replace(/,/g, '') : '0';
    }""")
    total = int(total_text)
    print(f"  [taa] Total results: {total}")

    if total == 0:
        return []

    # Paginate and extract
    all_ids = []
    page_num = 0
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_POPUPS)

    while True:
        page_num += 1

        # Get vehicle count on this page
        vehicle_count = await page.evaluate("""() => {
            const links = document.querySelectorAll('a[href*="popDetail"]');
            const ids = new Set();
            links.forEach(a => {
                const m = a.href.match(/popDetail\\((\\d+)\\)/);
                if (m) ids.add(m[1]);
            });
            return ids.size;
        }""")

        if vehicle_count == 0:
            break

        print(f"  [taa] Page {page_num}: {vehicle_count} vehicles on page")

        # Extract vehicles in parallel using popups
        async def extract_one(idx):
            async with semaphore:
                return await _extract_vehicle_detail(context, page, idx, existing_ids)

        results = await asyncio.gather(*[extract_one(idx) for idx in range(1, vehicle_count + 1)])
        vehicles = [v for v in results if v]

        if vehicles:
            result = upsert_auctions(vehicles)
            all_ids.extend(v["item_id"] for v in vehicles)
            existing_ids.update(v["item_id"] for v in vehicles)
            pct = len(all_ids) / total * 100 if total else 0
            print(f"  [taa] Page {page_num}: {len(vehicles)} → DB (new:{result['new']}) | {len(all_ids)}/{total} ({pct:.1f}%)")
        else:
            # Count skipped
            skipped = vehicle_count - len(vehicles)
            if skipped > 0:
                print(f"  [taa] Page {page_num}: {skipped} skipped (existing)")

        if len(all_ids) >= total:
            break

        # Click next page
        has_next = await page.evaluate("""() => {
            const links = document.querySelectorAll('a');
            for (const a of links) {
                if (a.textContent.trim() === 'next' || a.textContent.trim() === '次へ') {
                    a.click();
                    return true;
                }
            }
            return false;
        }""")

        if not has_next:
            print("  [taa] No next page")
            break

        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(2)

    print(f"  [taa] Done: {len(all_ids)} vehicles across {page_num} pages")
    return all_ids


async def _extract_vehicle_detail(context: BrowserContext, list_page: Page, idx: int, existing_ids: set) -> dict | None:
    """Open vehicle detail popup, extract data, upload images, close popup."""
    popup = None
    try:
        async with context.expect_page(timeout=10000) as popup_info:
            await list_page.evaluate(f"() => popDetail({idx})")

        popup = await popup_info.value
        await popup.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(1)

        # Extract data + image URLs from the popup
        data = await popup.evaluate("""() => {
            const allText = document.body.innerText;

            const modelMatch = allText.match(/Next \\( (.+?) \\)/);
            const title = modelMatch ? modelMatch[1] : '';

            const carImageUrls = [];
            const sheetUrls = [];
            const seenSections = new Set();

            document.querySelectorAll('img').forEach(img => {
                const src = img.src || '';
                if (!src || !src.includes('/data/img/')) return;

                const match = src.match(/(\\/data\\/img\\/[^/]+\\/[^/]+)\\/([A-J])\\/([A-J][^_]+)_\\d\\.jpg/);
                if (!match) return;

                const basePath = match[1];
                const section = match[2];
                const fileBase = match[3];

                if (seenSections.has(section)) return;
                seenSections.add(section);

                if (section === 'A') {
                    sheetUrls.push('https://taacaa.jp/app/common/carImageFile.do?path=' + basePath + '/A/' + fileBase + '_5.jpg');
                } else if (section === 'B' || section === 'C') {
                    carImageUrls.push('https://taacaa.jp' + basePath + '/' + section + '/' + fileBase + '_4.jpg');
                } else {
                    carImageUrls.push('https://taacaa.jp' + basePath + '/' + section + '/' + fileBase + '_1.jpg');
                }
            });

            const refMatch = allText.match(/([A-Z])\\n\\s*(\\d{5})/);
            const dateMatch = allText.match(/(\\d+\\/\\d+)[（(](\\w+)[)）]\\n\\s*(\\w+)/);

            return {
                title,
                car_image_urls: carImageUrls,
                sheet_urls: sheetUrls,
                raw_text: allText.substring(0, 1500),
                ref_match: refMatch ? { lane: refMatch[1], ref_no: refMatch[2] } : null,
                date_match: dateMatch ? { date: dateMatch[1], day: dateMatch[2], hall: dateMatch[3] } : null,
            };
        }""")

        if not data:
            await popup.close()
            return None

        # Build item_id early to check if we can skip
        raw = data.get("raw_text", "")
        vehicle = _parse_taa_detail(raw, data)
        item_id = vehicle["item_id"]

        if item_id in existing_ids:
            await popup.close()
            return None  # Skip — already in DB

        # Upload images in parallel
        async def download_and_upload(url: str) -> str | None:
            try:
                result = await popup.evaluate("""async (url) => {
                    try {
                        const res = await fetch(url, { credentials: 'include' });
                        if (!res.ok) return null;
                        const blob = await res.blob();
                        const reader = new FileReader();
                        return new Promise((resolve) => {
                            reader.onloadend = () => resolve(reader.result);
                            reader.readAsDataURL(blob);
                        });
                    } catch { return null; }
                }""", url)

                if result and result.startswith("data:"):
                    b64 = result.split(",", 1)[1]
                    img_bytes = base64.b64decode(b64)
                    if len(img_bytes) > 500:
                        return upload_image(img_bytes, "taa-images", url)
                return None
            except:
                return None

        # Parallel image uploads
        car_urls = data.get("car_image_urls", [])[:10]
        car_tasks = [download_and_upload(url) for url in car_urls]
        car_results = await asyncio.gather(*car_tasks) if car_tasks else []
        car_images = [r for r in car_results if r]

        exhibit_sheet = None
        for url in data.get("sheet_urls", []):
            path = await download_and_upload(url)
            if path:
                exhibit_sheet = path
                break

        await popup.close()

        vehicle["images"] = car_images
        vehicle["image_url"] = car_images[0] if car_images else None
        vehicle["exhibit_sheet"] = exhibit_sheet
        return vehicle

    except Exception as e:
        # Close any lingering popups
        if popup:
            try:
                await popup.close()
            except:
                pass
        else:
            for pg in context.pages:
                if "carDetail" in pg.url:
                    try:
                        await pg.close()
                    except:
                        pass
        return None


def _parse_taa_detail(raw: str, data: dict) -> dict:
    """Parse TAA detail popup text (English version) into structured vehicle data."""

    lines = [l.strip() for l in raw.split("\n") if l.strip()]

    title = data.get("title", "")
    parts = title.split() if title else []
    maker = parts[0] if len(parts) > 0 else ""
    model = " ".join(parts[1:]) if len(parts) > 1 else title

    def find_after(keyword):
        for i, line in enumerate(lines):
            if keyword.lower() in line.lower() and i + 1 < len(lines):
                return lines[i + 1]
        return None

    date_str = ""
    hall = ""
    ref_no = ""

    if data.get("date_match"):
        dm = data["date_match"]
        date_str = dm.get("date", "")
        hall = dm.get("hall", "")

    if data.get("ref_match"):
        rm = data["ref_match"]
        ref_no = f"{rm.get('lane', '')}{rm.get('ref_no', '')}"

    year = ""
    model_code = ""
    mileage = ""
    color = ""
    rating = ""
    start_price = ""
    inspection = ""

    for i, line in enumerate(lines):
        if re.match(r'^\d{2}/\d{1,2}$', line) and not year:
            year = line
        if re.match(r'^[A-Z]{2,4}\d{2,4}', line) and len(line) < 15 and not model_code:
            model_code = line
        if re.match(r'^\d{1,3}$', line) and 1 < int(line) < 500 and not mileage:
            mileage = f"{int(line) * 1000}km"

    color_match = re.search(r'(?:Color|Colour|Body color)[:\s]*([^\n]+)', raw, re.IGNORECASE)
    if color_match:
        color = color_match.group(1).strip()
    else:
        for line in lines:
            if re.match(r'^(White|Black|Silver|Red|Blue|Green|Pearl|Gold|Gray|Grey|Beige|Brown)', line, re.IGNORECASE):
                color = line
                break

    score_match = re.search(r'(?:Score|Rating|Evaluation)[:\s]*([^\n]+)', raw, re.IGNORECASE)
    if score_match:
        rating = score_match.group(1).strip()
    else:
        rating_match = re.search(r'\b([RS\d]\.?\d?)\s*/\s*([A-Z])\b', raw)
        if rating_match:
            rating = f"{rating_match.group(1)}/{rating_match.group(2)}"

    price_match = re.search(r'(?:Start\s*Price|Starting)[:\s]*([\d,]+)', raw, re.IGNORECASE)
    if price_match:
        start_price = price_match.group(1).replace(",", "")

    insp_match = re.search(r'(?:Inspection|Shaken)[:\s]*(\d{1,2}/\d{1,2})', raw, re.IGNORECASE)
    if insp_match:
        inspection = insp_match.group(1)

    item_id = f"taa-{hall}-{ref_no}-{date_str}".replace("/", "")

    return {
        "item_id": item_id,
        "lot_number": ref_no,
        "maker": maker,
        "model": model,
        "grade": None,
        "chassis_code": model_code,
        "engine_specs": None,
        "year": year,
        "mileage": mileage,
        "inspection_expiry": inspection,
        "color": color,
        "rating": rating,
        "start_price": start_price if start_price else None,
        "auction_date": date_str,
        "auction_house": f"TAA {hall}" if hall else "TAA",
        "location": hall,
        "status": "upcoming",
        "image_url": None,
        "images": [],
        "exhibit_sheet": None,
        "source": "taa",
    }
