"""iAUC scraper: Select all upcoming auctions, all makers, batch by 20 models.
Simplified: select all at once instead of day-by-day or maker-by-maker."""

import asyncio
import base64
import re
from playwright.async_api import Page, BrowserContext
from db import upsert_auctions, get_existing_item_ids
from storage import upload_image

BATCH_SIZE = 20


async def iauc_search_and_extract(page: Page, context: BrowserContext) -> list[str]:
    """Full iAUC scrape."""

    existing_ids = get_existing_item_ids("iauc")
    print(f"  [iauc] {len(existing_ids)} existing vehicles in DB (will skip)")

    # === Step 1: Select upcoming auctions ===
    print("  [iauc] Selecting upcoming auctions...")
    await page.evaluate("""() => {
        document.querySelectorAll('input[name="e[]"]').forEach(cb => { if (cb.checked) cb.click(); });
        document.querySelectorAll('input[name="d[]"]').forEach(cb => { if (cb.checked) cb.click(); });
    }""")
    await asyncio.sleep(1)

    # Select All Auction & Tender
    await page.click("a.title-button.checkbox_on_all")
    await asyncio.sleep(1)

    # Uncheck Today (finished auctions)
    days = await page.evaluate("""() => {
        return Array.from(document.querySelectorAll('button.day-button')).map(btn => {
            const r = btn.getBoundingClientRect();
            return { text: btn.textContent.trim(), x: r.x + r.width/2, y: r.y + r.height/2 };
        });
    }""")
    today = next((d for d in days if d['text'] == 'Today'), None)
    if today:
        await page.mouse.click(today['x'], today['y'])
        await asyncio.sleep(1)

    checked = await page.evaluate('() => document.querySelectorAll(\'input[name="d[]"]:checked\').length')
    print(f"  [iauc] {checked} auction sites selected (all upcoming)")

    if checked == 0:
        print("  [iauc] No upcoming auctions!")
        return []

    # === Step 2: Go to Make & Model ===
    await page.evaluate('() => check_sites(document.querySelector(".page-next-button"))')
    for _ in range(20):
        await asyncio.sleep(2)
        if "#maker" in page.url or "search" in page.url:
            break
    await asyncio.sleep(3)

    if "#maker" not in page.url and "search" not in page.url:
        print(f"  [iauc] Failed to reach Make & Model page")
        return []

    # === Step 3: Select ALL Japanese + Imported makers ===
    print("  [iauc] Selecting all makers...")
    # Click Japanese "All"
    jp_all = page.locator('button:text-is("All")').nth(0)
    im_all = page.locator('button:text-is("All")').nth(1)

    for btn in [jp_all, im_all]:
        try:
            if await btn.is_visible():
                await btn.click()
                await asyncio.sleep(1)
        except:
            pass

    # Fallback: click each maker via mouse if All buttons didn't work
    makers_checked = await page.evaluate('() => document.querySelectorAll(\'input[name="maker[]"]:checked\').length')
    if makers_checked == 0:
        print("  [iauc] All buttons didn't work, clicking makers manually...")
        maker_boxes = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('li.search-maker-checkbox')).map(li => {
                const r = li.getBoundingClientRect();
                return { text: li.textContent.trim(), x: r.x + r.width/2, y: r.y + r.height/2, visible: r.y > 0 };
            }).filter(m => m.visible);
        }""")
        for m in maker_boxes:
            await page.mouse.click(m['x'], m['y'])
            await asyncio.sleep(0.2)

    await asyncio.sleep(3)
    makers_checked = await page.evaluate('() => document.querySelectorAll(\'input[name="maker[]"]:checked\').length')
    print(f"  [iauc] {makers_checked} makers selected")

    # === Step 4: Get all models ===
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

    visible_models = [m for m in models if m['visible']]
    total_cars = sum(m['cnt'] for m in visible_models)
    print(f"  [iauc] {len(visible_models)} models visible, {total_cars} total vehicles")

    if total_cars == 0:
        return []

    # === Step 5: Batch by 20 models, search each batch ===
    all_ids = []

    for batch_start in range(0, len(visible_models), BATCH_SIZE):
        batch = visible_models[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        batch_total = sum(m['cnt'] for m in batch)
        batch_names = [m['name'] for m in batch[:3]]

        print(f"  [iauc] Batch {batch_num}: {len(batch)} models ({batch_total} vehicles) [{', '.join(batch_names)}...]")

        # Clear previous model selection
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="type[]"]:checked').forEach(inp => {
                const li = inp.closest('li');
                if (li) li.click();
            });
        }""")
        await asyncio.sleep(1)

        # Select models in this batch via mouse click
        for m in batch:
            if m['y'] > 0:
                await page.mouse.click(m['x'], m['y'])
                await asyncio.sleep(0.15)
        await asyncio.sleep(1)

        # Enable and click Next
        await page.evaluate('() => { var b = document.querySelector("#next-bottom"); if (b) { b.disabled = false; b.click(); } }')
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass
        await asyncio.sleep(8)

        # Get __tid
        tid = await page.evaluate("""() => {
            for (const a of document.querySelectorAll('a[href*="__tid"]')) {
                const m = a.href.match(/__tid=([^&#]+)/);
                if (m) return m[1];
            }
            return '';
        }""")

        # Wait for vehicle images
        for _ in range(10):
            cnt = await page.evaluate("() => document.querySelectorAll('img[data-code]').length")
            if cnt > 0:
                break
            await asyncio.sleep(2)

        # Get vehicle IDs
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

        new_ids = [vid for vid in vehicle_ids if f"iauc-{vid}" not in existing_ids]
        print(f"  [iauc] Batch {batch_num}: {len(vehicle_ids)} on page ({len(new_ids)} new)")

        # Extract each vehicle
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
            print(f"  [iauc] Batch {batch_num}: {len(vehicles)} → DB (new:{result['new']}, imgs:{img_total})")

        # Track all IDs
        for vid in vehicle_ids:
            item_id = f"iauc-{vid}"
            if item_id not in all_ids:
                all_ids.append(item_id)

        # TODO: handle pagination within this batch (Next page button)

        # Go back to Make & Model for next batch
        await page.evaluate("""() => {
            document.querySelectorAll('a').forEach(a => {
                if (a.textContent.trim() === 'Select Make & Model') a.click();
            });
        }""")
        await asyncio.sleep(5)

    print(f"  [iauc] Total: {len(all_ids)} vehicles")
    return all_ids


