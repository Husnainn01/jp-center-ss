"""iAUC scraper: maker-by-maker, models in batches of 20.
Extracts vehicle details + all images + auction sheet.
Optimized: skip existing vehicles, parallel image uploads."""

import asyncio
import base64
import re
from playwright.async_api import Page, BrowserContext
from db import upsert_auctions, get_existing_item_ids
from storage import upload_image

BATCH_SIZE = 20  # Max models per search

JP_MAKERS = [
    "TOYOTA", "LEXUS", "NISSAN", "HONDA", "MITSUBISHI", "MAZDA",
    "SUZUKI", "DAIHATSU", "SUBARU", "ISUZU", "HINO", "OTHER JAPAN",
]

IMPORTED_MAKERS = [
    "MERCEDES-BENZ", "BMW", "AUDI", "VOLKSWAGEN", "PORSCHE",
    "VOLVO", "JAGUAR", "FORD", "GM", "CHRYSLER", "TESLA",
    "ALFA ROMEO", "FIAT", "FERRARI", "MASERATI", "LAMBORGHINI",
    "CITROEN", "PEUGEOT", "RENAULT", "BYD", "OTHER IMPORTED",
]


async def iauc_search_and_extract(page: Page, context: BrowserContext) -> list[str]:
    """Full iAUC scrape. Returns list of scraped item_ids."""

    existing_ids = get_existing_item_ids("iauc")
    print(f"  [iauc] {len(existing_ids)} existing vehicles in DB (will skip)")

    # Uncheck Kyoyuzaiko
    print("  [iauc] Setting up auction selection...")
    await page.evaluate("""() => {
        document.querySelectorAll('input[name="e[]"]').forEach(cb => { if (cb.checked) cb.click(); });
    }""")
    await asyncio.sleep(1)

    # Uncheck Today's finished auctions, keep upcoming days only
    # The d[] checkboxes that show "Finished" or are in Today's section should be unchecked
    await page.evaluate("""() => {
        document.querySelectorAll('input[name="d[]"]').forEach(cb => {
            const parent = cb.closest('li') || cb.parentElement;
            const text = parent?.textContent?.trim() || '';
            // Uncheck if finished
            if (text.includes('Finished') || text.includes('セリ終了')) {
                if (cb.checked) cb.click();
            }
            // Make sure upcoming ones are checked
            if (text.includes('Listed') || text.includes('入札可') || text.includes('Preparing') || text.includes('仮出品')) {
                if (!cb.checked) cb.click();
            }
        });
    }""")
    await asyncio.sleep(1)

    d_checked = await page.evaluate('() => document.querySelectorAll(\'input[name="d[]"]:checked\').length')
    d_total = await page.evaluate('() => document.querySelectorAll(\'input[name="d[]"]\').length')
    print(f"  [iauc] Auction sites selected: {d_checked}/{d_total} (skipped finished)")
    await asyncio.sleep(1)

    # Click Next to Make & Model page
    await page.evaluate('() => check_sites(document.querySelector(".page-next-button"))')
    await page.wait_for_load_state("networkidle", timeout=30000)
    await asyncio.sleep(5)

    if "#maker" not in page.url and "search" not in page.url:
        print(f"  [iauc] Failed to reach Make & Model page: {page.url}")
        return []

    all_ids = []
    all_makers = JP_MAKERS + IMPORTED_MAKERS

    for maker in all_makers:
        print(f"  [iauc] Scraping {maker}...")
        try:
            ids = await _scrape_maker(page, context, maker, existing_ids)
            all_ids.extend(ids)
            if ids:
                print(f"  [iauc] {maker}: {len(ids)} vehicles")
        except Exception as e:
            print(f"  [iauc] {maker} failed: {e}")

    print(f"  [iauc] Total: {len(all_ids)} vehicles")
    return all_ids


