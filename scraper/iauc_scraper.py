"""iAUC scraper: Select upcoming auctions, all makers, batch models.
Uses JS checkbox clicks (not mouse), supports pagination.
Limits: 500 vehicles & 30 min per batch cycle, smallest models first."""

import asyncio
import base64
import os
import re
import time
from playwright.async_api import Page, BrowserContext
from db import upsert_auctions, get_existing_item_ids, normalize_auction_date
from storage import upload_image
from jst import should_scrape_today, get_target_date, now_jst

# ── Mode switch ─────────────────────────────────────────────────────────────
# Set IAUC_OVERNIGHT=true in env to enable full overnight pass.
# run_iauc.py sets this automatically via the 11pm JST cron job.
OVERNIGHT_MODE = os.getenv("IAUC_OVERNIGHT", "false").lower() == "true"

# ── Japanese makers (scraped first in daytime mode) ──────────────────────────
JAPANESE_MAKERS = {
    "TOYOTA", "LEXUS", "NISSAN", "HONDA", "MAZDA",
    "MITSUBISHI", "SUBARU", "DAIHATSU", "SUZUKI",
    "ISUZU", "HINO",
}

# ── Limits (overnight vs daytime delta) ─────────────────────────────────────
BATCH_SIZE           = 50    if OVERNIGHT_MODE else 40    # models per batch
MAX_VEHICLES_TOTAL   = 99999 if OVERNIGHT_MODE else 5000  # no cap overnight
MAX_TIME_TOTAL       = 28800 if OVERNIGHT_MODE else 10800 # 8 hrs vs 3 hrs
MAX_RESULTS_PER_BATCH = 500  if OVERNIGHT_MODE else 400   # pagination depth
CONCURRENT_TABS      = 15   if OVERNIGHT_MODE else 8      # parallel extractions


async def _select_makers(page: Page, maker_names: set[str] | None = None):
    """Select makers on the Make & Model page.
    maker_names=None → select all makers (overnight behavior).
    maker_names=set  → select only makers whose label matches."""
    if maker_names is None:
        # Click both "All" buttons (Japanese + Imported sections)
        await page.evaluate("""() => {
            const allBtns = Array.from(document.querySelectorAll('button'))
                .filter(b => b.textContent.trim() === 'All' && b.offsetParent !== null);
            allBtns.forEach(b => b.click());
        }""")
        await asyncio.sleep(2)
        # Fallback: click each maker via mouse
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
    else:
        # First uncheck all makers
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="maker[]"]:checked').forEach(inp => inp.click());
        }""")
        await asyncio.sleep(0.5)
        # Click only makers whose text matches the filter set
        maker_boxes = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('li.search-maker-checkbox')).map(li => {
                const r = li.getBoundingClientRect();
                return { text: li.textContent.trim(), x: r.x + r.width/2, y: r.y + r.height/2, visible: r.y > 0 };
            }).filter(m => m.visible);
        }""")
        clicked = 0
        for m in maker_boxes:
            # Match maker name: the li text may include count, e.g. "TOYOTA (123)"
            label = m['text'].split('(')[0].strip().upper()
            if label in maker_names:
                await page.mouse.click(m['x'], m['y'])
                await asyncio.sleep(0.2)
                clicked += 1
        print(f"  [iauc] Clicked {clicked} makers matching filter")

    await asyncio.sleep(2)
    makers_checked = await page.evaluate('() => document.querySelectorAll(\'input[name="maker[]"]:checked\').length')
    print(f"  [iauc] {makers_checked} makers selected")
    return makers_checked


