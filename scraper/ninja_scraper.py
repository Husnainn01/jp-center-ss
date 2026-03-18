"""USS/NINJA scraper: maker-by-maker, JS navigation (no page.goto).
Optimized: skip existing vehicles, parallel image uploads.
Limits: 500 vehicles & 30 min per maker, smallest makers first."""

import asyncio
import base64
import re
import time
from datetime import date as date_type
from playwright.async_api import Page, BrowserContext
from db import upsert_auctions, get_existing_item_ids, normalize_auction_date
from storage import upload_image
from jst import should_scrape_today, get_target_date, now_jst, today_jst

ALL_MAKERS = [
    "TOYOTA", "LEXUS", "NISSAN", "HONDA", "MAZDA", "MITSUBISHI",
    "SUBARU", "DAIHATSU", "SUZUKI", "ISUZU", "HINO",
    "MERCEDES BENZ", "BMW", "AUDI", "VOLKSWAGEN", "PORSCHE",
]

BRAND_CODES = {
    "LEXUS": "00", "TOYOTA": "01", "NISSAN": "04", "HONDA": "06",
    "MAZDA": "10", "MITSUBISHI": "08", "SUBARU": "14", "DAIHATSU": "15",
    "SUZUKI": "16", "ISUZU": "17", "MERCEDES BENZ": "40", "BMW": "44",
    "AUDI": "46", "VOLKSWAGEN": "47", "PORSCHE": "49",
}

# Limits per maker to ensure all makers get scraped each cycle
MAX_PAGES_PER_MAKER = 20
MAX_VEHICLES_PER_MAKER = 500
MAX_TIME_PER_MAKER = 1800  # 30 minutes in seconds


async def _select_maker(page: Page, brand_code: str):
    """Navigate to searchcondition (if needed) then select maker via seniBrand."""
    # If not on searchcondition, go back first (seniToSearchcondition is available on all NINJA pages)
    if "searchcondition" not in page.url:
        try:
            await page.evaluate("() => seniToSearchcondition()")
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(3)
        except:
            # Fallback: browser back
            await page.go_back()
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(3)

    await page.evaluate(f"() => seniBrand('{brand_code}')")
    await page.wait_for_load_state("networkidle", timeout=30000)
    await asyncio.sleep(3)


async def _get_maker_vehicle_count(page: Page, brand_code: str) -> int:
    """Quick check: select maker and return total vehicle count."""
    await _select_maker(page, brand_code)
    total = await page.evaluate("""() => {
        let total = 0;
        document.querySelectorAll('a').forEach(a => {
            const onclick = a.getAttribute('onclick') || '';
            if (onclick.match(/makerListChoiceCarCat/)) {
                const m = a.textContent.trim().match(/\\((\\d+)\\)/);
                if (m) total += parseInt(m[1]);
            }
        });
        return total;
    }""")
    return total


async def ninja_search_and_extract(context: BrowserContext, makers: list[str] | None = None) -> list[str]:
    page = context.pages[0] if context.pages else await context.new_page()
    all_ids = []

    makers = makers or ALL_MAKERS

    target_date = get_target_date()
    scrape_today = should_scrape_today()
    jst_now = now_jst()
    print(f"  [ninja] JST time: {jst_now.strftime('%Y-%m-%d %H:%M')}")
    print(f"  [ninja] Target date: {target_date} ({'today + future' if scrape_today else 'tomorrow + future only'})")
    print(f"  [ninja] Current URL: {page.url[:60]}...")
    print(f"  [ninja] Makers to scrape: {', '.join(makers)}")
    print(f"  [ninja] Limits: {MAX_VEHICLES_PER_MAKER} vehicles, {MAX_TIME_PER_MAKER//60} min per maker")

    existing_ids = get_existing_item_ids("uss")
    print(f"  [ninja] {len(existing_ids)} existing vehicles in DB (will skip)")

    # Pre-scan: get vehicle counts for all makers and sort smallest first
    print(f"  [ninja] Pre-scanning maker sizes...")
    maker_counts = []
    for maker in makers:
        brand_code = BRAND_CODES.get(maker)
        if not brand_code:
            continue
        try:
            count = await _get_maker_vehicle_count(page, brand_code)
            maker_counts.append((maker, count))
            print(f"  [ninja]   {maker}: {count} vehicles")
        except Exception as e:
            maker_counts.append((maker, 0))
            print(f"  [ninja]   {maker}: failed to count ({e})")

    # Sort smallest first so small makers finish quickly
    maker_counts.sort(key=lambda x: x[1])
    sorted_makers = [m for m, _ in maker_counts]
    print(f"  [ninja] Scrape order (smallest first): {', '.join(sorted_makers)}")

    for maker in sorted_makers:
        print(f"  [ninja] Scraping {maker}...")
        try:
            ids = await _scrape_maker(page, context, maker, existing_ids)
            all_ids.extend(ids)
            print(f"  [ninja] {maker}: {len(ids)} vehicles total")
        except Exception as e:
            print(f"  [ninja] {maker} failed: {e}")

    print(f"  [ninja] Total: {len(all_ids)} vehicles")
    return all_ids


