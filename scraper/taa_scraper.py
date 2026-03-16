"""TAA scraper: search → paginate → open each detail popup → extract data + download images.
Chunk-based: saves each page of results to DB immediately.
Images are downloaded locally since TAA requires auth cookies."""

import asyncio
import os
import hashlib
import base64
from playwright.async_api import Page, BrowserContext
from db import upsert_auctions
from storage import upload_image

# Days to scrape — checkHallYobi checkboxes
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat"]


async def taa_search_and_extract(context: BrowserContext) -> list[str]:
    """Full TAA scrape flow. Returns list of scraped item_ids."""
    page = context.pages[0] if context.pages else await context.new_page()

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
    print(f"  [taa] Checked {checked_models} models for {DAYS}")

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

    while True:
        page_num += 1
        print(f"  [taa] Page {page_num} — extracting list...")

        # Get vehicle refs from this page (popDetail indices)
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

        # Extract each vehicle's detail by opening popup
        vehicles = []
        for idx in range(1, vehicle_count + 1):
            v = await _extract_vehicle_detail(context, page, idx)
            if v:
                vehicles.append(v)

        if vehicles:
            result = upsert_auctions(vehicles)
            all_ids.extend(v["item_id"] for v in vehicles)
            pct = len(all_ids) / total * 100 if total else 0
            print(f"  [taa] Page {page_num}: {len(vehicles)} vehicles → DB (new:{result['new']}) | {len(all_ids)}/{total} ({pct:.1f}%)")

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
        await asyncio.sleep(3)

    print(f"  [taa] Done: {len(all_ids)} vehicles across {page_num} pages")
    return all_ids