async def iauc_search_and_extract(page: Page, context: BrowserContext) -> list[str]:
    """Full iAUC scrape."""

    scrape_start = time.time()

    existing_ids = get_existing_item_ids("iauc")
    print(f"  [iauc] {len(existing_ids)} existing vehicles in DB (will skip)")

    # === Step 1: Select upcoming auctions (smart date based on JST) ===
    scrape_today = should_scrape_today()
    jst_now = now_jst()
    print(f"  [iauc] JST time: {jst_now.strftime('%Y-%m-%d %H:%M')} — {'including' if scrape_today else 'excluding'} today's auctions")

    await page.evaluate("""() => {
        document.querySelectorAll('input[name="e[]"]').forEach(cb => { if (cb.checked) cb.click(); });
        document.querySelectorAll('input[name="d[]"]').forEach(cb => { if (cb.checked) cb.click(); });
    }""")
    await asyncio.sleep(1)

    # Select All Auction & Tender
    await page.click("a.title-button.checkbox_on_all")
    await asyncio.sleep(1)

    # should_scrape_today() is always True so this block never runs.
    # Today's checkbox stays checked — we always include today's upcoming auctions.
    # After midnight JST, today_jst() rolls naturally to the next day.
    if not scrape_today:
        days = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('button.day-button')).map(btn => {
                const r = btn.getBoundingClientRect();
                return { text: btn.textContent.trim(), x: r.x + r.width/2, y: r.y + r.height/2 };
            });
        }""")
        today_btn = next((d for d in days if d['text'] == 'Today'), None)
        if today_btn:
            await page.mouse.click(today_btn['x'], today_btn['y'])
            await asyncio.sleep(1)
            print("  [iauc] Unchecked 'Today' — scraping tomorrow's auctions only")

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

    # Save the search URL for re-navigation between batches
    search_base_url = page.url.split("#")[0]
    print(f"  [iauc] Search URL saved: {search_base_url[:60]}...")

    # === Step 3+4+5: Two-pass maker strategy ===
    # Overnight: one pass with all makers
    # Daytime: Pass 1 = Japanese makers only, Pass 2 = all makers (existing_ids skips dupes)
    if OVERNIGHT_MODE:
        maker_passes = [(None, "All makers")]
    else:
        maker_passes = [
            (JAPANESE_MAKERS, "Japanese makers"),
            (None, "All makers (foreign + remaining)"),
        ]

    all_ids = []

    for pass_idx, (maker_filter, pass_label) in enumerate(maker_passes):
        # Check limits before starting a new pass
        elapsed = time.time() - scrape_start
        if len(all_ids) >= MAX_VEHICLES_TOTAL:
            print(f"  [iauc] Vehicle limit reached ({len(all_ids)}/{MAX_VEHICLES_TOTAL}), skipping pass {pass_idx + 1}")
            break
        if elapsed >= MAX_TIME_TOTAL:
            print(f"  [iauc] Time limit reached ({elapsed/60:.1f} min), skipping pass {pass_idx + 1}")
            break

        print(f"  [iauc] ── Pass {pass_idx + 1}: {pass_label} ──")

        # On pass 2+, reload the maker page
        if pass_idx > 0:
            search_url = search_base_url + "#maker"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(3)

        # Select makers for this pass
        await _select_makers(page, maker_filter)

        # Get all models, sort smallest first
        models = await page.evaluate("""() => {
            const items = [];
            document.querySelectorAll('input[name="type[]"]').forEach((inp, idx) => {
                const name = inp.getAttribute('data-name') || '';
                const cnt = parseInt(inp.getAttribute('data-cnt') || '0');
                if (cnt > 0) {
                    items.push({ name, cnt, idx });
                }
            });
            items.sort((a, b) => a.cnt - b.cnt);
            return items;
        }""")

        total_cars = sum(m['cnt'] for m in models)
        print(f"  [iauc] Pass {pass_idx + 1}: {len(models)} models, {total_cars} total vehicles (sorted smallest first)")
        print(f"  [iauc] Limits: {MAX_VEHICLES_TOTAL} vehicles, {MAX_TIME_TOTAL // 60} min total")

        if total_cars == 0:
            print(f"  [iauc] Pass {pass_idx + 1}: no vehicles, moving on")
            continue

        # Batch models, search each batch
        for batch_start in range(0, len(models), BATCH_SIZE):
            # Check global limits
            elapsed = time.time() - scrape_start
            if elapsed >= MAX_TIME_TOTAL:
                print(f"  [iauc] Time limit reached ({elapsed/60:.1f} min), stopping")
                break
            if len(all_ids) >= MAX_VEHICLES_TOTAL:
                print(f"  [iauc] Vehicle limit reached ({len(all_ids)}/{MAX_VEHICLES_TOTAL}), stopping")
                break

            batch = models[batch_start:batch_start + BATCH_SIZE]
            batch_num = batch_start // BATCH_SIZE + 1
            batch_total = sum(m['cnt'] for m in batch)
            batch_names = [m['name'] for m in batch[:3]]

            print(f"  [iauc] P{pass_idx + 1} Batch {batch_num}: {len(batch)} models ({batch_total} vehicles) [{', '.join(batch_names)}...]")

            # Clear previous model selection via JS
            await page.evaluate("""() => {
                document.querySelectorAll('input[name="type[]"]:checked').forEach(inp => inp.click());
            }""")
            await asyncio.sleep(0.5)

            # Select models in this batch via JS checkbox click (not mouse — works off-screen)
            batch_indices = [m['idx'] for m in batch]
            await page.evaluate("""(indices) => {
                const inputs = document.querySelectorAll('input[name="type[]"]');
                indices.forEach(idx => {
                    if (inputs[idx] && !inputs[idx].checked) inputs[idx].click();
                });
            }""", batch_indices)
            await asyncio.sleep(1)

            # Enable and click Next
            await page.evaluate('() => { var b = document.querySelector("#next-bottom"); if (b) { b.disabled = false; b.click(); } }')
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except:
                pass
            await asyncio.sleep(4)

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
                await asyncio.sleep(1)

            # Paginate through results for this batch
            batch_ids = []
            page_num = 0
            while True:
                page_num += 1

                # Check limits
                if len(all_ids) + len(batch_ids) >= MAX_VEHICLES_TOTAL:
                    break
                if time.time() - scrape_start >= MAX_TIME_TOTAL:
                    break
                if len(batch_ids) >= MAX_RESULTS_PER_BATCH:
                    print(f"  [iauc] P{pass_idx + 1} Batch {batch_num}: result limit reached ({len(batch_ids)})")
                    break

                # Get vehicle IDs on current page (short format only: XX-XXXX-XXXX)
                vehicle_ids = await page.evaluate("""() => {
                    const items = [];
                    const seen = new Set();
                    document.querySelectorAll('img[data-code]').forEach(img => {
                        const code = img.getAttribute('data-code');
                        if (!code) return;
                        // Only use short codes (3 parts). Long codes (6 parts) return "Not Found" on detail page
                        const parts = code.split('-');
                        const shortCode = parts.length > 3 ? parts.slice(0, 3).join('-') : code;
                        if (!seen.has(shortCode)) {
                            seen.add(shortCode);
                            items.push(shortCode);
                        }
                    });
                    return items;
                }""")

                if not vehicle_ids:
                    break

                new_ids = [vid for vid in vehicle_ids if f"iauc-{vid}" not in existing_ids]
                skipped = len(vehicle_ids) - len(new_ids)
                if page_num == 1:
                    print(f"  [iauc] P{pass_idx + 1} Batch {batch_num} p{page_num}: {len(vehicle_ids)} on page ({len(new_ids)} new, {skipped} existing)")
                else:
                    print(f"  [iauc] P{pass_idx + 1} Batch {batch_num} p{page_num}: {len(vehicle_ids)} ({len(new_ids)} new)")

                # ── Parallel vehicle extraction ──────────────────────────────────
                target = get_target_date()
                semaphore = asyncio.Semaphore(CONCURRENT_TABS)

                async def extract_with_limit(vid: str):
                    async with semaphore:
                        new_page = await context.new_page()
                        try:
                            return await _extract_vehicle(new_page, vid, tid)
                        except Exception as e:
                            print(f"  [iauc] Detail {vid} failed: {e}")
                            return None
                        finally:
                            await new_page.close()

                raw_results = await asyncio.gather(
                    *[extract_with_limit(vid) for vid in new_ids],
                    return_exceptions=True,
                )

                vehicles = []
                skipped_date = 0
                for v in raw_results:
                    if not v or isinstance(v, Exception) or not v.get("item_id"):
                        continue
                    auction_date_str = v.get("auction_date", "")
                    auction_date = normalize_auction_date(auction_date_str, "iauc")
                    if auction_date and auction_date < target:
                        skipped_date += 1
                        continue
                    vehicles.append(v)

                if skipped_date:
                    print(f"  [iauc] P{pass_idx + 1} Batch {batch_num} p{page_num}: skipped {skipped_date} vehicles with past auction dates")

                if vehicles:
                    result = upsert_auctions(vehicles)
                    all_ids.extend(v["item_id"] for v in vehicles)
                    existing_ids.update(v["item_id"] for v in vehicles)
                    img_total = sum(len(v.get("images", [])) for v in vehicles)
                    print(f"  [iauc] P{pass_idx + 1} Batch {batch_num} p{page_num}: {len(vehicles)} → DB (new:{result['new']}, imgs:{img_total})")

                # Track all IDs (including skipped existing)
                for vid in vehicle_ids:
                    item_id = f"iauc-{vid}"
                    if item_id not in batch_ids:
                        batch_ids.append(item_id)

                # Try next page
                has_next = await page.evaluate("""() => {
                    const links = document.querySelectorAll('a');
                    for (const a of links) {
                        if (a.textContent.trim() === 'Next' && a.getAttribute('onclick') && a.getAttribute('onclick').includes('get_carlist')) {
                            a.click();
                            return true;
                        }
                    }
                    return false;
                }""")
                if not has_next:
                    break
                await asyncio.sleep(3)

                # Wait for new results to load
                for _ in range(10):
                    cnt = await page.evaluate("() => document.querySelectorAll('img[data-code]').length")
                    if cnt > 0:
                        break
                    await asyncio.sleep(1)

            # Add batch IDs to total
            for bid in batch_ids:
                if bid not in all_ids:
                    all_ids.append(bid)

            # Reload Make & Model page fresh for next batch
            search_url = search_base_url + "#maker"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(3)
            # Re-select makers for this pass
            await _select_makers(page, maker_filter)

    elapsed = time.time() - scrape_start
    print(f"  [iauc] Total: {len(all_ids)} vehicles in {elapsed/60:.1f} min")
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

    # Get images — iauc_pic URLs contain car photos and exhibit sheets
    imgs = await page.evaluate("""() => {
        return Array.from(document.querySelectorAll('img'))
            .filter(i => i.src && i.src.includes('iauc_pic') && i.naturalWidth > 100)
            .map(i => ({ src: i.src, w: i.naturalWidth, h: i.naturalHeight }));
    }""")

    car_urls = []
    sheet_url = None
    seen_urls = set()
    for img in imgs:
        src = img['src']
        # Dedupe by base filename (ignore query params)
        base = src.split('?')[0]
        if base in seen_urls:
            continue
        seen_urls.add(base)

        filename = base.split('/')[-1].upper()
        # Exhibit sheet: starts with A (e.g., A05009.JPG) or contains _scan
        if re.match(r'^A\d+\.JPG', filename) or '_scan.' in src.lower():
            if not sheet_url:
                sheet_url = src
        else:
            # Car photos: everything else (B, C, D, F, R, V patterns, numbered, etc.)
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
                raw_model = lines[i + 1].strip()
                # Strip chassis code (e.g., "Prius ZVW30-5355115" → "Prius")
                # Chassis codes look like: ABC123-456789 or ABC12 (caps+digits pattern)
                model = re.split(r'\s+[A-Z0-9]{3,}-', raw_model)[0].strip()
                if not model:
                    model = raw_model
                # Also strip standalone chassis codes like "ZVW55" at end
                model = re.sub(r'\s+[A-Z]{1,4}\d{2,}$', '', model).strip()
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
