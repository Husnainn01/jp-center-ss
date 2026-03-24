"""USS/NINJA scraper: maker-by-maker, list-page extraction (no detail clicks).
Scrapes ALL makers, ALL models, ALL vehicles. Japanese brands first.
Splits >1000 models by body type to bypass NINJA's 1000-result limit."""

import asyncio
import base64
import re
import time
from datetime import date as date_type
from playwright.async_api import Page, BrowserContext
from db import upsert_auctions, get_existing_item_ids, normalize_auction_date
from storage import upload_image
from jst import should_scrape_today, get_target_date, now_jst, today_jst

# Japanese makers first, foreign after — ensures JP brands get scraped first
JAPANESE_MAKERS = [
    "TOYOTA", "LEXUS", "NISSAN", "HONDA", "MAZDA", "MITSUBISHI",
    "SUBARU", "DAIHATSU", "SUZUKI", "ISUZU", "EUNOS", "MITSUOKA",
]
FOREIGN_MAKERS = [
    "MERCEDES BENZ", "BMW", "AUDI", "VOLKSWAGEN", "PORSCHE",
    "VOLVO", "MINI", "PEUGEOT", "ALFA ROMEO",
    "CHEVROLET", "CADILLAC", "FORD", "DODGE", "CHRYSLER JEEP",
]
ALL_MAKERS = JAPANESE_MAKERS + FOREIGN_MAKERS

BRAND_CODES = {
    "LEXUS": "00", "TOYOTA": "01", "NISSAN": "04", "HONDA": "06",
    "MAZDA": "10", "MITSUBISHI": "08", "SUBARU": "14", "DAIHATSU": "15",
    "SUZUKI": "16", "ISUZU": "17", "EUNOS": "12", "MITSUOKA": "19",
    "MERCEDES BENZ": "40", "BMW": "44", "AUDI": "46", "VOLKSWAGEN": "47",
    "PORSCHE": "49", "VOLVO": "90", "MINI": "56", "PEUGEOT": "81",
    "ALFA ROMEO": "73", "CHEVROLET": "21", "CADILLAC": "20", "FORD": "29",
    "DODGE": "33", "CHRYSLER JEEP": "32",
}

# No artificial caps — scrape everything
MAX_PAGES_PER_MAKER = 999
MAX_VEHICLES_PER_MAKER = 99999
MAX_TIME_PER_MAKER = 14400  # 4 hours per maker (safety only)


async def _relogin_on_page(page: Page):
    """Re-login on the SAME page (no new page created, reference stays valid)."""
    from db import get_site_credentials
    user_id, password = get_site_credentials("uss")
    if not user_id or not password:
        raise Exception("No USS credentials for re-login")

    await page.goto("https://www.ninja-cartrade.jp/ninja/", wait_until="networkidle", timeout=60000)
    await asyncio.sleep(2)
    await page.fill("#loginId", user_id)
    await page.fill("#password", password)
    await page.evaluate("() => login()")
    await asyncio.sleep(5)
    await page.wait_for_load_state("networkidle", timeout=15000)

    body = await page.inner_text("body")
    if "different user" in body.lower():
        await page.evaluate("""() => {
            for (const a of document.querySelectorAll('a'))
                if (a.textContent.trim() === 'Login') { a.click(); return; }
        }""")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(3)

    if "searchcondition" not in page.url:
        raise Exception(f"Re-login failed, ended up at {page.url[:60]}")
    print(f"  [ninja] Re-login successful")


