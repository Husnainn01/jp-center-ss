"""Comprehensive Ninja test:
1. How many vehicles are we getting vs what's available?
2. What's the best sheet fetching strategy with re-login?
3. Are we missing any data?

Run: cd scraper && python3 test_ninja_comprehensive.py
"""
import asyncio
import time
from playwright.async_api import async_playwright


async def do_login(page):
    """Login and return to search condition page. Returns True on success."""
    await page.goto("https://www.ninja-cartrade.jp/ninja/", wait_until="networkidle", timeout=60000)
    await asyncio.sleep(2)
    await page.fill("#loginId", "L4013V80")
    await page.fill("#password", "93493493")
    await page.evaluate("() => login()")
    await asyncio.sleep(5)
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except:
        pass
    body = await page.inner_text("body")
    if "different user" in body.lower():
        await page.evaluate("""() => { for (const a of document.querySelectorAll('a')) if (a.textContent.trim() === 'Login') { a.click(); return; } }""")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(3)
    return "searchcondition" in page.url


async def re_login_on_page(page):
    """Re-login without navigating away — preserves search state."""
    await page.goto("https://www.ninja-cartrade.jp/ninja/", wait_until="networkidle", timeout=30000)
    await asyncio.sleep(2)
    body = await page.inner_text("body")
    if "loginId" in await page.content():
        await page.fill("#loginId", "L4013V80")
        await page.fill("#password", "93493493")
        await page.evaluate("() => login()")
        await asyncio.sleep(5)
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass
        body = await page.inner_text("body")
        if "different user" in body.lower():
            await page.evaluate("""() => { for (const a of document.querySelectorAll('a')) if (a.textContent.trim() === 'Login') { a.click(); return; } }""")
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(3)
    return "searchcondition" in page.url