async def _scrape_maker(page: Page, context: BrowserContext, maker: str, existing_ids: set) -> list[str]:
    """Scrape all vehicles for one maker, models in batches of 20."""

    # Navigate back to Make & Model page
    await page.evaluate("""() => {
        document.querySelectorAll('a').forEach(a => {
            if (a.textContent.trim() === 'Select Make & Model') a.click();
        });
    }""")
    await asyncio.sleep(3)

    # Clear previous maker selection
    await page.evaluate("""() => {
        // Click Clear All buttons for both Japanese and Imported
        document.querySelectorAll('button').forEach(b => {
            if (b.textContent.trim() === 'Clear All' && b.offsetParent !== null) b.click();
        });
    }""")
    await asyncio.sleep(2)

    # Find and click the maker
    maker_box = await page.evaluate(f"""() => {{
        for (const li of document.querySelectorAll('li.search-maker-checkbox')) {{
            if (li.textContent.trim() === '{maker}') {{
                const r = li.getBoundingClientRect();
                return {{ x: r.x + r.width/2, y: r.y + r.height/2 }};
            }}
        }}
        return null;
    }}""")

    if not maker_box:
        print(f"  [iauc] {maker} not found on page")
        return []

    await page.mouse.click(maker_box['x'], maker_box['y'])
    await asyncio.sleep(3)

    # Get all models for this maker
    models = await page.evaluate("""() => {
        const items = [];
        document.querySelectorAll('input[name="type[]"]').forEach(inp => {
            const name = inp.getAttribute('data-name') || '';
            const cnt = parseInt(inp.getAttribute('data-cnt') || '0');
            const li = inp.closest('li');
            if (li && cnt > 0) {
                const r = li.getBoundingClientRect();
                items.push({ name, cnt, x: r.x + r.width/2, y: r.y + r.height/2, visible: r.y > 0 });
            }
        });
        return items;
    }""")

    total_cars = sum(m['cnt'] for m in models)
    if total_cars == 0:
        return []

    print(f"  [iauc] {maker}: {len(models)} models, {total_cars} vehicles")

    # Process models in batches of 20
    all_ids = []
    visible_models = [m for m in models if m['visible']]

    for batch_start in range(0, len(visible_models), BATCH_SIZE):
        batch = visible_models[batch_start:batch_start + BATCH_SIZE]
        batch_names = [m['name'] for m in batch]
        batch_total = sum(m['cnt'] for m in batch)

        if batch_total == 0:
            continue

        print(f"  [iauc] {maker} batch {batch_start//BATCH_SIZE + 1}: {len(batch)} models ({batch_total} vehicles)")

        # Clear previous model selection and select this batch
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="type[]"]').forEach(inp => {
                if (inp.checked) {
                    const li = inp.closest('li');
                    if (li) li.click();
                }
            });
        }""")
        await asyncio.sleep(1)

        # Click each model in this batch
        for m in batch:
            if m['y'] > 0:
                await page.mouse.click(m['x'], m['y'])
                await asyncio.sleep(0.2)

        await asyncio.sleep(1)

        # Check if Next is enabled
        next_disabled = await page.evaluate('() => document.querySelector("#next-bottom")?.disabled')
        if next_disabled:
            # Force enable
            await page.evaluate('() => { var b = document.querySelector("#next-bottom"); if (b) b.disabled = false; }')

        # Click Next to search
        await page.evaluate('() => document.querySelector("#next-bottom")?.click()')
        await page.wait_for_load_state("networkidle", timeout=60000)
        await asyncio.sleep(8)

        # Extract vehicles from results
        ids = await _extract_results(page, context, maker, existing_ids)
        all_ids.extend(ids)

        # Go back to Make & Model page for next batch
        await page.evaluate("""() => {
            document.querySelectorAll('a').forEach(a => {
                if (a.textContent.trim() === 'Select Make & Model') a.click();
            });
        }""")
        await asyncio.sleep(3)

        # Re-select the maker for next batch
        maker_box2 = await page.evaluate(f"""() => {{
            for (const li of document.querySelectorAll('li.search-maker-checkbox')) {{
                if (li.textContent.trim() === '{maker}') {{
                    const r = li.getBoundingClientRect();
                    return {{ x: r.x + r.width/2, y: r.y + r.height/2 }};
                }}
            }}
            return null;
        }}""")
        if maker_box2:
            await page.mouse.click(maker_box2['x'], maker_box2['y'])
            await asyncio.sleep(3)

    return all_ids


async def _extract_results(page: Page, context: BrowserContext, maker: str, existing_ids: set) -> list[str]:
    """Extract vehicles from the results page. Handles pagination."""
    all_ids = []

    # Wait for car images to load
    for _ in range(10):
        img_count = await page.evaluate("() => document.querySelectorAll('img[data-code]').length")
        if img_count > 0:
            break
        await asyncio.sleep(2)

    result_text = await page.evaluate("""() => {
        const m = document.body.innerText.match(/Result[：:]\\s*(\\d[\\d,]*)/);
        return m ? m[1].replace(/,/g, '') : '0';
    }""")
    total = int(result_text)
    if total == 0:
        return []

    # Get __tid for building detail URLs
    tid = ""
    tid_match = re.search(r'__tid=([^&#]+)', page.url)
    if tid_match:
        tid = tid_match.group(1)

    page_num = 0
    while True:
        page_num += 1

        # Get vehicle IDs from image data-code attributes
        vehicle_ids = await page.evaluate("""() => {
            const items = [];
            const seen = new Set();
            document.querySelectorAll('img[data-code]').forEach(img => {
                const code = img.getAttribute('data-code');
                if (code && !seen.has(code)) {
                    seen.add(code);
                    items.push(code);
                }
            });
            return items;
        }""")

        if not vehicle_ids:
            break

        # Filter out existing
        new_ids = [vid for vid in vehicle_ids if f"iauc-{vid}" not in existing_ids]
        skipped = len(vehicle_ids) - len(new_ids)

        print(f"  [iauc] {maker} p{page_num}: {len(vehicle_ids)} vehicles ({skipped} existing, {len(new_ids)} new)")

        # Extract each new vehicle
        vehicles = []
        for vid in new_ids:
            try:
                v = await _extract_vehicle(page, vid, tid)
                if v and v.get("item_id"):
                    vehicles.append(v)
            except Exception as e:
                print(f"  [iauc] Detail {vid} failed: {e}")

        if vehicles:
            result = upsert_auctions(vehicles)
            all_ids.extend(v["item_id"] for v in vehicles)
            existing_ids.update(v["item_id"] for v in vehicles)
            img_total = sum(len(v.get("images", [])) for v in vehicles)
            print(f"  [iauc] {maker} p{page_num}: {len(vehicles)} → DB (new:{result['new']}, imgs:{img_total})")

        # Also track skipped IDs
        for vid in vehicle_ids:
            item_id = f"iauc-{vid}"
            if item_id not in all_ids:
                all_ids.append(item_id)

        # Next page
        has_next = await page.evaluate("""() => {
            const links = document.querySelectorAll('a');
            for (const a of links) {
                if (a.textContent.trim() === 'Next') {
                    a.click();
                    return true;
                }
            }
            return false;
        }""")

        if not has_next:
            break

        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(5)

        # Wait for new images
        for _ in range(10):
            cnt = await page.evaluate("() => document.querySelectorAll('img[data-code]').length")
            if cnt > 0:
                break
            await asyncio.sleep(2)

    return all_ids


async def _extract_vehicle(page: Page, vehicle_id: str, tid: str) -> dict | None:
    """Navigate to detail page, extract data + upload images."""
    detail_url = f"https://www.iauc.co.jp/detail/?vehicleId={vehicle_id}&owner_id=&from=vehicle&id=&__tid={tid}"
    await page.goto(detail_url, wait_until="networkidle", timeout=30000)
    await asyncio.sleep(3)

    # Parse data
    detail_text = await page.inner_text("body")
    vehicle = _parse_detail(detail_text, vehicle_id)

    # Get images
    imgs = await page.evaluate("""() => {
        return Array.from(document.querySelectorAll('img'))
            .filter(i => i.src.includes('iauc_pic') && i.naturalWidth > 100)
            .map(i => ({ src: i.src, w: i.naturalWidth, h: i.naturalHeight }));
    }""")

    # Upload images in parallel
    car_urls = []
    sheet_url = None
    for img in imgs:
        letter_match = re.search(r'/([A-F])\d+\.JPG', img['src'])
        if letter_match:
            letter = letter_match.group(1)
            if letter == 'A':
                sheet_url = img['src']
            else:
                car_urls.append(img['src'])

    # Parallel upload car images
    async def upload_one(url):
        return await _download_and_upload(page, url)

    car_results = await asyncio.gather(*[upload_one(u) for u in car_urls]) if car_urls else []
    car_images = [r for r in car_results if r]

    # Upload auction sheet
    exhibit_sheet = None
    if sheet_url:
        exhibit_sheet = await _download_and_upload(page, sheet_url)

    vehicle["images"] = car_images
    vehicle["image_url"] = car_images[0] if car_images else None
    vehicle["exhibit_sheet"] = exhibit_sheet

    # Go back to results
    await page.go_back()
    await page.wait_for_load_state("networkidle", timeout=30000)
    await asyncio.sleep(3)

    return vehicle


def _parse_detail(text: str, vehicle_id: str) -> dict:
    """Parse iAUC detail page. Fields are tab-separated."""
    fields = {}
    for line in text.split("\n"):
        line = line.strip()
        if "\t" in line:
            parts = line.split("\t", 1)
            if len(parts) == 2:
                fields[parts[0].strip()] = parts[1].strip()

    # Get maker/model
    maker = ""
    model = ""
    known_makers = [
        "TOYOTA", "LEXUS", "NISSAN", "HONDA", "MAZDA", "MITSUBISHI",
        "SUBARU", "DAIHATSU", "SUZUKI", "BMW", "MERCEDES-BENZ", "AUDI",
        "VOLKSWAGEN", "PORSCHE", "ISUZU", "HINO", "VOLVO", "JAGUAR",
        "FORD", "GM", "CHRYSLER", "ALFA ROMEO", "FIAT", "FERRARI",
        "MASERATI", "OPEL", "SMART", "ROVER", "BENTLEY", "TESLA",
        "PEUGEOT", "RENAULT", "CITROEN", "LAMBORGHINI", "BYD",
    ]
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for i, line in enumerate(lines):
        if line in known_makers:
            maker = line
            if i + 1 < len(lines):
                model = lines[i + 1].strip()
            break

    lot_no = fields.get("Lot No.", "")
    grade = fields.get("Grade", "")
    year_raw = fields.get("Year", "")
    cc = fields.get("cc", "")
    score = fields.get("Score", "")
    color = fields.get("Color", "")
    color_no = fields.get("Color No.", "")
    odometer = fields.get("Odometer", "")
    start_price_raw = fields.get("Start Price", "")
    auction_site = fields.get("Auction Site", "")
    holding_date = fields.get("Holding Date", "")
    exterior = fields.get("Exterior", "")
    interior = fields.get("Interior", "")
    inspection = fields.get("Inspection", "")

    year = ""
    year_match = re.search(r'(20\d{2})', year_raw)
    if year_match:
        year = year_match.group(1)

    start_price = start_price_raw.replace(",", "") if start_price_raw else None

    rating = score
    if exterior or interior:
        rating = f"{score} {exterior}/{interior}".strip()

    site_name = auction_site.split("[")[0].strip() if auction_site else ""
    location = ""
    loc_match = re.search(r'\[(.+?)\]', auction_site)
    if loc_match:
        location = loc_match.group(1)

    color_str = color
    if color_no:
        color_str = f"{color} ({color_no})"

    return {
        "item_id": f"iauc-{vehicle_id}",
        "lot_number": lot_no,
        "maker": maker,
        "model": model,
        "grade": grade or None,
        "chassis_code": None,
        "engine_specs": cc or None,
        "year": year or year_raw,
        "mileage": odometer or None,
        "inspection_expiry": inspection or None,
        "color": color_str or None,
        "rating": rating or None,
        "start_price": start_price if start_price else None,
        "auction_date": holding_date,
        "auction_house": site_name or "iAUC",
        "location": location or site_name,
        "status": "upcoming",
        "image_url": None,
        "images": [],
        "exhibit_sheet": None,
        "source": "iauc",
    }


async def _download_and_upload(page: Page, url: str) -> str | None:
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
                return upload_image(img_bytes, "iauc-images", url)
        return None
    except:
        return None
