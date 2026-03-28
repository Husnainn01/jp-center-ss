"""Minimal iAUC scraper test — login, select, scrape 1 small batch (1 page only).
Reports: how many vehicles found, date distribution, data quality.
No DB needed — reads only from iAUC website.

Run: cd scraper && python3 test_scraper_check.py
"""

import asyncio
import os
import re
from collections import Counter
from datetime import date
from dotenv import load_dotenv
load_dotenv()

from playwright.async_api import async_playwright
from iauc_login import iauc_login, iauc_logout
from jst import now_jst, get_target_date, today_jst

MONTH_MAP = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
             "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}


def parse_date(long_code: str, result_status: str):
    """Parse date from longCode first, then fallback to result_status column."""
    # Try longCode: XX-XXXX-XXXX-XX-XXXX-YYYYMMDD
    if long_code:
        parts = long_code.split("-")
        for part in parts:
            if len(part) == 8 and part.isdigit() and part.startswith("20"):
                try:
                    return date(int(part[:4]), int(part[4:6]), int(part[6:8]))
                except:
                    pass

    # Fallback: result_status "Apr 01\n00:00"
    if result_status:
        date_line = result_status.split("\n")[0].strip()
        m = re.match(r'([A-Za-z]{3})\s+(\d{1,2})', date_line)
        if m:
            month_num = MONTH_MAP.get(m.group(1).lower())
            day_num = int(m.group(2))
            if month_num and 1 <= day_num <= 31:
                year_num = now_jst().year
                if month_num < now_jst().month - 6:
                    year_num += 1
                try:
                    return date(year_num, month_num, day_num)
                except:
                    pass
    return None