async def _extract_vehicle_detail(context: BrowserContext, list_page: Page, idx: int) -> dict | None:
    """Open vehicle detail popup, extract data, download images locally, close popup."""
    try:
        async with context.expect_page(timeout=10000) as popup_info:
            await list_page.evaluate(f"() => popDetail({idx})")

        popup = await popup_info.value
        await popup.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(2)

        # Extract data + image URLs from the popup
        data = await popup.evaluate("""() => {
            const allText = document.body.innerText;

            // Title from "Next ( MODEL ) >>"
            const modelMatch = allText.match(/Next \\( (.+?) \\)/);
            const title = modelMatch ? modelMatch[1] : '';

            // ALL images — smart quality selection per section
            // B,C = _4 exists (10KB, decent), D-J = only _1 (4KB, small)
            // A = auction sheet, use carImageFile.do?path= with _5 (36KB, clear)
            const carImageUrls = [];
            const sheetUrls = [];
            const seenSections = new Set();

            document.querySelectorAll('img').forEach(img => {
                const src = img.src || '';
                if (!src || !src.includes('/data/img/')) return;

                // Parse: /data/img/{date}/{hall}/{section}/{section}{ref}_{size}.jpg
                const match = src.match(/(\\/data\\/img\\/[^/]+\\/[^/]+)\\/([A-J])\\/([A-J][^_]+)_\\d\\.jpg/);
                if (!match) return;

                const basePath = match[1];
                const section = match[2];
                const fileBase = match[3];

                if (seenSections.has(section)) return;
                seenSections.add(section);

                if (section === 'A') {
                    // Auction sheet — use carImageFile.do wrapper with _5 for best quality
                    sheetUrls.push('https://taacaa.jp/app/common/carImageFile.do?path=' + basePath + '/A/' + fileBase + '_5.jpg');
                } else if (section === 'B' || section === 'C') {
                    // Front/rear — _4 exists and is 10KB (decent)
                    carImageUrls.push('https://taacaa.jp' + basePath + '/' + section + '/' + fileBase + '_4.jpg');
                } else {
                    // D-J sections — only _1 exists (4KB thumbnail)
                    carImageUrls.push('https://taacaa.jp' + basePath + '/' + section + '/' + fileBase + '_1.jpg');
                }
            });

            // Ref and date
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

        # Download images through the authenticated browser session
        async def download_image(page: Page, url: str) -> str | None:
            """Download image via browser fetch, upload to S3."""
            try:
                result = await page.evaluate("""async (url) => {
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
                        s3_url = upload_image(img_bytes, "taa-images", url)
                        if s3_url:
                            return s3_url
                return None
            except:
                return None

        # Download car images
        car_images = []
        for url in data.get("car_image_urls", []):
            local = await download_image(popup, url)
            if local and local not in car_images:
                car_images.append(local)
            if len(car_images) >= 10:
                break  # Cap at 10 images per vehicle

        # Download auction sheet
        exhibit_sheet = None
        for url in data.get("sheet_urls", []):
            local = await download_image(popup, url)
            if local:
                exhibit_sheet = local
                break

        await popup.close()

        # Parse text fields
        raw = data.get("raw_text", "")
        vehicle = _parse_taa_detail(raw, data)
        vehicle["images"] = car_images
        vehicle["image_url"] = car_images[0] if car_images else None
        vehicle["exhibit_sheet"] = exhibit_sheet
        return vehicle

    except Exception as e:
        for pg in context.pages:
            if "carDetail" in pg.url:
                await pg.close()
        return None


def _parse_taa_detail(raw: str, data: dict) -> dict:
    """Parse TAA detail popup text (English version) into structured vehicle data."""
    import re

    lines = [l.strip() for l in raw.split("\n") if l.strip()]

    # Extract title (model name) from "Next ( MODEL ) >>"
    title = data.get("title", "")
    parts = title.split() if title else []
    maker = parts[0] if len(parts) > 0 else ""
    model = " ".join(parts[1:]) if len(parts) > 1 else title

    # Find field value after a keyword label
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

    # Extract fields from English text
    year = ""
    model_code = ""
    mileage = ""
    color = ""
    rating = ""
    start_price = ""
    inspection = ""

    for i, line in enumerate(lines):
        # Year: 29/9 or R7/5
        if re.match(r'^\d{2}/\d{1,2}$', line) and not year:
            year = line
        # Model code: like GRS182, NZE161 etc.
        if re.match(r'^[A-Z]{2,4}\d{2,4}', line) and len(line) < 15 and not model_code:
            model_code = line
        # Mileage: number followed by km or just a small number
        if re.match(r'^\d{1,3}$', line) and 1 < int(line) < 500 and not mileage:
            mileage = f"{int(line) * 1000}km"

    # Color: look for English color names or color codes
    color_match = re.search(r'(?:Color|Colour|Body color)[:\s]*([^\n]+)', raw, re.IGNORECASE)
    if color_match:
        color = color_match.group(1).strip()
    else:
        # Try color code pattern: "W" or "1F7" near known color words
        for line in lines:
            if re.match(r'^(White|Black|Silver|Red|Blue|Green|Pearl|Gold|Gray|Grey|Beige|Brown)', line, re.IGNORECASE):
                color = line
                break

    # Rating/score
    score_match = re.search(r'(?:Score|Rating|Evaluation)[:\s]*([^\n]+)', raw, re.IGNORECASE)
    if score_match:
        rating = score_match.group(1).strip()
    else:
        # Pattern like "3.5" or "4" or "R" or "A/B"
        rating_match = re.search(r'\b([RS\d]\.?\d?)\s*/\s*([A-Z])\b', raw)
        if rating_match:
            rating = f"{rating_match.group(1)}/{rating_match.group(2)}"

    # Start price
    price_match = re.search(r'(?:Start\s*Price|Starting)[:\s]*([\d,]+)', raw, re.IGNORECASE)
    if price_match:
        start_price = price_match.group(1).replace(",", "")

    # Inspection
    insp_match = re.search(r'(?:Inspection|Shaken)[:\s]*(\d{1,2}/\d{1,2})', raw, re.IGNORECASE)
    if insp_match:
        inspection = insp_match.group(1)

    # Build unique ID
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