async def _select_maker(page: Page, brand_code: str, context: BrowserContext | None = None):
    """Navigate to searchcondition then select maker via seniBrand.
    Re-logins on the same page if session is lost (keeps page reference valid)."""

    for attempt in range(3):
        # Step 1: Get to searchcondition page
        try:
            if "searchcondition" not in page.url:
                has_fn = await page.evaluate("() => typeof seniToSearchcondition === 'function'")
                if has_fn:
                    await page.evaluate("() => seniToSearchcondition()")
                    await page.wait_for_load_state("networkidle", timeout=30000)
                    await asyncio.sleep(2)
                else:
                    raise Exception("JS not available")
        except:
            # Session likely dead — re-login on this same page
            try:
                print(f"  [ninja] _select_maker: session lost, re-logging in (attempt {attempt+1}/3)...")
                await _relogin_on_page(page)
            except Exception as e:
                print(f"  [ninja] _select_maker: re-login failed: {e}")
                continue

        # Step 2: Call seniBrand
        try:
            has_brand = await page.evaluate("() => typeof seniBrand === 'function'")
            if not has_brand:
                raise Exception("seniBrand not available")
            await page.evaluate(f"() => seniBrand('{brand_code}')")
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(2)

            # Step 3: Verify we landed on makersearch
            has_model_fn = await page.evaluate("() => typeof makerListChoiceCarCat === 'function'")
            if has_model_fn:
                return page  # Success
            print(f"  [ninja] _select_maker: makerListChoiceCarCat not found, retrying ({attempt+1}/3)")
        except Exception as e:
            print(f"  [ninja] _select_maker: attempt {attempt+1}/3 failed: {e}")
            # Try re-login for next attempt
            try:
                await _relogin_on_page(page)
            except:
                pass

    raise Exception(f"_select_maker failed after 3 attempts for brand_code={brand_code}")



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
    print(f"  [ninja] Mode: scrape ALL vehicles (no caps)")

    existing_ids = get_existing_item_ids("uss")
    print(f"  [ninja] {len(existing_ids)} existing vehicles in DB (will skip)")

    # Scrape order: Japanese makers first, then foreign (defined in ALL_MAKERS)
    print(f"  [ninja] Scrape order (JP first): {', '.join(makers)}")

    for maker in makers:
        print(f"  [ninja] Scraping {maker}...")
        try:
            # Always get the latest page from context (may change after re-login)
            page = context.pages[-1] if context.pages else await context.new_page()
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

    page = await _select_maker(page, brand_code, context)

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
            await asyncio.sleep(3)

            body = await page.inner_text("body")
            if "more than 1,000" not in body.lower() and "1,000items" not in body.lower():
                return await _paginate_results(page, context, maker, existing_ids, maker_start)
        except Exception as e:
            print(f"  [ninja] {maker} allSearch failed: {e}")

    # >1000: search model by model — scrape ALL models (smallest first for fast coverage)
    models.sort(key=lambda m: m["count"])
    print(f"  [ninja] {maker}: searching all {len(models)} models (smallest first)...")

    all_ids = []
    for model in models:
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
    page = await _select_maker(page, brand_code, context)

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
    await asyncio.sleep(3)

    body = await page.inner_text("body")
    if "more than 1,000" not in body.lower() and "1,000items" not in body.lower():
        # Under 1000 — scrape normally
        return await _paginate_results(page, context, maker, existing_ids, maker_start)

    # >1000 results for this model — split by body type to get under the limit
    print(f"  [ninja] {maker} > {model['name']}: >1000, splitting by body type...")

    # Go back to maker page and re-select
    page = await _select_maker(page, brand_code, context)

    # Get available body types
    body_types = await page.evaluate("""() => {
        const types = [];
        document.querySelectorAll('input[name="bodytype"]').forEach(cb => {
            const label = cb.closest('label')?.textContent?.trim() ||
                          cb.parentElement?.textContent?.trim() || '';
            types.push({ value: cb.value, label: label, id: cb.id });
        });
        return types;
    }""")

    sub_ids = []
    for bt in body_types:
        if time.time() - maker_start >= MAX_TIME_PER_MAKER:
            break

        # Re-select maker
        page = await _select_maker(page, brand_code, context)

        # Uncheck all body types, then check only this one
        await page.evaluate("""(btValue) => {
            document.querySelectorAll('input[name="bodytype"]').forEach(cb => {
                if (cb.checked) cb.click();
            });
            document.querySelectorAll('input[name="bodytype"]').forEach(cb => {
                if (cb.value === btValue && !cb.checked) cb.click();
            });
        }""", bt["value"])
        await asyncio.sleep(0.3)

        # Click the model
        await page.evaluate(f"() => makerListChoiceCarCat('{cat_id}')")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(2)

        sub_body = await page.inner_text("body")
        if "more than 1,000" in sub_body.lower() or "1,000items" in sub_body.lower():
            print(f"  [ninja] {maker} > {model['name']} [{bt['label']}]: still >1000, scraping what we can")

        ids = await _paginate_results(page, context, maker, existing_ids, maker_start)
        sub_ids.extend(ids)
        if ids:
            print(f"  [ninja] {maker} > {model['name']} [{bt['label']}]: {len(ids)} vehicles")

    return sub_ids


