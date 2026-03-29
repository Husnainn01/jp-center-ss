"""Test: iframe sheet fetching with proactive re-login.
Find the exact session limit and optimal re-login cadence.
Run: cd scraper && python3 test_ninja_relogin.py
"""
import asyncio
import time
from playwright.async_api import async_playwright


async def do_login(page):
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


async def navigate_to_results(page, maker_code):
    """Navigate to search results for a maker. Returns vehicle count."""
    await page.evaluate(f"() => seniBrand('{maker_code}')")
    await asyncio.sleep(3)
    await page.evaluate("() => allSearch()")
    await asyncio.sleep(5)
    for _ in range(10):
        cnt = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
        if cnt > 0:
            return cnt
        await asyncio.sleep(1)
    return 0


async def get_vehicles(page):
    """Get unique vehicles from current results page."""
    return await page.evaluate("""() => {
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


async def fetch_sheet(page, v):
    """Fetch exhibit sheet via iframe. Returns {sheet, loggedOut, htmlLen}."""
    return await page.evaluate("""(v) => {
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
                    } catch(e) { resolve({ error: e.message, loggedOut: false, sheet: '' }); }
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
            setTimeout(() => resolve({ error: 'timeout', loggedOut: false, sheet: '' }), 12000);
        });
    }""", v)


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

        # Use MAZDA (874 vehicles, under 1000 limit)
        maker_code = "10"
        maker_name = "MAZDA"

        # ====================================================
        # TEST 1: Find exact session limit
        # ====================================================
        print("="*60)
        print("TEST 1: Find session limit (how many fetches before logout)")
        print("="*60)

        cnt = await navigate_to_results(page, maker_code)
        vehicles = await get_vehicles(page)
        print(f"{maker_name}: {cnt} rows, {len(vehicles)} unique")

        consecutive_success = 0
        for i, v in enumerate(vehicles[:15]):
            result = await fetch_sheet(page, v)
            await page.evaluate("() => document.getElementById('form1')?.setAttribute('target', '')")

            if result.get('loggedOut'):
                print(f"  #{i+1} {v['bidNo']}: LOGGED OUT after {consecutive_success} successful fetches")
                break
            elif result.get('sheet'):
                consecutive_success += 1
                print(f"  #{i+1} {v['bidNo']}: SHEET ({result['htmlLen']} chars) [success #{consecutive_success}]")
            else:
                consecutive_success += 1
                print(f"  #{i+1} {v['bidNo']}: no sheet ({result['htmlLen']} chars) [success #{consecutive_success}]")

        session_limit = consecutive_success
        print(f"\n>>> SESSION LIMIT: {session_limit} fetches before logout")

        # ====================================================
        # TEST 2: Re-login cadence test
        # ====================================================
        print(f"\n{'='*60}")
        print(f"TEST 2: Fetch with re-login every {session_limit} fetches")
        print("="*60)

        # Fresh login
        ok = await do_login(page)
        if not ok:
            print("Re-login failed!")
            await browser.close()
            return

        cnt = await navigate_to_results(page, maker_code)
        vehicles = await get_vehicles(page)
        print(f"Vehicles: {len(vehicles)}")

        t0 = time.time()
        total_sheets = 0
        total_fetched = 0
        relogins = 0
        fetch_since_login = 0
        relogin_limit = max(1, session_limit - 1)  # Re-login 1 before limit

        for i, v in enumerate(vehicles[:20]):  # Test 20 vehicles
            # Proactive re-login
            if fetch_since_login >= relogin_limit:
                relogin_t = time.time()
                ok = await do_login(page)
                if not ok:
                    print(f"  Re-login failed at vehicle {i}!")
                    break
                cnt = await navigate_to_results(page, maker_code)
                vehicles_new = await get_vehicles(page)
                relogins += 1
                fetch_since_login = 0
                relogin_dur = time.time() - relogin_t
                print(f"  [RE-LOGIN #{relogins} in {relogin_dur:.1f}s, found {len(vehicles_new)} vehicles]")
                # Update vehicle list in case order changed
                # But keep using original list for consistency

            result = await fetch_sheet(page, v)
            await page.evaluate("() => document.getElementById('form1')?.setAttribute('target', '')")
            fetch_since_login += 1
            total_fetched += 1

            if result.get('loggedOut'):
                print(f"  {v['bidNo']}: LOGOUT (unexpected! fetch #{fetch_since_login})")
                fetch_since_login = relogin_limit  # Force re-login next
            elif result.get('sheet'):
                total_sheets += 1
                print(f"  {v['bidNo']}: SHEET")
            else:
                print(f"  {v['bidNo']}: no sheet")

        t_total = time.time() - t0
        print(f"\n--- Results ---")
        print(f"  Fetched: {total_fetched}/20")
        print(f"  Sheets: {total_sheets}")
        print(f"  Re-logins: {relogins}")
        print(f"  Time: {t_total:.1f}s ({t_total/max(total_fetched,1):.2f}s per vehicle)")
        print(f"  Effective rate: {total_fetched/t_total*60:.0f} vehicles/min")

        # ====================================================
        # SUMMARY
        # ====================================================
        print(f"\n{'='*60}")
        print("OPTIMIZATION PLAN")
        print("="*60)
        print(f"  Session limit: {session_limit} detail page requests")
        print(f"  Re-login takes: ~8-10s")
        print(f"  Iframe speed: ~2s per vehicle (with 1.5s render wait)")
        print(f"  For 100 vehicles:")
        relogins_needed = 100 // relogin_limit
        fetch_time = 100 * 2
        relogin_time = relogins_needed * 10
        total_est = fetch_time + relogin_time
        print(f"    {relogins_needed} re-logins × 10s = {relogin_time}s")
        print(f"    100 fetches × 2s = {fetch_time}s")
        print(f"    Total: ~{total_est}s ({total_est/60:.1f} min)")
        print(f"    Current (new tab): ~100-200s for 100 vehicles")
        print(f"    With re-login overhead: comparable but more reliable")

        await browser.close()

asyncio.run(main())
