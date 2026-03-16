"""Scraper: extracts all vehicle data with chunk-based pagination.
- 100 items/page
- Saves each chunk to DB immediately (crash-safe)
- Captures ALL images per vehicle (front, side, rear + exhibit sheet)
- High-res URLs (/tvaa/3/ instead of /tvaa/1/)
"""

import asyncio
from playwright.async_api import Page
from db import upsert_auctions

EXTRACT_JS = """() => {
    const list = document.getElementById('results_list');
    if (!list) return [];

    return Array.from(list.querySelectorAll('li[data-item_id]')).map(li => {
        const get = (sel) => {
            const el = li.querySelector(sel);
            return el ? el.textContent.trim() : null;
        };
        const getAll = (sel) => Array.from(li.querySelectorAll(sel)).map(e => e.textContent.trim());

        const col4 = getAll('.col_4 .ellipsis');
        const col5 = getAll('.col_5 .ellipsis');
        const col6 = getAll('.col_6 .ellipsis');
        const col7 = getAll('.col_7 .ellipsis');
        const col8 = getAll('.col_8 .ellipsis');
        const col9 = getAll('.col_9 .ellipsis');

        const makeModel = col5[0] || '';
        const parts = makeModel.split(/\\u3000|\\s+/);
        const maker = parts[0] || '';
        const model = parts.slice(1).join(' ') || '';

        const rating = col8[1] || null;
        const priceStr = col9.find(t => /^[\\d.]+$/.test(t));
        const statusText = col9.find(t => t.includes('セリ') || t.includes('落札') || t.includes('流れ')) || '';
        const status = statusText.includes('落札') ? 'sold' : 'upcoming';

        // === ALL IMAGES — generate full set from URL pattern ===
        // Two URL patterns exist:
        //   tvaa:  /tvaa/3/{folder}/{vehicleId}{nn}.jpg  (nn = 01-30)
        //   stock: /stock/3/{year}/{vehicleId}_{nn}.jpg  (nn = 01-25)
        // The list view only shows 3 images, but we can generate all from the base.

        let carImages = [];
        const mainImg = li.querySelector('.prod_img img');
        if (mainImg && mainImg.src && mainImg.src.includes('aucnetcars.com')) {
            const src = mainImg.src.replace('/tvaa/1/', '/tvaa/3/').replace('/stock/1/', '/stock/3/');

            if (src.includes('/tvaa/')) {
                // Pattern: .../{vehicleId}03.jpg → base is vehicleId (without last 2 digits)
                const match = src.match(/^(.*\\/)(\\d+?)(\\d{2})\\.jpg$/);
                if (match) {
                    const base = match[1] + match[2];
                    for (let i = 1; i <= 30; i++) {
                        carImages.push(base + String(i).padStart(2, '0') + '.jpg');
                    }
                }
            } else if (src.includes('/stock/')) {
                // Pattern: .../{vehicleId}_03.jpg → base is vehicleId
                const match = src.match(/^(.*\\/)([^_]+)_\\d{2}\\.jpg$/);
                if (match) {
                    const base = match[1] + match[2];
                    for (let i = 1; i <= 25; i++) {
                        carImages.push(base + '_' + String(i).padStart(2, '0') + '.jpg');
                    }
                }
            }

            // Fallback: if pattern didn't match, just collect what we have
            if (carImages.length === 0) {
                const seen = new Set();
                li.querySelectorAll('img').forEach(img => {
                    if (img.src && img.src.includes('aucnetcars.com') && !seen.has(img.src)) {
                        seen.add(img.src);
                        carImages.push(img.src.replace('/tvaa/1/', '/tvaa/3/').replace('/stock/1/', '/stock/3/'));
                    }
                });
            }
        }

        // Exhibit sheet
        const sheet = li.querySelector('.exhibit_sheet_img');
        const exhibitSheet = sheet ? sheet.getAttribute('data-expand-img') : null;

        return {
            item_id: li.getAttribute('data-item_id'),
            lot_number: get('.col_3 div:nth-child(2) .ellipsis') || '',
            maker, model,
            grade: col5[1] || null,
            chassis_code: col6[0] || null,
            engine_specs: col6[1] || null,
            year: col4[0] || null,
            mileage: col7[0] || null,
            inspection_expiry: col7[1] || null,
            color: col8[0] || null,
            rating,
            start_price: priceStr || null,
            auction_date: get('.col_2 div:nth-child(1) .ellipsis') || '',
            auction_house: get('.col_3 div:nth-child(1) .ellipsis') || '',
            location: get('.col_2 div:nth-child(2) .ellipsis') || '',
            status,
            image_url: carImages[0] || null,
            images: carImages,
            exhibit_sheet: exhibitSheet,
        };
    });
}"""


