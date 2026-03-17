"""iAUC scraper: day-by-day, maker-by-maker, models in batches of 20.
Scrapes one upcoming day at a time (WED→THU→FRI→SAT→MON).
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
    """Full iAUC scrape — day by day, starting from next upcoming day."""

    existing_ids = get_existing_item_ids("iauc")
    print(f"  [iauc] {len(existing_ids)} existing vehicles in DB (will skip)")

    # Get upcoming days from the page
    upcoming_days = await _get_upcoming_days(page)
    if not upcoming_days:
        print("  [iauc] No upcoming days found!")
        return []

    print(f"  [iauc] Upcoming days: {[d['label'] for d in upcoming_days]}")

    all_ids = []

    for day in upcoming_days:
        print(f"\n  [iauc] ===== {day['label']} =====")
        try:
            ids = await _scrape_day(page, context, day, existing_ids)
            all_ids.extend(ids)
            print(f"  [iauc] {day['label']} complete: {len(ids)} vehicles")
        except Exception as e:
            print(f"  [iauc] {day['label']} failed: {e}")
            # Try to go back to auction selection for next day
            try:
                await page.evaluate("""() => {
                    document.querySelectorAll('a').forEach(a => {
                        if (a.textContent.trim() === 'Select Auctions') a.click();
                    });
                }""")
                await asyncio.sleep(5)
            except:
                pass

    print(f"\n  [iauc] Total across all days: {len(all_ids)} vehicles")
    return all_ids


async def _get_upcoming_days(page: Page) -> list[dict]:
    """Get list of upcoming day buttons (skip Today/finished)."""
    days = await page.evaluate("""() => {
        const results = [];
        document.querySelectorAll('button.day-button').forEach(btn => {
            const text = btn.textContent.trim();
            const cls = btn.className || '';
            const rect = btn.getBoundingClientRect();

            // Count checkboxes in this day's section
            // Day sections have d[] checkboxes grouped together
            let hasListed = false;
            let sectionEl = btn.parentElement;
            if (sectionEl) {
                sectionEl.querySelectorAll('input[name="d[]"]').forEach(cb => {
                    const li = cb.closest('li') || cb.parentElement;
                    const liText = li?.textContent?.trim() || '';
                    if (liText.includes('Listed') || liText.includes('Preparing')) {
                        hasListed = true;
                    }
                });
            }

            results.push({
                label: text,
                isToday: text === 'Today' || cls.includes('active'),
                hasListed,
                x: rect.x + rect.width / 2,
                y: rect.y + rect.height / 2,
            });
        });
        return results;
    }""")

    # Filter: skip Today, only keep days that have listed auctions
    upcoming = [d for d in days if not d['isToday']]
    return upcoming


async def _scrape_day(page: Page, context: BrowserContext, day: dict, existing_ids: set) -> list[str]:
    """Scrape all vehicles for one day."""

    # Go to auction selection page
    await page.evaluate("""() => {
        document.querySelectorAll('a').forEach(a => {
            if (a.textContent.trim() === 'Select Auctions') a.click();
        });
    }""")
    await asyncio.sleep(5)

    # Uncheck Kyoyuzaiko and all auction sites
    await page.evaluate("""() => {
        document.querySelectorAll('input[name="e[]"]').forEach(cb => { if (cb.checked) cb.click(); });
        document.querySelectorAll('input[name="d[]"]').forEach(cb => { if (cb.checked) cb.click(); });
    }""")
    await asyncio.sleep(1)

    # Select All Auction & Tender sites
    await page.click("a.title-button.checkbox_on_all")
    await asyncio.sleep(1)

    # Get all day buttons
    all_days = await page.evaluate("""() => {
        return Array.from(document.querySelectorAll('button.day-button')).map(btn => {
            const r = btn.getBoundingClientRect();
            return { text: btn.textContent.trim(), x: r.x + r.width/2, y: r.y + r.height/2 };
        });
    }""")

    # Uncheck every day EXCEPT the target day
    for d in all_days:
        if d['text'] != day['label']:
            await page.mouse.click(d['x'], d['y'])
            await asyncio.sleep(0.5)
    await asyncio.sleep(1)

    checked = await page.evaluate('() => document.querySelectorAll(\'input[name="d[]"]:checked\').length')
    print(f"  [iauc] {day['label']}: {checked} auction sites selected (Auction + Tender)")

    if checked == 0:
        print(f"  [iauc] {day['label']}: no auctions, skipping")
        return []

    # Click Next to Make & Model page
    await page.evaluate('() => check_sites(document.querySelector(".page-next-button"))')
    for _ in range(20):
        await asyncio.sleep(2)
        if "#maker" in page.url or "search" in page.url:
            break
    await asyncio.sleep(3)

    if "#maker" not in page.url and "search" not in page.url:
        print(f"  [iauc] Failed to reach Make & Model page")
        return []

    # Scrape all makers for this day
    all_ids = []
    all_makers = JP_MAKERS + IMPORTED_MAKERS

    for maker in all_makers:
        try:
            ids = await _scrape_maker(page, context, maker, existing_ids)
            all_ids.extend(ids)
            if ids:
                print(f"  [iauc] {day['label']} > {maker}: {len(ids)} vehicles")
        except Exception as e:
            print(f"  [iauc] {day['label']} > {maker} failed: {e}")

    return all_ids


async def _scrape_maker(page: Page, context: BrowserContext, maker: str, existing_ids: set) -> list[str]:
    """Scrape all vehicles for one maker, models in batches of 20."""

    # Navigate to Make & Model tab
    await page.evaluate("""() => {
        document.querySelectorAll('a').forEach(a => {
            if (a.textContent.trim() === 'Select Make & Model') a.click();
        });
    }""")
    await asyncio.sleep(3)

    # Clear previous selection
    await page.evaluate("""() => {
        document.querySelectorAll('button').forEach(b => {
            if (b.textContent.trim() === 'Clear All' && b.offsetParent !== null) b.click();
        });
    }""")
    await asyncio.sleep(2)

    # Click the maker
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
        return []

    await page.mouse.click(maker_box['x'], maker_box['y'])
    await asyncio.sleep(3)

    # Get models
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

    # Process visible models in batches of 20
    all_ids = []
    visible_models = [m for m in models if m['visible']]

    for batch_start in range(0, len(visible_models), BATCH_SIZE):
        batch = visible_models[batch_start:batch_start + BATCH_SIZE]
        batch_total = sum(m['cnt'] for m in batch)
        if batch_total == 0:
            continue

        # Clear previous model selection
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="type[]"]').forEach(inp => {
                if (inp.checked) {
                    const li = inp.closest('li');
                    if (li) li.click();
                }
            });
        }""")
        await asyncio.sleep(1)

        # Select models in this batch
        for m in batch:
            if m['y'] > 0:
                await page.mouse.click(m['x'], m['y'])
                await asyncio.sleep(0.2)
        await asyncio.sleep(1)

        # Enable and click Next
        next_disabled = await page.evaluate('() => document.querySelector("#next-bottom")?.disabled')
        if next_disabled:
            await page.evaluate('() => { var b = document.querySelector("#next-bottom"); if (b) b.disabled = false; }')

        await page.evaluate('() => document.querySelector("#next-bottom")?.click()')
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass
        await asyncio.sleep(8)

        # Extract vehicles
        ids = await _extract_results(page, context, maker, existing_ids)
        all_ids.extend(ids)

        # Go back to Make & Model for next batch
        await page.evaluate("""() => {
            document.querySelectorAll('a').forEach(a => {
                if (a.textContent.trim() === 'Select Make & Model') a.click();
            });
        }""")
        await asyncio.sleep(3)

        # Re-select maker
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
    """Extract vehicles from results page with pagination."""
    all_ids = []

    # Wait for images to load
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

    # Get __tid
    tid = ""
    tid_match = re.search(r'__tid=([^&#]+)', page.url)
    if tid_match:
        tid = tid_match.group(1)

    page_num = 0
    while True:
        page_num += 1

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

        new_ids = [vid for vid in vehicle_ids if f"iauc-{vid}" not in existing_ids]
        skipped = len(vehicle_ids) - len(new_ids)
        print(f"  [iauc] {maker} p{page_num}: {len(vehicle_ids)} vehicles ({skipped} existing, {len(new_ids)} new)")

        # Extract new vehicles
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

        # Track all as seen
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

        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass
        await asyncio.sleep(5)

        for _ in range(10):
            cnt = await page.evaluate("() => document.querySelectorAll('img[data-code]').length")
            if cnt > 0:
                break
            await asyncio.sleep(2)

    return all_ids


async def _extract_vehicle(page: Page, vehicle_id: str, tid: str) -> dict | None:
    """Navigate to detail, extract data + upload images."""
    detail_url = f"https://www.iauc.co.jp/detail/?vehicleId={vehicle_id}&owner_id=&from=vehicle&id=&__tid={tid}"
    await page.goto(detail_url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3)

    detail_text = await page.inner_text("body")
    vehicle = _parse_detail(detail_text, vehicle_id)

    # Get images
    imgs = await page.evaluate("""() => {
        return Array.from(document.querySelectorAll('img'))
            .filter(i => i.src.includes('iauc_pic') && i.naturalWidth > 100)
            .map(i => ({ src: i.src, w: i.naturalWidth, h: i.naturalHeight }));
    }""")

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
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except:
        pass
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
