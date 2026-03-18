"""USS/NINJA scraper: maker-by-maker, model-by-model for large makers.
Optimized: parallel detail extraction (3 concurrent tabs), skip existing vehicles.
Chunk-based: saves each page of results to DB immediately."""

import asyncio
import os
import hashlib
import base64
import re
from playwright.async_api import Page, BrowserContext
from db import upsert_auctions, get_existing_item_ids
from storage import upload_image

MAKERS = [
    "TOYOTA", "LEXUS", "NISSAN", "HONDA", "MAZDA", "MITSUBISHI",
    "SUBARU", "DAIHATSU", "SUZUKI", "MERCEDES BENZ", "BMW", "AUDI",
    "VOLKSWAGEN", "PORSCHE",
]


async def ninja_search_and_extract(context: BrowserContext) -> list[str]:
    page = context.pages[0] if context.pages else await context.new_page()
    all_ids = []

    # Load existing vehicle IDs to skip re-scraping
    existing_ids = get_existing_item_ids("uss")
    print(f"  [ninja] {len(existing_ids)} existing vehicles in DB (will skip detail extraction)")

    for maker in MAKERS:
        print(f"  [ninja] Scraping {maker}...")
        try:
            ids = await _scrape_maker(page, context, maker, existing_ids)
            all_ids.extend(ids)
            print(f"  [ninja] {maker}: {len(ids)} vehicles total")
        except Exception as e:
            print(f"  [ninja] {maker} failed: {e}")
            try:
                await page.evaluate("() => seniToSearchcondition()")
                await page.wait_for_load_state("networkidle", timeout=15000)
                await asyncio.sleep(3)
            except:
                pass

    print(f"  [ninja] Total: {len(all_ids)} vehicles")
    return all_ids


async def _scrape_maker(page: Page, context: BrowserContext, maker: str, existing_ids: set) -> list[str]:
    """Scrape all vehicles for a maker. If >1000, break down by model."""

    await page.evaluate("() => seniToSearchcondition()")
    await page.wait_for_load_state("networkidle", timeout=15000)
    await asyncio.sleep(2)

    await page.evaluate(f"""() => {{
        for (const a of document.querySelectorAll('a'))
            if (a.textContent.trim() === '・{maker}') {{ a.click(); return; }}
    }}""")
    await page.wait_for_load_state("networkidle", timeout=15000)
    await asyncio.sleep(2)

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
    print(f"  [ninja] {maker}: {len(models)} models, {total_available} vehicles available")

    if total_available == 0:
        return []

    await page.evaluate("""() => {
        document.querySelectorAll('input[name="bodytype"]').forEach(cb => {
            if (!cb.checked) cb.click();
        });
    }""")
    await asyncio.sleep(0.5)

    if total_available < 1000:
        try:
            await page.evaluate("() => allSearch()")
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(5)

            body = await page.inner_text("body")
            if "more than 1,000" not in body.lower() and "1,000items" not in body.lower():
                return await _paginate_results(page, context, maker, existing_ids)
        except Exception as e:
            print(f"  [ninja] {maker} allSearch failed: {e}")

    print(f"  [ninja] {maker}: searching model by model...")
    all_ids = []

    for model in models:
        if model["count"] == 0:
            continue

        try:
            ids = await _scrape_single_model(page, context, maker, model, existing_ids)
            all_ids.extend(ids)
            if ids:
                print(f"  [ninja] {maker} > {model['name']}: {len(ids)} vehicles")
        except Exception as e:
            print(f"  [ninja] {maker} > {model['name']} failed: {e}")
            try:
                await page.evaluate("() => seniToSearchcondition()")
                await page.wait_for_load_state("networkidle", timeout=15000)
                await asyncio.sleep(3)
            except:
                pass

    return all_ids


async def _scrape_single_model(page: Page, context: BrowserContext, maker: str, model: dict, existing_ids: set) -> list[str]:
    """Search for a single maker+model combination."""
    await page.evaluate("() => seniToSearchcondition()")
    await page.wait_for_load_state("networkidle", timeout=15000)
    await asyncio.sleep(2)

    await page.evaluate(f"""() => {{
        for (const a of document.querySelectorAll('a'))
            if (a.textContent.trim() === '・{maker}') {{ a.click(); return; }}
    }}""")
    await page.wait_for_load_state("networkidle", timeout=15000)
    await asyncio.sleep(2)

    await page.evaluate("""() => {
        document.querySelectorAll('input[name="bodytype"]').forEach(cb => {
            if (!cb.checked) cb.click();
        });
    }""")
    await asyncio.sleep(0.5)

    cat_id = model["catId"]
    await page.evaluate(f"() => makerListChoiceCarCat('{cat_id}')")
    await page.wait_for_load_state("networkidle", timeout=30000)
    await asyncio.sleep(5)

    body = await page.inner_text("body")
    if "more than 1,000" in body.lower() or "1,000items" in body.lower():
        print(f"  [ninja] {maker} > {model['name']}: still >1000, skipping")
        return []

    return await _paginate_results(page, context, maker, existing_ids)


async def _paginate_results(page: Page, context: BrowserContext, maker: str, existing_ids: set) -> list[str]:
    """Paginate through search results. Skip existing vehicles, parallel image uploads."""
    all_ids = []
    page_num = 0

    while True:
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

        # Pre-generate item_ids to check which ones we can skip
        new_params = []
        skipped = 0
        for vp in vehicle_params:
            date_guess = vp["times"]
            item_id = f"uss-{vp['bidNo']}-{date_guess}"
            if item_id in existing_ids:
                skipped += 1
                all_ids.append(item_id)
            else:
                new_params.append(vp)

        total_on_page = len(vehicle_params)
        print(f"  [ninja] {maker} p{page_num}: {total_on_page} vehicles ({skipped} existing, {len(new_params)} new)")

        # Extract new vehicles sequentially on the main page
        vehicles = []
        for vp in new_params:
            try:
                v = await _extract_vehicle_detail(page, context, vp, maker)
                if v and v.get("item_id"):
                    vehicles.append(v)
            except Exception as e:
                print(f"  [ninja] Detail failed: {e}")
                continue

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

    return all_ids


async def _extract_vehicle_detail(page: Page, context: BrowserContext, params: dict, maker: str) -> dict | None:
    """Open vehicle detail on the main page, extract data + images, go back."""
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

                if (img.src.includes('get_ex_image')) {
                    sheet.push(img.src);
                } else if (img.src.includes('get_image') || img.src.includes('get_car_image')) {
                    car.push(img.src);
                }
            });
            return { car, sheet };
        }""")

        # Upload images in parallel
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

        # Go back to list
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
    """Parse vehicle detail page text."""
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
                if rest:
                    return rest
                if i + 1 < len(lines):
                    return lines[i + 1]
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
    """Download image via browser fetch and upload to S3."""
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
                s3_url = upload_image(img_bytes, prefix, url)
                if s3_url:
                    return s3_url
        return None
    except:
        return None
