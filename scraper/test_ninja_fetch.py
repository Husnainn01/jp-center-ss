"""Test Ninja: login → search → fetch-based sheet extraction (no new tabs).
Run: cd scraper && python3 test_ninja_fetch.py
"""
import asyncio
import time
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        page = await context.new_page()

        # Login
        print("Logging in...")
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
            print("Force login...")
            await page.evaluate("""() => {
                for (const a of document.querySelectorAll('a'))
                    if (a.textContent.trim() === 'Login') { a.click(); return; }
            }""")
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(3)

        if "searchcondition" not in page.url:
            print(f"Login failed! URL: {page.url}")
            await browser.close()
            return
        print("Logged in!\n")

        # Get makers
        makers = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('a[onclick*="seniBrand"]').forEach(a => {
                const text = a.textContent.trim();
                const match = a.getAttribute('onclick').match(/seniBrand\\('([^']+)'/);
                if (text && match) results.push({ name: text, code: match[1] });
            });
            return results;
        }""")
        print(f"Makers: {len(makers)}")
        for m in makers:
            print(f"  {m['name']} ({m['code']})")

        # Pick a small maker
        test = makers[-1] if makers else None
        for m in makers:
            if any(k in m['name'].upper() for k in ['MINI', 'SMART', 'FIAT']):
                test = m
                break

        if not test:
            print("No makers found!")
            await browser.close()
            return

        print(f"\n{'='*60}")
        print(f"Testing: {test['name']}")
        print(f"{'='*60}")

        await page.evaluate(f"() => seniBrand('{test['code']}')")
        await asyncio.sleep(3)

        # Models
        models = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('a[onclick*="makerListChoiceCarCat"]').forEach(a => {
                const text = a.textContent.trim();
                const countMatch = text.match(/\\(([\\d,]+)\\)/);
                const count = countMatch ? parseInt(countMatch[1].replace(',', '')) : 0;
                const name = text.replace(/\\([\\d,]+\\)/, '').trim();
                results.push({ name, count });
            });
            results.sort((a, b) => b.count - a.count);
            return results;
        }""")
        total = sum(m['count'] for m in models)
        print(f"Models: {len(models)}, total: {total}")
        for m in models[:5]:
            print(f"  {m['name']}: {m['count']}")

        if total == 0:
            print("No vehicles!")
            await browser.close()
            return

        # allSearch
        print(f"\nSearching...")
        await page.evaluate("() => allSearch()")
        await asyncio.sleep(5)

        # Switch to 100/page
        await page.evaluate("""() => {
            const sel = document.querySelector('.selDisplayedItems');
            if (sel) { sel.value = '100'; sel.dispatchEvent(new Event('change')); }
        }""")
        await asyncio.sleep(3)

        # Get vehicles
        vehicles = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('[onclick*=seniCarDetail]').forEach(el => {
                const onclick = el.getAttribute('onclick');
                const match = onclick.match(/seniCarDetail\\('(\\d+)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)'/);
                if (match) {
                    results.push({
                        index: match[1], site: match[2], times: match[3],
                        bidNo: match[4], zaikoNo: match[5],
                    });
                }
            });
            return results;
        }""")
        print(f"Vehicles on page: {len(vehicles)}")

        if not vehicles:
            print("No vehicle data found!")
            await browser.close()
            return

        # Check form1
        has_form = await page.evaluate("() => !!document.getElementById('form1')")
        print(f"form1: {has_form}")

        if not has_form:
            print("No form1!")
            await browser.close()
            return

        # === TEST 1: Single fetch (no new tab) ===
        print(f"\n--- TEST 1: Single fetch ---")
        v = vehicles[0]
        t0 = time.time()
        result = await page.evaluate("""async (v) => {
            const form = document.getElementById('form1');
            const params = new URLSearchParams();
            for (const [key, val] of new FormData(form)) {
                params.set(key, val);
            }
            params.set('carKindType', '1');
            params.set('kaijoCode', v.site);
            params.set('auctionCount', v.times);
            params.set('bidNo', v.bidNo);
            params.set('zaikoNo', '');
            params.set('action', 'init');

            const res = await fetch('./cardetail.action', {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: params.toString()
            });
            const html = await res.text();
            const exUrls = [...html.matchAll(/get_ex_image[^"']*/g)].map(m => m[0]);
            return {
                status: res.status,
                htmlLen: html.length,
                hasEx: html.includes('get_ex_image'),
                exUrl: exUrls.length > 0 ? exUrls[0] : '',
                exCount: exUrls.length,
            };
        }""", v)
        t1 = time.time()
        print(f"  Time: {t1-t0:.2f}s")
        print(f"  status={result['status']}, htmlLen={result['htmlLen']}")
        print(f"  hasSheet: {result['hasEx']}, sheetURLs: {result['exCount']}")
        if result.get('exUrl'):
            print(f"  URL: {result['exUrl'][:100]}")

        # === TEST 2: Parallel fetch (5 vehicles at once) ===
        test_count = min(5, len(vehicles))
        print(f"\n--- TEST 2: Parallel fetch ({test_count} vehicles) ---")
        test_vehicles = vehicles[:test_count]
        t0 = time.time()
        results = await page.evaluate("""async (vehicles) => {
            const form = document.getElementById('form1');
            const baseParams = new URLSearchParams();
            for (const [key, val] of new FormData(form)) {
                baseParams.set(key, val);
            }

            const promises = vehicles.map(async (v) => {
                const params = new URLSearchParams(baseParams);
                params.set('carKindType', '1');
                params.set('kaijoCode', v.site);
                params.set('auctionCount', v.times);
                params.set('bidNo', v.bidNo);
                params.set('zaikoNo', '');
                params.set('action', 'init');

                const res = await fetch('./cardetail.action', {
                    method: 'POST',
                    credentials: 'include',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: params.toString()
                });
                const html = await res.text();
                const exUrls = [...html.matchAll(/get_ex_image[^"']*/g)].map(m => m[0]);
                return {
                    bidNo: v.bidNo,
                    hasEx: html.includes('get_ex_image'),
                    exUrl: exUrls.length > 0 ? exUrls[0] : '',
                };
            });
            return Promise.all(promises);
        }""", test_vehicles)
        t1 = time.time()
        print(f"  Time: {t1-t0:.2f}s (for {test_count} vehicles)")
        for r in results:
            sheet_info = r['exUrl'][:60] if r['exUrl'] else 'none'
            print(f"  bidNo={r['bidNo']}: sheet={'YES' if r['hasEx'] else 'NO'} {sheet_info}")

        # === TEST 3: Parallel fetch (10 vehicles) ===
        if len(vehicles) >= 10:
            test_count = 10
            print(f"\n--- TEST 3: Parallel fetch ({test_count} vehicles) ---")
            test_vehicles = vehicles[:test_count]
            t0 = time.time()
            results = await page.evaluate("""async (vehicles) => {
                const form = document.getElementById('form1');
                const baseParams = new URLSearchParams();
                for (const [key, val] of new FormData(form)) {
                    baseParams.set(key, val);
                }

                const promises = vehicles.map(async (v) => {
                    const params = new URLSearchParams(baseParams);
                    params.set('carKindType', '1');
                    params.set('kaijoCode', v.site);
                    params.set('auctionCount', v.times);
                    params.set('bidNo', v.bidNo);
                    params.set('zaikoNo', '');
                    params.set('action', 'init');

                    const res = await fetch('./cardetail.action', {
                        method: 'POST',
                        credentials: 'include',
                        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                        body: params.toString()
                    });
                    const html = await res.text();
                    const exUrls = [...html.matchAll(/get_ex_image[^"']*/g)].map(m => m[0]);
                    return {
                        bidNo: v.bidNo,
                        hasEx: html.includes('get_ex_image'),
                    };
                });
                return Promise.all(promises);
            }""", test_vehicles)
            t1 = time.time()
            found = sum(1 for r in results if r['hasEx'])
            print(f"  Time: {t1-t0:.2f}s (for {test_count} vehicles)")
            print(f"  Sheets found: {found}/{test_count}")

        # === Verify session still alive ===
        print(f"\n--- Session check ---")
        still_ok = await page.evaluate("""() => {
            return !document.body.innerText.includes('different user') &&
                   !!document.getElementById('form1');
        }""")
        print(f"Session alive after fetch tests: {still_ok}")

        print(f"\n{'='*60}")
        print("TEST COMPLETE")
        print(f"{'='*60}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