async def _paginate_results(page: Page, context: BrowserContext, maker: str, existing_ids: set, maker_start: float) -> list[str]:
    """Paginate through results, extracting data directly from the list page.
    No detail page clicks needed — all fields + thumbnail extracted in one JS call per page."""
    all_ids = []
    page_num = 0

    # Switch to 100 items per page for fewer page loads
    await page.evaluate("""() => {
        const links = document.querySelectorAll('a');
        for (const a of links) {
            if (a.textContent.trim() === '100' && a.getAttribute('onclick')
                && a.getAttribute('onclick').includes('changeDisp')) {
                a.click(); return true;
            }
        }
        return false;
    }""")
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except:
        pass
    await asyncio.sleep(2)

    while page_num < MAX_PAGES_PER_MAKER:
        # Check time and vehicle limits
        if time.time() - maker_start >= MAX_TIME_PER_MAKER:
            print(f"  [ninja] {maker}: time limit reached, stopping pagination")
            break
        if len(all_ids) >= MAX_VEHICLES_PER_MAKER:
            print(f"  [ninja] {maker}: vehicle limit reached ({len(all_ids)}/{MAX_VEHICLES_PER_MAKER}), stopping pagination")
            break

        page_num += 1

        # Extract ALL vehicle data from the list page in a single JS call
        raw_vehicles = await page.evaluate("""() => {
            const results = [];
            const rows = document.querySelectorAll('tr');
            const seen = new Set();

            for (const row of rows) {
                // Find seniCarDetail onclick in this row
                const detailLink = row.querySelector('[onclick*=seniCarDetail]');
                if (!detailLink) continue;

                const onclick = detailLink.getAttribute('onclick') || '';
                const match = onclick.match(/seniCarDetail\\('(\\d+)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)'/);
                if (!match) continue;

                const bidNo = match[4];
                if (seen.has(bidNo)) continue;
                seen.add(bidNo);

                // Get all td cells text
                const cells = Array.from(row.querySelectorAll('td')).map(td => td.innerText.trim());

                // Get thumbnail image URL
                const img = row.querySelector('img[src*=get_car_image], img[src*=get_image]');
                const imgSrc = img ? img.src : '';

                // Get carKeyStr hidden input for image path
                const keyInput = row.querySelector('input[name^=carKeyStr]');
                const keyVal = keyInput ? keyInput.value : '';

                results.push({
                    index: match[1],
                    site: match[2],
                    times: match[3],
                    bidNo: bidNo,
                    cells: cells,
                    imgSrc: imgSrc,
                    keyVal: keyVal,
                });
            }
            return results;
        }""")

        if not raw_vehicles:
            break

        # Skip existing
        target = get_target_date()
        new_vehicles = []
        skipped = 0
        skipped_date = 0
        for rv in raw_vehicles:
            item_id = f"uss-{rv['bidNo']}-{rv['times']}"
            if item_id in existing_ids:
                skipped += 1
                all_ids.append(item_id)
                continue

            # Parse vehicle data from cells
            vehicle = _parse_list_row(rv, maker)
            if not vehicle or not vehicle.get("item_id"):
                continue

            # Filter by target date
            auction_date_str = vehicle.get("auction_date", "")
            auction_date = normalize_auction_date(auction_date_str, "uss")
            if auction_date and auction_date < target:
                skipped_date += 1
                continue

            new_vehicles.append((vehicle, rv.get("imgSrc", "")))

        print(f"  [ninja] {maker} p{page_num}: {len(raw_vehicles)} vehicles ({skipped} existing, {len(new_vehicles)} new)")

        if skipped_date:
            print(f"  [ninja] {maker} p{page_num}: skipped {skipped_date} vehicles with past auction dates")

        # Fetch exhibit sheets via new-tab form submission + upload thumbnails
        if new_vehicles:
            # Step 1: Get exhibit sheet URLs by submitting form1 to new tabs
            sheet_urls = {}
            sheet_errors = 0
            for vehicle, _ in new_vehicles:
                # Stop fetching sheets if main page is broken (avoid cascade)
                if sheet_errors >= 2:
                    break
                rv_match = next((rv for rv in raw_vehicles if rv['bidNo'] == vehicle['lot_number']), None)
                if not rv_match:
                    continue
                try:
                    # Check form1 still exists on main page before submitting
                    has_form = await page.evaluate("() => !!document.getElementById('form1')")
                    if not has_form:
                        print(f"  [ninja] {maker} p{page_num}: form1 lost, stopping sheet fetch")
                        break

                    new_page_promise = context.wait_for_event("page", timeout=10000)
                    await page.evaluate("""(v) => {
                        document.getElementById('carKindType').value = '1';
                        document.getElementById('kaijoCode').value = v.site;
                        document.getElementById('auctionCount').value = v.times;
                        document.getElementById('bidNo').value = v.bidNo;
                        document.getElementById('zaikoNo').value = '';
                        document.getElementById('action').value = 'init';
                        var form = document.getElementById('form1');
                        form.setAttribute('action', './cardetail.action');
                        form.setAttribute('target', '_blank');
                        form.submit();
                    }""", rv_match)
                    detail_page = await new_page_promise
                    await detail_page.wait_for_load_state("networkidle", timeout=10000)
                    await asyncio.sleep(0.5)

                    sheet_url = await detail_page.evaluate("""() => {
                        for (const img of document.querySelectorAll('img')) {
                            if (img.src && img.src.includes('get_ex_image')) return img.src;
                        }
                        return '';
                    }""")
                    if sheet_url:
                        sheet_urls[vehicle['item_id']] = sheet_url
                    await detail_page.close()
                    sheet_errors = 0  # Reset on success
                except Exception as e:
                    sheet_errors += 1
                    # Close any extra pages that may have opened
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

            if sheet_urls:
                print(f"  [ninja] {maker} p{page_num}: found {len(sheet_urls)} exhibit sheets")

            # Step 2: Upload thumbnails + exhibit sheets in parallel
            async def upload_one(url):
                if not url:
                    return None
                return await _download_and_upload(page, url, "ninja-images")

            # Build upload tasks: thumbnail + sheet for each vehicle
            upload_tasks = []
            task_map = []  # track which task belongs to which vehicle
            for i, (vehicle, img_url) in enumerate(new_vehicles):
                upload_tasks.append(upload_one(img_url))
                task_map.append(('thumb', i))
                sheet_url = sheet_urls.get(vehicle['item_id'], '')
                upload_tasks.append(upload_one(sheet_url))
                task_map.append(('sheet', i))

            upload_results = await asyncio.gather(*upload_tasks, return_exceptions=True)

            vehicles_to_save = []
            for i, (vehicle, _) in enumerate(new_vehicles):
                thumb_idx = i * 2
                sheet_idx = i * 2 + 1
                thumb = upload_results[thumb_idx] if not isinstance(upload_results[thumb_idx], Exception) else None
                sheet = upload_results[sheet_idx] if not isinstance(upload_results[sheet_idx], Exception) else None
                vehicle["images"] = [thumb] if thumb else []
                vehicle["image_url"] = thumb
                vehicle["exhibit_sheet"] = sheet
                vehicles_to_save.append(vehicle)

            if vehicles_to_save:
                result = upsert_auctions(vehicles_to_save)
                all_ids.extend(v["item_id"] for v in vehicles_to_save)
                existing_ids.update(v["item_id"] for v in vehicles_to_save)
                img_total = sum(len(v.get("images", [])) for v in vehicles_to_save)
                sheet_total = sum(1 for v in vehicles_to_save if v.get("exhibit_sheet"))
                print(f"  [ninja] {maker} p{page_num}: {len(vehicles_to_save)} → DB (new:{result['new']}, imgs:{img_total}, sheets:{sheet_total})")

        # Next page
        has_next = await page.evaluate("""() => {
            for (const a of document.querySelectorAll('a'))
                if (a.textContent.trim().includes('Next page')) { a.click(); return true; }
            return false;
        }""")
        if not has_next:
            break
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(2)

    if page_num >= MAX_PAGES_PER_MAKER:
        print(f"  [ninja] {maker}: reached page limit ({MAX_PAGES_PER_MAKER}), moving to next maker")

    return all_ids