async def _scrape_maker(page: Page, context: BrowserContext, maker: str, existing_ids: set) -> list[str]:
    """Scrape vehicles for a maker. Uses JS navigation to preserve session.
    Enforces MAX_VEHICLES_PER_MAKER and MAX_TIME_PER_MAKER limits."""

    maker_start = time.time()

    brand_code = BRAND_CODES.get(maker)
    if not brand_code:
        print(f"  [ninja] {maker}: no brand code, skipping")
        return []

    await _select_maker(page, brand_code)

    # Now on makersearch.action — get models via makerListChoiceCarCat links
    models = await page.evaluate("""() => {
        const models = [];
        document.querySelectorAll('a').forEach(a => {
            const onclick = a.getAttribute('onclick') || '';
            const match = onclick.match(/makerListChoiceCarCat\\('(\\d+)'\\)/);
            if (match) {
                const text = a.textContent.trim();
                const countMatch = text.match(/(.+?)\\s*\\((\\d+)\\)/);
                if (countMatch && parseInt(countMatch[2]) > 0) {
                    models.push({ name: countMatch[1], count: parseInt(countMatch[2]), catId: match[1] });
                }
            }
        });
        return models;
    }""")

    total_available = sum(m["count"] for m in models)
    print(f"  [ninja] {maker}: {len(models)} models, {total_available} vehicles")

    if total_available == 0:
        snippet = (await page.inner_text("body"))[:200]
        print(f"  [ninja] {maker}: 0 vehicles, page snippet: {snippet}")
        return []

    # Select all body types
    await page.evaluate("""() => {
        document.querySelectorAll('input[name="bodytype"]').forEach(cb => {
            if (!cb.checked) cb.click();
        });
    }""")
    await asyncio.sleep(0.5)

    # If < 1000, try allSearch (fast path)
    if total_available < 1000:
        try:
            await page.evaluate("() => allSearch()")
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(5)

            body = await page.inner_text("body")
            if "more than 1,000" not in body.lower() and "1,000items" not in body.lower():
                return await _paginate_results(page, context, maker, existing_ids, maker_start)
        except Exception as e:
            print(f"  [ninja] {maker} allSearch failed: {e}")

    # >1000: search model by model, but limit to top models by count
    models.sort(key=lambda m: m["count"], reverse=True)
    top_models = models[:30]
    print(f"  [ninja] {maker}: searching top {len(top_models)} models (of {len(models)})...")

    all_ids = []
    for model in top_models:
        if model["count"] == 0:
            continue

        # Check limits before starting next model
        elapsed = time.time() - maker_start
        if elapsed >= MAX_TIME_PER_MAKER:
            print(f"  [ninja] {maker}: time limit reached ({elapsed/60:.1f} min), moving on")
            break
        if len(all_ids) >= MAX_VEHICLES_PER_MAKER:
            print(f"  [ninja] {maker}: vehicle limit reached ({len(all_ids)}/{MAX_VEHICLES_PER_MAKER}), moving on")
            break

        try:
            ids = await _scrape_single_model(page, context, maker, model, existing_ids, maker_start)
            all_ids.extend(ids)
            if ids:
                print(f"  [ninja] {maker} > {model['name']}: {len(ids)} vehicles")
        except Exception as e:
            print(f"  [ninja] {maker} > {model['name']} failed: {e}")

    elapsed = time.time() - maker_start
    print(f"  [ninja] {maker}: done in {elapsed/60:.1f} min")
    return all_ids