async def _extract_vehicle(page: Page, vehicle_id: str, tid: str) -> dict | None:
    """Navigate to detail, extract data + upload images."""
    if not tid:
        tid = await page.evaluate("""() => {
            for (const a of document.querySelectorAll('a[href*="__tid"]')) {
                const m = a.href.match(/__tid=([^&#]+)/);
                if (m) return m[1];
            }
            return '';
        }""")

    detail_url = f"https://www.iauc.co.jp/detail/?vehicleId={vehicle_id}&owner_id=&from=vehicle&id=&__tid={tid}"
    try:
        await page.goto(detail_url, wait_until="domcontentloaded", timeout=20000)
    except:
        pass
    await asyncio.sleep(2)

    if "detail" not in page.url:
        return None

    detail_text = await page.inner_text("body")
    vehicle = _parse_detail(detail_text, vehicle_id)

    if not vehicle.get("maker"):
        return None

    # Get images
    imgs = await page.evaluate("""() => {
        return Array.from(document.querySelectorAll('img'))
            .filter(i => i.src && i.src.includes('iauc_pic'))
            .map(i => ({ src: i.src, w: i.naturalWidth, h: i.naturalHeight }));
    }""")

    car_urls = []
    sheet_url = None
    for img in imgs:
        src = img['src']
        # Pattern 1: /A09008.JPG
        letter_match = re.search(r'/([A-F])\d+\.JPG', src)
        if letter_match:
            if letter_match.group(1) == 'A':
                sheet_url = src
            else:
                car_urls.append(src)
            continue
        # Pattern 2: _scan.jpg / _1.jpg
        if '_scan.' in src:
            sheet_url = src
        elif re.search(r'_\d+\.jpg', src):
            car_urls.append(src)

    # Parallel upload
    async def upload_one(url):
        return await _download_and_upload(page, url)

    car_results = await asyncio.gather(*[upload_one(u) for u in car_urls]) if car_urls else []
    car_images = [r for r in car_results if r]

    exhibit_sheet = None
    if sheet_url:
        exhibit_sheet = await _download_and_upload(page, sheet_url)

    vehicle["images"] = car_images
    vehicle["image_url"] = car_images[0] if car_images else None
    vehicle["exhibit_sheet"] = exhibit_sheet

    # Go back
    await page.go_back()
    await asyncio.sleep(2)

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

    start_price = None
    if start_price_raw:
        try:
            price_yen = int(start_price_raw.replace(",", ""))
            start_price = str(price_yen / 10000)
        except ValueError:
            pass

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