async def search_and_extract_all(page: Page, buy_href: str) -> list[dict]:
    """Chunk-based scraper: extracts page, saves to DB, moves to next."""

    await page.goto(buy_href, wait_until="networkidle", timeout=60000)
    await asyncio.sleep(8)

    # Uncheck all Aucnet special auction types (TV Auction, GOOD VALUE, Shared Inventory, etc.)
    await page.evaluate("""() => {
        const skipCheckboxes = [
            'chk_sel_tvaa',              // TV Auction
            'chk_sel_good_value',        // GOOD VALUE
            'chk_sel_rcmnd',             // SAKIDORI / Assessment Direct
            'chk_sel_wlsale_exhibit_all',// Shared Inventory (ALL)
            'chk_sel_sel_strike_display',// Ichigeki
            'chk_sel_estmate',           // Inspected
            'chk_sel_preliminary_inspection', // Pre-inspection
        ];
        skipCheckboxes.forEach(name => {
            const cb = document.querySelector('input[name="' + name + '"]');
            if (cb && cb.checked) cb.click();
        });
    }""")
    await asyncio.sleep(1)

    # Select all days (Mon-Sat venue auctions)
    await page.evaluate("""() => {
        document.querySelectorAll('.chk_select_all_in_day').forEach(cb => {
            if (!cb.checked) cb.click();
        });
    }""")
    await asyncio.sleep(1)

    # Select all makers
    await page.evaluate("() => document.querySelectorAll('.chk_makers').forEach(c => { if(!c.checked) c.click(); })")
    await asyncio.sleep(0.5)

    # Click search
    await page.evaluate("""() => {
        for (const a of document.querySelectorAll('a'))
            if (a.textContent.includes('この条件で一覧表示')) { a.click(); return; }
    }""")

    # Wait for first results
    if not await _wait_for_results(page, 60):
        print("  [scraper] No results loaded")
        return []

    # Set 100/page
    try:
        await page.select_option(".selDisplayedItems", "100")
        for _ in range(15):
            await asyncio.sleep(1)
            n = await page.evaluate("() => document.querySelectorAll('#results_list li[data-item_id]').length")
            if n > 50:
                break
        await asyncio.sleep(2)
    except Exception as e:
        print(f"  [scraper] 100/page failed: {e}")

    current_count = await page.evaluate("() => document.querySelectorAll('#results_list li[data-item_id]').length")
    total = await page.evaluate("() => { const m = document.body.innerText.match(/(\\d+)台/); return m ? parseInt(m[1]) : 0; }")
    print(f"  [scraper] {total} vehicles, {current_count}/page")

    # === CHUNK-BASED EXTRACTION ===
    all_ids = set()
    total_new = 0
    total_updated = 0
    page_num = 0

    while True:
        page_num += 1

        # Extract this page
        vehicles = await page.evaluate(EXTRACT_JS)
        if not vehicles:
            break

        # Deduplicate
        chunk = [v for v in vehicles if v["item_id"] and v["item_id"] not in all_ids]
        for v in chunk:
            all_ids.add(v["item_id"])

        if chunk:
            # Save chunk to DB immediately
            result = upsert_auctions(chunk)
            total_new += result["new"]
            total_updated += result["updated"]

        pct = (len(all_ids) / total * 100) if total else 0
        img_count = sum(len(v.get("images", [])) for v in chunk)
        print(f"  [scraper] Page {page_num}: +{len(chunk)} vehicles, {img_count} images → DB (new:{result['new']}) | {len(all_ids)}/{total} ({pct:.1f}%)")

        if len(all_ids) >= total:
            break

        # Next page
        has_next = await page.evaluate("""() => {
            const btns = document.querySelectorAll('a.btnNext');
            for (const b of btns) {
                if (!b.classList.contains('disabled') && b.offsetParent !== null) {
                    b.click();
                    return true;
                }
            }
            return false;
        }""")

        if not has_next:
            print("  [scraper] No next button")
            break

        if not await _wait_for_page_change(page, all_ids, 25):
            print("  [scraper] Page didn't change, stopping")
            break

    print(f"  [scraper] Complete: {len(all_ids)} vehicles, {total_new} new, {total_updated} updated")
    return list(all_ids)  # Return IDs for expire tracking


async def _wait_for_results(page: Page, timeout: int = 30) -> bool:
    for _ in range(timeout):
        n = await page.evaluate("() => document.querySelectorAll('#results_list li[data-item_id]').length")
        if n > 0:
            return True
        await asyncio.sleep(1)
    return False


async def _wait_for_page_change(page: Page, seen_ids: set, timeout: int = 20) -> bool:
    for _ in range(timeout):
        await asyncio.sleep(1)
        ids = await page.evaluate("""() =>
            Array.from(document.querySelectorAll('#results_list li[data-item_id]'))
                .slice(0, 5).map(li => li.getAttribute('data-item_id'))
        """)
        if ids and any(fid not in seen_ids for fid in ids if fid):
            return True
    return False