async def fetch_sheet_iframe(page, v):
    """Fetch exhibit sheet via iframe. Returns sheet URL or empty string."""
    result = await page.evaluate("""(v) => {
        return new Promise((resolve) => {
            let f = document.getElementById('_sf');
            if (!f) {
                f = document.createElement('iframe');
                f.id = '_sf'; f.name = '_sf';
                f.style.cssText = 'position:absolute;left:-9999px;width:800px;height:600px';
                document.body.appendChild(f);
            }
            f.onload = function() {
                setTimeout(() => {
                    try {
                        const doc = f.contentDocument;
                        const html = doc.documentElement.innerHTML;
                        const loggedOut = doc.body.innerText.includes('logged out');
                        let sheet = '';
                        if (!loggedOut) {
                            doc.querySelectorAll('img').forEach(img => {
                                if (img.src.includes('get_ex_image')) sheet = img.src;
                            });
                            if (!sheet) {
                                const m = html.match(/action=get_ex_image&amp;FilePath=([^"&]*)/);
                                if (m) sheet = './cardetail.action?action=get_ex_image&FilePath=' + m[1];
                            }
                        }
                        resolve({ sheet, loggedOut, htmlLen: html.length });
                    } catch(e) { resolve({ error: e.message, loggedOut: false }); }
                }, 1500);
            };
            document.getElementById('carKindType').value = '1';
            document.getElementById('kaijoCode').value = v.site;
            document.getElementById('auctionCount').value = v.times;
            document.getElementById('bidNo').value = v.bidNo;
            document.getElementById('zaikoNo').value = '';
            document.getElementById('action').value = 'init';
            var form = document.getElementById('form1');
            form.setAttribute('action', './cardetail.action');
            form.setAttribute('target', '_sf');
            form.submit();
            setTimeout(() => resolve({ error: 'timeout', loggedOut: false }), 12000);
        });
    }""", v)
    return result


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080}, locale="en-US")
        page = await context.new_page()

        print("Logging in...")
        ok = await do_login(page)
        if not ok:
            print("Login failed!")
            await browser.close()
            return
        print("Logged in!\n")

        # ====================================================
        # PART 1: Check all makers and their vehicle counts
        # ====================================================
        print("="*60)
        print("PART 1: VEHICLE COUNT AUDIT")
        print("="*60)

        makers = await page.evaluate("""() => {
            const r = [];
            document.querySelectorAll('a[onclick*="seniBrand"]').forEach(a => {
                const text = a.textContent.trim().replace('・', '').trim();
                const match = a.getAttribute('onclick').match(/seniBrand\\('([^']+)'/);
                if (text && match) r.push({ name: text, code: match[1] });
            });
            return r;
        }""")
        print(f"Makers: {len(makers)}")

        maker_totals = {}
        for m in makers:
            await page.evaluate(f"() => seniBrand('{m['code']}')")
            await asyncio.sleep(2)
            models = await page.evaluate("""() => {
                let total = 0;
                document.querySelectorAll('a[onclick*="makerListChoiceCarCat"]').forEach(a => {
                    const m = a.textContent.match(/\\(([\\d,]+)\\)/);
                    if (m) total += parseInt(m[1].replace(',', ''));
                });
                return total;
            }""")
            maker_totals[m['name']] = models
            print(f"  {m['name']}: {models} vehicles")
            await page.evaluate("() => seniToSearchcondition()")
            await asyncio.sleep(2)
            # Wait for seniBrand to be available again
            for _ in range(10):
                has_fn = await page.evaluate("() => typeof seniBrand === 'function'")
                if has_fn:
                    break
                await asyncio.sleep(1)

        grand_total = sum(maker_totals.values())
        print(f"\nTotal vehicles across all makers: {grand_total}")

        # ====================================================
        # PART 2: Test sheet fetching with re-login strategy
        # ====================================================
        print(f"\n{'='*60}")
        print("PART 2: SHEET FETCHING WITH RE-LOGIN")
        print("="*60)

        # Pick a maker with 10-50 vehicles for testing
        test_maker = None
        for m in makers:
            if 10 <= maker_totals.get(m['name'], 0) <= 100:
                test_maker = m
                break
        if not test_maker:
            # Try any maker with vehicles
            for m in makers:
                if maker_totals.get(m['name'], 0) > 0:
                    test_maker = m
                    break

        if not test_maker:
            print("No makers with vehicles!")
            await browser.close()
            return

        print(f"\nTest maker: {test_maker['name']} ({maker_totals[test_maker['name']]} vehicles)")

        # Navigate to search results
        await page.evaluate(f"() => seniBrand('{test_maker['code']}')")
        await asyncio.sleep(3)
        await page.evaluate("() => allSearch()")
        await asyncio.sleep(5)
        for _ in range(10):
            cnt = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
            if cnt > 0: break
            await asyncio.sleep(1)

        vehicles = await page.evaluate("""() => {
            const r = [];
            const seen = new Set();
            document.querySelectorAll('[onclick*=seniCarDetail]').forEach(el => {
                const m = el.getAttribute('onclick').match(/seniCarDetail\\('(\\d+)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)'/);
                if (m && !seen.has(m[4])) {
                    seen.add(m[4]);
                    r.push({ index: m[1], site: m[2], times: m[3], bidNo: m[4], zaikoNo: m[5] });
                }
            });
            return r;
        }""")
        print(f"Unique vehicles: {len(vehicles)}")

        # ===== Strategy: Iframe with re-login every 2 sheets =====
        print(f"\n--- Strategy: Iframe + re-login every 2 fetches ---")
        t0 = time.time()
        total_sheets = 0
        total_fetched = 0
        relogins = 0
        fetch_count_since_login = 0

        for i, v in enumerate(vehicles):
            # Proactive re-login every 2 fetches
            if fetch_count_since_login >= 2:
                print(f"  [re-login #{relogins+1} after {fetch_count_since_login} fetches]")
                ok = await re_login_on_page(page)
                if not ok:
                    print("  Re-login failed!")
                    break
                relogins += 1
                fetch_count_since_login = 0

                # Re-navigate to search results
                await page.evaluate(f"() => seniBrand('{test_maker['code']}')")
                await asyncio.sleep(2)
                await page.evaluate("() => allSearch()")
                await asyncio.sleep(4)
                for _ in range(10):
                    cnt = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
                    if cnt > 0: break
                    await asyncio.sleep(1)

            result = await fetch_sheet_iframe(page, v)
            fetch_count_since_login += 1
            total_fetched += 1

            if result.get('loggedOut'):
                print(f"  {v['bidNo']}: SESSION DEAD (after {fetch_count_since_login} fetches)")
                # Force re-login next iteration
                fetch_count_since_login = 99
            elif result.get('sheet'):
                total_sheets += 1
                print(f"  {v['bidNo']}: SHEET! ({result['htmlLen']} chars)")
            else:
                print(f"  {v['bidNo']}: no sheet (html={result.get('htmlLen','?')})")

            await page.evaluate("() => document.getElementById('form1')?.setAttribute('target', '')")

        t_total = time.time() - t0
        print(f"\nResults:")
        print(f"  Vehicles: {total_fetched}/{len(vehicles)}")
        print(f"  Sheets found: {total_sheets}")
        print(f"  Re-logins: {relogins}")
        print(f"  Time: {t_total:.1f}s ({t_total/max(total_fetched,1):.2f}s per vehicle)")

        # ====================================================
        # PART 3: Check for missing data
        # ====================================================
        print(f"\n{'='*60}")
        print("PART 3: DATA COMPLETENESS CHECK")
        print("="*60)

        # Re-login fresh
        ok = await re_login_on_page(page)
        if not ok:
            print("Re-login failed!")
            await browser.close()
            return

        # Check what data the list page provides
        await page.evaluate(f"() => seniBrand('{test_maker['code']}')")
        await asyncio.sleep(3)
        await page.evaluate("() => allSearch()")
        await asyncio.sleep(5)
        for _ in range(10):
            cnt = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
            if cnt > 0: break
            await asyncio.sleep(1)

        # Extract ALL data from list page
        list_data = await page.evaluate("""() => {
            const results = [];
            const seen = new Set();
            const rows = document.querySelectorAll('tr');
            for (const row of rows) {
                const detailLink = row.querySelector('[onclick*=seniCarDetail]');
                if (!detailLink) continue;
                const onclick = detailLink.getAttribute('onclick');
                const match = onclick.match(/seniCarDetail\\('(\\d+)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)'/);
                if (!match) continue;
                const bidNo = match[4];
                if (seen.has(bidNo)) continue;
                seen.add(bidNo);

                const cells = Array.from(row.querySelectorAll('td')).map(td => td.innerText.trim());
                const img = row.querySelector('img[src*=get_car_image], img[src*=get_image]');
                const imgSrc = img ? img.src : '';
                const keyInput = row.querySelector('input[name^=carKeyStr]');

                results.push({
                    bidNo,
                    site: match[2],
                    times: match[3],
                    cellCount: cells.length,
                    cells: cells.slice(0, 8),
                    hasImage: !!imgSrc,
                    hasKey: !!keyInput,
                });
            }
            return results;
        }""")

        print(f"\nList page data ({len(list_data)} vehicles):")
        print(f"  {'bidNo':>8} | {'site':>4} | cells | img | data sample")
        print(f"  {'-'*70}")
        for d in list_data[:10]:
            sample = ' | '.join(d['cells'][:4])[:50]
            print(f"  {d['bidNo']:>8} | {d['site']:>4} | {d['cellCount']:>5} | {'YES' if d['hasImage'] else ' NO'} | {sample}")
        if len(list_data) > 10:
            print(f"  ... and {len(list_data) - 10} more")

        # Check for missing fields
        no_image = sum(1 for d in list_data if not d['hasImage'])
        print(f"\n  Missing images on list page: {no_image}/{len(list_data)}")
        print(f"  Missing carKeyStr: {sum(1 for d in list_data if not d['hasKey'])}/{len(list_data)}")

        # ====================================================
        # SUMMARY
        # ====================================================
        print(f"\n{'='*60}")
        print("FINAL SUMMARY")
        print("="*60)
        print(f"  Grand total vehicles (all makers): {grand_total}")
        print(f"  Test maker: {test_maker['name']} ({maker_totals[test_maker['name']]} listed, {len(list_data)} found)")
        print(f"  Sheet fetch: {total_sheets}/{total_fetched} with {relogins} re-logins in {t_total:.1f}s")
        print(f"  Session limit: ~2 detail page requests before forced logout")
        print(f"  Re-login overhead: ~8-10s per re-login (login + navigate + search)")

        await browser.close()

asyncio.run(main())