async def _scrape_single_model(page: Page, context: BrowserContext, maker: str, model: dict, existing_ids: set, maker_start: float) -> list[str]:
    """Search for a single maker+model. Uses JS navigation."""
    brand_code = BRAND_CODES.get(maker)
    if not brand_code:
        return []

    # Re-select maker to get back to model list
    await _select_maker(page, brand_code)

    # Select all body types
    await page.evaluate("""() => {
        document.querySelectorAll('input[name="bodytype"]').forEach(cb => {
            if (!cb.checked) cb.click();
        });
    }""")
    await asyncio.sleep(0.5)

    # Click model
    cat_id = model["catId"]
    await page.evaluate(f"() => makerListChoiceCarCat('{cat_id}')")
    await page.wait_for_load_state("networkidle", timeout=30000)
    await asyncio.sleep(5)

    body = await page.inner_text("body")
    if "more than 1,000" in body.lower() or "1,000items" in body.lower():
        print(f"  [ninja] {maker} > {model['name']}: >1000, skipping")
        return []

    return await _paginate_results(page, context, maker, existing_ids, maker_start)


async def _paginate_results(page: Page, context: BrowserContext, maker: str, existing_ids: set, maker_start: float) -> list[str]:
    """Paginate through results. Enforces page, vehicle, and time limits."""
    all_ids = []
    page_num = 0

    while page_num < MAX_PAGES_PER_MAKER:
        # Check time and vehicle limits
        if time.time() - maker_start >= MAX_TIME_PER_MAKER:
            print(f"  [ninja] {maker}: time limit reached, stopping pagination")
            break
        if len(all_ids) >= MAX_VEHICLES_PER_MAKER:
            print(f"  [ninja] {maker}: vehicle limit reached ({len(all_ids)}/{MAX_VEHICLES_PER_MAKER}), stopping pagination")
            break

        page_num += 1

        vehicle_params = await page.evaluate("""() => {
            const params = [];
            const els = document.querySelectorAll('[onclick*=seniCarDetail]');
            const seen = new Set();
            for (const el of els) {
                const onclick = el.getAttribute('onclick') || '';
                const match = onclick.match(/seniCarDetail\\('(\\d+)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)'/);
                if (match) {
                    const key = match[4];
                    if (!seen.has(key)) {
                        seen.add(key);
                        params.push({ index: match[1], site: match[2], times: match[3], bidNo: match[4], extra: match[5] });
                    }
                }
            }
            return params;
        }""")

        if not vehicle_params:
            break

        # Skip existing
        new_params = []
        skipped = 0
        for vp in vehicle_params:
            item_id = f"uss-{vp['bidNo']}-{vp['times']}"
            if item_id in existing_ids:
                skipped += 1
                all_ids.append(item_id)
            else:
                new_params.append(vp)

        print(f"  [ninja] {maker} p{page_num}: {len(vehicle_params)} vehicles ({skipped} existing, {len(new_params)} new)")

        # Extract new vehicles (filter by target date)
        target = get_target_date()
        vehicles = []
        skipped_date = 0
        for vp in new_params:
            try:
                v = await _extract_vehicle_detail(page, context, vp, maker)
                if v and v.get("item_id"):
                    # Filter: skip vehicles with auction dates before target date
                    auction_date_str = v.get("auction_date", "")
                    auction_date = normalize_auction_date(auction_date_str, "uss")
                    if auction_date and auction_date < target:
                        skipped_date += 1
                        continue
                    vehicles.append(v)
            except Exception as e:
                print(f"  [ninja] Detail failed: {e}")

        if skipped_date:
            print(f"  [ninja] {maker} p{page_num}: skipped {skipped_date} vehicles with past auction dates")

        if vehicles:
            result = upsert_auctions(vehicles)
            all_ids.extend(v["item_id"] for v in vehicles)
            existing_ids.update(v["item_id"] for v in vehicles)
            img_total = sum(len(v.get("images", [])) for v in vehicles)
            print(f"  [ninja] {maker} p{page_num}: {len(vehicles)} → DB (new:{result['new']}, imgs:{img_total})")

        # Next page
        has_next = await page.evaluate("""() => {
            for (const a of document.querySelectorAll('a'))
                if (a.textContent.trim().includes('Next page')) { a.click(); return true; }
            return false;
        }""")
        if not has_next:
            break
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(5)

    if page_num >= MAX_PAGES_PER_MAKER:
        print(f"  [ninja] {maker}: reached page limit ({MAX_PAGES_PER_MAKER}), moving to next maker")

    return all_ids