async def main():
    user_id = os.getenv("IAUC_USER_ID", "")
    password = os.getenv("IAUC_PASSWORD", "")
    if not user_id or not password:
        print("Set IAUC_USER_ID and IAUC_PASSWORD in .env")
        return

    jst_now = now_jst()
    target = get_target_date()
    today = today_jst()
    print(f"JST time: {jst_now.strftime('%Y-%m-%d %H:%M')}")
    print(f"Today JST: {today}")
    print(f"Target (tomorrow): {target}")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        # === LOGIN ===
        print("Logging in...")
        ok = await iauc_login(page, user_id, password)
        if not ok:
            print("LOGIN FAILED!")
            await browser.close()
            return
        print("Logged in!\n")

        # === Select auction sites (same as real scraper) ===
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="e[]"]:checked').forEach(cb => cb.click());
            document.querySelectorAll('input[name="d[]"]:checked').forEach(cb => cb.click());
        }""")
        await asyncio.sleep(1)

        await page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('a.title-button.checkbox_on_all'));
            for (const b of btns) {
                if (!b.classList.contains('title-green-button')) { b.click(); return; }
            }
        }""")
        await asyncio.sleep(1)

        await page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('a.day-button4g, button.day-button4g'));
            for (const b of btns) {
                if (b.textContent.trim().toUpperCase() === 'TODAY' && b.offsetParent !== null) {
                    b.click(); return;
                }
            }
        }""")
        await asyncio.sleep(1)

        selected = await page.evaluate("""() => ({
            eChecked: document.querySelectorAll('input[name="e[]"]:checked').length,
            dChecked: document.querySelectorAll('input[name="d[]"]:checked').length,
        })""")
        print(f"Auction sites selected: {selected['dChecked']}")

        if selected['dChecked'] == 0:
            print("NO auction sites selected!")
            await browser.close()
            return

        # === Go to Make & Model ===
        print("Navigating to Make & Model...")
        await page.evaluate('() => check_sites(document.querySelector(".page-next-button"))')
        for _ in range(20):
            await asyncio.sleep(2)
            if "#maker" in page.url or "search" in page.url:
                break
        await asyncio.sleep(3)

        if "#maker" not in page.url and "search" not in page.url:
            print(f"Failed! URL: {page.url}")
            await browser.close()
            return

        # === Select ALL makers ===
        await page.evaluate("""() => {
            const allBtns = Array.from(document.querySelectorAll('button'))
                .filter(b => b.textContent.trim() === 'All' && b.offsetParent !== null);
            allBtns.forEach(b => b.click());
        }""")
        await asyncio.sleep(2)

        makers_checked = await page.evaluate('() => document.querySelectorAll(\'input[name="maker[]"]:checked\').length')
        print(f"Makers selected: {makers_checked}")

        # === Get model counts ===
        models = await page.evaluate("""() => {
            const items = [];
            document.querySelectorAll('input[name="type[]"]').forEach((inp, idx) => {
                const name = inp.getAttribute('data-name') || '';
                const cnt = parseInt(inp.getAttribute('data-cnt') || '0');
                if (cnt > 0) items.push({ name, cnt, idx });
            });
            items.sort((a, b) => b.cnt - a.cnt);
            return items;
        }""")

        total_cars = sum(m['cnt'] for m in models)
        print(f"Total future vehicles on iAUC: {total_cars}\n")

        # === Pick test batch (smallest 5 models) ===
        test_batch = models[-5:]
        test_total = sum(m['cnt'] for m in test_batch)
        print(f"TEST: {len(test_batch)} smallest models (~{test_total} vehicles)")
        print(f"Models: {[m['name'] for m in test_batch]}\n")

        await page.evaluate("""() => {
            document.querySelectorAll('input[name="type[]"]:checked').forEach(inp => inp.click());
        }""")
        await asyncio.sleep(0.5)

        batch_indices = [m['idx'] for m in test_batch]
        await page.evaluate("""(indices) => {
            const inputs = document.querySelectorAll('input[name="type[]"]');
            indices.forEach(idx => { if (inputs[idx] && !inputs[idx].checked) inputs[idx].click(); });
        }""", batch_indices)
        await asyncio.sleep(1)

        await page.evaluate('() => { var b = document.querySelector("#next-bottom"); if (b) { b.disabled = false; b.click(); } }')
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass
        await asyncio.sleep(4)

        for _ in range(10):
            cnt = await page.evaluate("() => document.querySelectorAll('tr.scroll-anchor.line-auction').length")
            if cnt > 0:
                break
            await asyncio.sleep(1)

        # === Read list page ===
        raw_vehicles = await page.evaluate("""() => {
            const results = [];
            const seen = new Set();
            const rows = document.querySelectorAll('tr.scroll-anchor.line-auction');
            for (const row of rows) {
                const vid = row.getAttribute('data-vid') || '';
                if (!vid || seen.has(vid)) continue;
                seen.add(vid);
                let longCode = '';
                row.querySelectorAll('[data-code]').forEach(el => {
                    const c = el.getAttribute('data-code') || '';
                    if (c.split('-').length > 3 && !longCode) longCode = c;
                });
                const thumbImg = row.querySelector('img.img-car');
                const thumbUrl = thumbImg ? (thumbImg.src || '') : '';
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
                    vid, longCode, thumbUrl,
                    model_grade: cells['col3'] || '',
                    site: cells['col4'] || '',
                    year: cells['col5'] || '',
                    result_status: cells['col12'] || '',
                    start_price: cells['col11'] || '',
                    mileage: cells['col7'] || '',
                    score: cells['col10'] || '',
                });
            }
            return results;
        }""")

        print(f"Vehicles found: {len(raw_vehicles)}\n")

        if not raw_vehicles:
            print("No vehicles found!")
            await iauc_logout(page)
            await browser.close()
            return

        # === Analyze with BOTH date sources ===
        date_counts = Counter()
        date_source = Counter()
        no_date = 0
        past_date = 0
        placeholder_thumbs = 0

        PLACEHOLDER_PATTERNS = ["now_printing", "noimage", "no_image", "dummy", "blank", "placeholder"]

        for rv in raw_vehicles:
            # Date parsing (longCode + fallback)
            parsed = parse_date(rv.get("longCode", ""), rv.get("result_status", ""))
            if parsed:
                date_counts[str(parsed)] += 1
                if parsed < target:
                    past_date += 1
                # Track which source gave us the date
                long_code = rv.get("longCode", "")
                has_lc_date = False
                if long_code:
                    for part in long_code.split("-"):
                        if len(part) == 8 and part.isdigit() and part.startswith("20"):
                            has_lc_date = True
                            break
                date_source["longCode" if has_lc_date else "result_status (fallback)"] += 1
            else:
                no_date += 1

            # Check for placeholder thumbnails
            thumb = rv.get("thumbUrl", "").lower()
            if thumb and any(p in thumb for p in PLACEHOLDER_PATTERNS):
                placeholder_thumbs += 1

        total = len(raw_vehicles)

        print(f"--- Date Distribution ---")
        for date_str in sorted(date_counts.keys()):
            marker = ""
            if date_str == str(today):
                marker = " << TODAY"
            elif date_str == str(target):
                marker = " << TOMORROW (target)"
            print(f"  {date_str}: {date_counts[date_str]} vehicles{marker}")
        if no_date:
            print(f"  (no date): {no_date}")
        if past_date:
            print(f"  WARN: {past_date} have past dates")

        print(f"\n--- Date Source ---")
        for src, count in date_source.most_common():
            print(f"  {src}: {count}")

        print(f"\n--- Image Check ---")
        print(f"  Placeholder thumbnails (Now Printing): {placeholder_thumbs}/{total}")
        thumb_urls = set()
        for rv in raw_vehicles:
            if rv.get("thumbUrl"):
                thumb_urls.add(rv["thumbUrl"])
        print(f"  Sample thumbnail URLs:")
        for url in list(thumb_urls)[:3]:
            is_placeholder = any(p in url.lower() for p in PLACEHOLDER_PATTERNS)
            print(f"    {'[PLACEHOLDER] ' if is_placeholder else ''}{url[:100]}")

        # === Open 1 detail page to check images ===
        print(f"\n--- Detail Page Image Check (1 vehicle) ---")
        test_vid = raw_vehicles[0]['vid']
        tid = await page.evaluate("""() => {
            for (const a of document.querySelectorAll('a[href*="__tid"]')) {
                const m = a.href.match(/__tid=([^&#]+)/);
                if (m) return m[1];
            }
            return '';
        }""")

        if tid:
            detail_page = await context.new_page()
            detail_url = f"https://www.iauc.co.jp/detail/?vehicleId={test_vid}&owner_id=&from=vehicle&id=&__tid={tid}"
            await detail_page.goto(detail_url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(3)

            all_imgs = await detail_page.evaluate("""() => {
                const placeholders = ['now_printing', 'noimage', 'no_image', 'dummy', 'blank', 'placeholder'];
                return Array.from(document.querySelectorAll('img'))
                    .filter(i => i.src && i.src.includes('iauc_pic'))
                    .map(i => ({
                        src: i.src,
                        width: i.naturalWidth,
                        height: i.naturalHeight,
                        isPlaceholder: placeholders.some(p => i.src.toLowerCase().includes(p)),
                    }));
            }""")

            print(f"  VID: {test_vid}")
            print(f"  Detail page images with 'iauc_pic': {len(all_imgs)}")
            for img in all_imgs:
                status = "[PLACEHOLDER - SKIP]" if img['isPlaceholder'] else f"[{img['width']}x{img['height']}]"
                print(f"    {status} {img['src'][:100]}")

            await detail_page.close()
        else:
            print("  Could not get __tid for detail page test")

        print(f"\n{'='*60}")
        print(f"SUMMARY")
        print(f"  Total future vehicles on iAUC: {total_cars}")
        print(f"  Test batch found: {total}")
        print(f"  Dates from longCode: {date_source.get('longCode', 0)}")
        print(f"  Dates from fallback (result_status): {date_source.get('result_status (fallback)', 0)}")
        print(f"  No date at all: {no_date}")
        print(f"  Placeholder thumbnails: {placeholder_thumbs}")
        print(f"{'='*60}")

        await iauc_logout(page)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