def _parse_list_row(rv: dict, maker: str) -> dict | None:
    """Parse vehicle data from NINJA list page row cells.
    Cell layout: [0] checkbox [1] image [2] site/date/lot [3] maker/model/chassis [4] year [5] trans/cc [6] mileage [7] score [8] price/status"""
    cells = rv.get("cells", [])
    if len(cells) < 8:
        return None

    # Cell 2: site, date, lot number
    cell2_lines = [l.strip() for l in cells[2].split("\n") if l.strip()]
    site_name = cell2_lines[0] if cell2_lines else ""
    auction_date = ""
    lot_no = rv["bidNo"]
    for line in cell2_lines:
        date_match = re.search(r'(\d{4}/\d{2}/\d{2})', line)
        if date_match:
            auction_date = date_match.group(1)
        no_match = re.search(r'No\.(\d+)', line)
        if no_match:
            lot_no = no_match.group(1)

    # Cell 3: maker, model, grade, chassis
    cell3_lines = [l.strip() for l in cells[3].split("\n") if l.strip()]
    model = ""
    grade = ""
    chassis = ""
    for line in cell3_lines:
        if line == maker:
            continue
        if not model:
            # First non-maker line is model + grade
            parts = line.split()
            model = parts[0] if parts else line
            grade = " ".join(parts[1:]) if len(parts) > 1 else ""
        else:
            # Next line is chassis code (full-width chars)
            chassis = line

    # Cell 4: year
    year = cells[4].strip() if len(cells) > 4 else ""

    # Cell 5: transmission + cc
    cell5_lines = [l.strip() for l in cells[5].split("\n") if l.strip()]
    cc = ""
    for line in cell5_lines:
        cc_match = re.search(r'([\d,]+)\s*cc', line, re.IGNORECASE)
        if cc_match:
            cc = cc_match.group(0)

    # Cell 6: mileage
    mileage = cells[6].strip() if len(cells) > 6 else ""

    # Cell 7: score
    score = cells[7].strip() if len(cells) > 7 else ""

    # Cell 8: price + status
    start_price = None
    if len(cells) > 8:
        price_match = re.search(r'JPY\s*([\d,]+)', cells[8])
        if price_match:
            price_raw = price_match.group(1).replace(",", "")
            try:
                start_price = str(int(price_raw) / 10000)
            except ValueError:
                pass

    item_id = f"uss-{rv['bidNo']}-{auction_date.replace('/', '') if auction_date else rv['times']}"

    return {
        "item_id": item_id,
        "lot_number": lot_no,
        "maker": maker,
        "model": model,
        "grade": grade or None,
        "chassis_code": chassis or None,
        "engine_specs": cc or None,
        "year": year or None,
        "mileage": mileage or None,
        "inspection_expiry": None,
        "color": None,
        "rating": score if score != "***" else None,
        "start_price": start_price,
        "auction_date": auction_date,
        "auction_house": f"USS {site_name}".strip(),
        "location": site_name or "USS",
        "status": "upcoming",
        "image_url": None,
        "images": [],
        "exhibit_sheet": None,
        "source": "uss",
    }



async def _download_and_upload(page: Page, url: str, prefix: str) -> str | None:
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
                    return upload_image(img_bytes, prefix, url)
            if attempt == 0:
                await asyncio.sleep(1)
                continue
            return None
        except:
            if attempt == 0:
                await asyncio.sleep(1)
                continue
            return None