async def _extract_vehicle_detail(page: Page, context: BrowserContext, params: dict, maker: str) -> dict | None:
    """Open vehicle detail on main page, extract data + images."""
    try:
        idx, site, times, bid_no = params["index"], params["site"], params["times"], params["bidNo"]

        await page.evaluate(f"() => seniCarDetail('{idx}', '{site}', '{times}', '{bid_no}', '')")
        await page.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(2)

        text = await page.inner_text("body")

        imgs_data = await page.evaluate("""() => {
            const car = [];
            const sheet = [];
            const seen = new Set();
            document.querySelectorAll('img').forEach(img => {
                if (!img.src || !img.src.startsWith('http') || seen.has(img.src)) return;
                seen.add(img.src);
                if (img.src.includes('get_ex_image')) sheet.push(img.src);
                else if (img.src.includes('get_image') || img.src.includes('get_car_image')) car.push(img.src);
            });
            return { car, sheet };
        }""")

        # Parallel upload
        async def upload_one(url):
            return await _download_and_upload(page, url, "ninja-images")

        car_tasks = [upload_one(url) for url in imgs_data.get("car", [])]
        car_results = await asyncio.gather(*car_tasks) if car_tasks else []
        car_images = [r for r in car_results if r]

        exhibit_sheet = None
        for url in imgs_data.get("sheet", []):
            path = await _download_and_upload(page, url, "ninja-images")
            if path:
                exhibit_sheet = path
                break

        vehicle = _parse_detail_text(text, maker, site, bid_no, times)
        vehicle["images"] = car_images
        vehicle["image_url"] = car_images[0] if car_images else None
        vehicle["exhibit_sheet"] = exhibit_sheet

        # Go back
        await page.evaluate("""() => {
            const links = document.querySelectorAll('a');
            for (const a of links) {
                if (a.textContent.trim() === 'Back to the list') { a.click(); return; }
            }
            history.back();
        }""")
        await page.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(2)

        return vehicle

    except Exception as e:
        try:
            await page.go_back()
            await page.wait_for_load_state("networkidle", timeout=10000)
            await asyncio.sleep(2)
        except:
            pass
        return None


def _parse_detail_text(text: str, maker: str, site: str, bid_no: str, times: str) -> dict:
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    model = ""
    grade = ""
    for line in lines:
        if maker in line and len(line) < 100:
            parts = line.replace(maker, "").strip().split()
            model = parts[0] if parts else ""
            grade = " ".join(parts[1:]) if len(parts) > 1 else ""
            break

    def find_field(label):
        for i, line in enumerate(lines):
            if line.startswith(label) or line == label:
                rest = line.replace(label, "").strip()
                if rest: return rest
                if i + 1 < len(lines): return lines[i + 1]
        return None

    year_match = re.search(r'\b(20\d{2})\b', text[:500])
    date_match = re.search(r'(\d{4}/\d{2}/\d{2})', text)
    price_match = re.search(r'(?:Start|JPY)\s*([\d,]+)', text)
    mileage_match = re.search(r'(\d[\d,]*)\s*km', text, re.IGNORECASE)
    cc_match = re.search(r'([\d,]+)\s*cc', text, re.IGNORECASE)
    score_match = re.search(r'Inspection score\s*([^\n]+)', text)

    chassis = find_field("Type") or ""
    color = find_field("Body color") or ""

    price_raw = price_match.group(1).replace(",", "") if price_match else None
    start_price = str(int(price_raw) / 10000) if price_raw else None

    item_id = f"uss-{bid_no}-{date_match.group(1).replace('/', '') if date_match else times}"

    return {
        "item_id": item_id,
        "lot_number": bid_no,
        "maker": maker,
        "model": model,
        "grade": grade or None,
        "chassis_code": chassis.strip() if chassis else None,
        "engine_specs": cc_match.group(0) if cc_match else None,
        "year": year_match.group(1) if year_match else None,
        "mileage": mileage_match.group(0) if mileage_match else None,
        "inspection_expiry": None,
        "color": color.strip() if color else None,
        "rating": score_match.group(1).strip() if score_match else None,
        "start_price": start_price,
        "auction_date": date_match.group(1) if date_match else "",
        "auction_house": f"USS {site}".strip(),
        "location": site or "USS",
        "status": "upcoming",
        "image_url": None,
        "images": [],
        "exhibit_sheet": None,
        "source": "uss",
    }


async def _download_and_upload(page: Page, url: str, prefix: str) -> str | None:
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
