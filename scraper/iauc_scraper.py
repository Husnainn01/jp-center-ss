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

# ── Limits (same for day and night — skip logic makes daytime fast) ────────
BATCH_SIZE           = 50     # models per batch
MAX_VEHICLES_TOTAL   = 99999  # no cap — skip logic handles dedup
MAX_TIME_TOTAL       = 28800  # 8 hrs safety valve (daytime exits early via skip logic)
MAX_RESULTS_PER_BATCH = 99999 # no cap — time limit is the safety valve
CONCURRENT_TABS      = 15    # parallel detail page extractions


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

    # should_scrape_today() returns True — we include today's auctions.
    # This block only runs if should_scrape_today() is overridden to False.
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

    # === Step 3+4+5: Single pass with all makers ===
    # No need for 2-pass strategy — largest models first + skip logic makes this fast
    maker_passes = [(None, "All makers")]

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
            items.sort((a, b) => b.cnt - a.cnt);
            return items;
        }""")

        total_cars = sum(m['cnt'] for m in models)
        print(f"  [iauc] Pass {pass_idx + 1}: {len(models)} models, {total_cars} total vehicles (sorted LARGEST first)")
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

            # Switch to 100 items per page for faster pagination (default is 15)
            # The page has a <select id="select_limit"> with onchange="get_carlist(this)"
            switched = await page.evaluate("""() => {
                const sel = document.getElementById('select_limit');
                if (sel) {
                    sel.value = '100';
                    // Trigger the onchange which calls get_carlist
                    sel.dispatchEvent(new Event('change'));
                    return true;
                }
                return false;
            }""")
            if switched:
                await asyncio.sleep(4)
                # Wait for page to reload with more items
                for _ in range(15):
                    cnt = await page.evaluate("() => document.querySelectorAll('tr.scroll-anchor.line-auction').length")
                    if cnt > 20:
                        break
                    await asyncio.sleep(1)
                actual = await page.evaluate("() => document.querySelectorAll('tr.scroll-anchor.line-auction').length")
                print(f"  [iauc] Switched to 100 items/page (got {actual} rows on first page)")
            else:
                print(f"  [iauc] Could not find page size selector, using default 15/page")

            # Paginate through results — extract data from list, images from detail in parallel
            batch_ids = []
            page_num = 0
            consecutive_all_existing = 0  # track pages with 0 new vehicles
            # Scale early exit threshold based on batch size:
            # Small batches (<500): exit after 3 all-existing pages (300 vehicles checked)
            # Medium batches (500-5000): exit after 10 pages (1000 vehicles checked)
            # Large batches (5000+): exit after 20 pages (2000 vehicles checked)
            MAX_CONSECUTIVE_EXISTING = 3 if batch_total < 500 else 10 if batch_total < 5000 else 20
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
                if consecutive_all_existing >= MAX_CONSECUTIVE_EXISTING:
                    print(f"  [iauc] P{pass_idx + 1} Batch {batch_num}: {MAX_CONSECUTIVE_EXISTING} consecutive pages with 0 new — skipping rest")
                    break

                # ── Extract ALL vehicle data from the list page in one JS call ──
                raw_vehicles = await page.evaluate("""() => {
                    const results = [];
                    const seen = new Set();
                    const rows = document.querySelectorAll('tr.scroll-anchor.line-auction');

                    for (const row of rows) {
                        const vid = row.getAttribute('data-vid') || '';
                        if (!vid || seen.has(vid)) continue;
                        seen.add(vid);

                        // Get long code (contains auction date) from any data-code attribute
                        let longCode = '';
                        const allCodes = [];
                        row.querySelectorAll('[data-code]').forEach(el => {
                            const c = el.getAttribute('data-code') || '';
                            if (c) allCodes.push(c);
                            if (c.split('-').length > 3 && !longCode) longCode = c;
                        });

                        // Get thumbnail URL
                        const thumbImg = row.querySelector('img.img-car');
                        const thumbUrl = thumbImg ? (thumbImg.src || thumbImg.getAttribute('data-original') || '') : '';

                        // Collect all TDs across this row and next 2 sibling rows (rowspan=3)
                        const cells = {};
                        let tr = row;
                        for (let r = 0; r < 3 && tr; r++) {
                            tr.querySelectorAll('td').forEach(td => {
                                const cls = Array.from(td.classList).find(c => c.startsWith('col'));
                                if (cls) cells[cls] = td.innerText.trim();
                            });
                            tr = tr.nextElementSibling;
                        }

                        results.push({
                            vid,
                            longCode,
                            allCodes,
                            thumbUrl,
                            model_grade: cells['col3'] || '',
                            site: cells['col4'] || '',
                            year: cells['col5'] || '',
                            chassis_cc: cells['col6'] || '',
                            mileage: cells['col7'] || '',
                            color: cells['col8'] || '',
                            shift: cells['col9'] || '',
                            score: cells['col10'] || '',
                            start_price: cells['col11'] || '',
                            result_status: cells['col12'] || '',
                            lot_no: cells['col14'] || '',
                        });
                    }
                    return results;
                }""")

                if not raw_vehicles:
                    break

                # Parse and filter vehicles
                target = get_target_date()
                new_vehicles = []
                skipped = 0
                skipped_date = 0
                no_date_count = 0
                for rv in raw_vehicles:
                    item_id = f"iauc-{rv['vid']}"
                    if item_id in existing_ids:
                        skipped += 1
                        batch_ids.append(item_id)
                        continue

                    vehicle = _parse_list_row(rv)
                    if not vehicle or not vehicle.get("item_id"):
                        continue

                    auction_date_str = vehicle.get("auction_date", "")
                    if not auction_date_str:
                        no_date_count += 1

                    auction_date = normalize_auction_date(auction_date_str, "iauc")
                    if auction_date and auction_date < target:
                        skipped_date += 1
                        continue

                    new_vehicles.append((vehicle, rv['vid']))

                total_on_page = len(raw_vehicles)
                print(f"  [iauc] P{pass_idx + 1} Batch {batch_num} p{page_num}: {total_on_page} on page ({len(new_vehicles)} new, {skipped} existing)")
                if no_date_count:
                    print(f"  [iauc] P{pass_idx + 1} Batch {batch_num} p{page_num}: {no_date_count} vehicles have no list-page date (will get from detail page)")
                if skipped_date:
                    print(f"  [iauc] P{pass_idx + 1} Batch {batch_num} p{page_num}: skipped {skipped_date} past dates")

                # Track consecutive all-existing pages for early exit
                if len(new_vehicles) == 0 and total_on_page > 0:
                    consecutive_all_existing += 1
                else:
                    consecutive_all_existing = 0

                # ── Parallel: open detail pages for 1 exhibit sheet + 2 car photos ──
                if new_vehicles:
                    semaphore = asyncio.Semaphore(CONCURRENT_TABS)

                    known_makers = [
                        "TOYOTA", "LEXUS", "NISSAN", "HONDA", "MAZDA", "MITSUBISHI",
                        "SUBARU", "DAIHATSU", "SUZUKI", "BMW", "MERCEDES-BENZ", "AUDI",
                        "VOLKSWAGEN", "PORSCHE", "ISUZU", "HINO", "VOLVO", "JAGUAR",
                        "FORD", "GM", "CHRYSLER", "ALFA ROMEO", "FIAT", "FERRARI",
                        "MASERATI", "OPEL", "SMART", "ROVER", "BENTLEY", "TESLA",
                        "PEUGEOT", "RENAULT", "CITROEN", "LAMBORGHINI", "BYD",
                    ]

                    async def fetch_images_and_maker(vid: str):
                        """Open detail page: grab maker, model, holding date, 1 exhibit sheet + 2 car photos."""
                        async with semaphore:
                            new_page = await context.new_page()
                            try:
                                detail_url = f"https://www.iauc.co.jp/detail/?vehicleId={vid}&owner_id=&from=vehicle&id=&__tid={tid}"
                                await new_page.goto(detail_url, wait_until="domcontentloaded", timeout=20000)
                                await asyncio.sleep(2)
                                if "detail" not in new_page.url:
                                    return {"car_urls": [], "sheet_url": None, "maker": "", "model": "", "holding_date": ""}

                                # Extract maker, model, holding date from detail page text
                                detail_text = await new_page.inner_text("body")
                                maker = ""
                                detail_model = ""
                                holding_date = ""
                                lines = [l.strip() for l in detail_text.split("\n") if l.strip()]
                                for idx, line in enumerate(lines):
                                    if line in known_makers:
                                        maker = line
                                        # Model is on the next line after maker
                                        if idx + 1 < len(lines):
                                            raw_model = lines[idx + 1].strip()
                                            # Strip chassis code (e.g., "Prius ZVW30-5355115" → "Prius")
                                            detail_model = re.split(r'\s+[A-Z0-9]{3,}-', raw_model)[0].strip()
                                            if not detail_model:
                                                detail_model = raw_model
                                            # Strip standalone chassis codes like "ZVW55" at end
                                            detail_model = re.sub(r'\s+[A-Z]{1,4}\d{2,}$', '', detail_model).strip()
                                    # Tab-separated fields: "Holding Date\tMar 25.2026 10:00"
                                    if "\t" in line:
                                        parts = line.split("\t", 1)
                                        if len(parts) == 2 and parts[0].strip() == "Holding Date":
                                            holding_date = parts[1].strip()

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
                                    base = img['src'].split('?')[0]
                                    if base in seen_urls:
                                        continue
                                    seen_urls.add(base)
                                    fn = img['filename']
                                    if re.match(r'^A\d+\.JPG', fn) or '_scan.' in img['src'].lower():
                                        if not sheet_url:
                                            sheet_url = img['src']
                                    else:
                                        if len(car_urls) < 2:
                                            car_urls.append(img['src'])
                                return {"car_urls": car_urls, "sheet_url": sheet_url, "maker": maker, "model": detail_model, "holding_date": holding_date}
                            except:
                                return {"car_urls": [], "sheet_url": None, "maker": "", "model": "", "holding_date": ""}
                            finally:
                                await new_page.close()

                    img_results = await asyncio.gather(
                        *[fetch_images_and_maker(vid) for _, vid in new_vehicles],
                        return_exceptions=True,
                    )

                    # Collect makers, models, holding dates from detail pages, upload images in parallel
                    maker_by_idx = {}
                    model_by_idx = {}
                    date_by_idx = {}
                    upload_tasks = []
                    upload_map = []
                    for i, img_data in enumerate(img_results):
                        if isinstance(img_data, Exception):
                            img_data = {"car_urls": [], "sheet_url": None, "maker": "", "model": "", "holding_date": ""}
                        if img_data.get("maker"):
                            maker_by_idx[i] = img_data["maker"]
                        if img_data.get("model"):
                            model_by_idx[i] = img_data["model"]
                        if img_data.get("holding_date"):
                            date_by_idx[i] = img_data["holding_date"]
                        for url in img_data.get("car_urls", []):
                            upload_tasks.append(_download_and_upload(page, url))
                            upload_map.append((i, 'car'))
                        if img_data.get("sheet_url"):
                            upload_tasks.append(_download_and_upload(page, img_data["sheet_url"]))
                            upload_map.append((i, 'sheet'))

                    upload_results = await asyncio.gather(*upload_tasks, return_exceptions=True) if upload_tasks else []

                    car_by_idx = {}
                    sheet_by_idx = {}
                    for j, (idx, img_type) in enumerate(upload_map):
                        val = upload_results[j] if not isinstance(upload_results[j], Exception) else None
                        if not val:
                            continue
                        if img_type == 'car':
                            car_by_idx.setdefault(idx, []).append(val)
                        else:
                            sheet_by_idx[idx] = val

                    vehicles_to_save = []
                    for i, (vehicle, vid) in enumerate(new_vehicles):
                        # Set maker from detail page (list page doesn't have it)
                        if maker_by_idx.get(i):
                            vehicle["maker"] = maker_by_idx[i]
                        # Fill in model from detail page if list page had none or empty
                        if not vehicle.get("model") and model_by_idx.get(i):
                            vehicle["model"] = model_by_idx[i]
                        # Fill in auction_date from detail page if list page had none
                        if not vehicle.get("auction_date") and date_by_idx.get(i):
                            vehicle["auction_date"] = date_by_idx[i]
                        car_imgs = car_by_idx.get(i, [])
                        vehicle["images"] = car_imgs
                        vehicle["image_url"] = car_imgs[0] if car_imgs else None
                        vehicle["exhibit_sheet"] = sheet_by_idx.get(i)
                        vehicles_to_save.append(vehicle)

                    if vehicles_to_save:
                        result = upsert_auctions(vehicles_to_save)
                        all_ids.extend(v["item_id"] for v in vehicles_to_save)
                        existing_ids.update(v["item_id"] for v in vehicles_to_save)
                        img_total = sum(len(v.get("images", [])) for v in vehicles_to_save)
                        sheet_total = sum(1 for v in vehicles_to_save if v.get("exhibit_sheet"))
                        print(f"  [iauc] P{pass_idx + 1} Batch {batch_num} p{page_num}: {len(vehicles_to_save)} -> DB (new:{result['new']}, imgs:{img_total}, sheets:{sheet_total})")

                # Track all IDs
                for rv in raw_vehicles:
                    item_id = f"iauc-{rv['vid']}"
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


def _parse_list_row(rv: dict) -> dict | None:
    """Parse vehicle data from iAUC list page row."""
    vid = rv.get("vid", "")
    if not vid:
        return None

    # Extract auction date from long code: XX-XXXX-XXXX-XX-XXXX-YYYYMMDD
    long_code = rv.get("longCode", "")
    auction_date = ""
    if long_code:
        parts = long_code.split("-")
        for part in parts:
            if len(part) == 8 and part.isdigit() and part.startswith("20"):
                auction_date = f"{part[:4]}/{part[4:6]}/{part[6:8]}"
                break

    # Model / Grade from col3 (e.g., "Aerio ／ 1.5 XR\nBid Free")
    model_grade = rv.get("model_grade", "")
    # Remove "Bid Free" and other status lines
    model_grade = "\n".join(l for l in model_grade.split("\n")
                           if l.strip() and l.strip() not in ("Bid Free", "Bid-Closed", "Sold", "Negotiation"))
    model = ""
    grade = ""
    if "／" in model_grade:
        parts = model_grade.split("／", 1)
        model = parts[0].strip()
        grade = parts[1].strip() if len(parts) > 1 else ""
    else:
        model = model_grade.strip()

    # Maker will be set from detail page (fetch_images_and_maker), leave empty here
    maker = ""

    # Year (col5 may have "2016\n " — take first line, extract 4-digit year)
    year_raw = rv.get("year", "").split("\n")[0].strip()
    year = ""
    year_match = re.search(r'(20\d{2}|19\d{2})', year_raw)
    if year_match:
        year = year_match.group(1)

    # Chassis / CC (col6: "RB21S\n1500cc" or "RB21S | 1500cc")
    chassis_cc = rv.get("chassis_cc", "")
    chassis = ""
    cc = ""
    if chassis_cc:
        parts = [p.strip() for p in re.split(r'[\n|]', chassis_cc) if p.strip()]
        for part in parts:
            if re.search(r'\d+cc', part, re.IGNORECASE):
                cc = part
            elif not chassis:
                chassis = part

    # Mileage (col7: " \n30000km" — find the km part)
    mileage_raw = rv.get("mileage", "")
    mileage = ""
    for part in mileage_raw.split("\n"):
        part = part.strip()
        if "km" in part.lower() and part != "0km":
            mileage = part

    # Color (col8: "ﾊﾟｰﾙﾎﾜｲﾄ\n\n34K" — take first line only)
    color_raw = rv.get("color", "")
    color_lines = [l.strip() for l in color_raw.split("\n") if l.strip()]
    color = color_lines[0] if color_lines else ""

    # Score (col10: "3.5\n-  -" or "4.5\nB C" — first line is score, rest is ext/int)
    score_raw = rv.get("score", "")
    score_lines = [l.strip() for l in score_raw.split("\n") if l.strip()]
    score = score_lines[0] if score_lines else ""
    ext_int = ""
    if len(score_lines) > 1:
        ext_int = score_lines[1]
    rating = None
    if score and score not in ("-", "***", "0"):
        rating = f"{score} {ext_int}".strip() if ext_int and ext_int != "-  -" else score

    # Start price (col11: "1,380,000" — in yen, convert to man-yen)
    start_price = None
    price_raw = rv.get("start_price", "").strip().replace(",", "")
    if price_raw and price_raw.isdigit() and int(price_raw) > 0:
        start_price = str(int(price_raw) / 10000)

    # Auction site (col4)
    site = rv.get("site", "").strip()

    # Lot number (col14)
    lot_no = rv.get("lot_no", "").strip()

    return {
        "item_id": f"iauc-{vid}",
        "lot_number": lot_no or None,
        "maker": maker,
        "model": model,
        "grade": grade or None,
        "chassis_code": chassis or None,
        "engine_specs": cc or None,
        "year": year or year_raw,
        "mileage": mileage or None,
        "inspection_expiry": None,
        "color": color or None,
        "rating": rating,
        "start_price": start_price,
        "auction_date": auction_date,
        "auction_house": site or "iAUC",
        "location": site,
        "status": "upcoming",
        "image_url": None,
        "images": [],
        "exhibit_sheet": None,
        "source": "iauc",
    }


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
    """Download image via authenticated browser and upload to R2. Retries once on failure."""
    for attempt in range(2):
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
            if attempt == 0:
                await asyncio.sleep(1)
                continue
            return None
        except:
            if attempt == 0:
                await asyncio.sleep(1)
                continue
            return None
