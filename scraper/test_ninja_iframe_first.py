"""Test iframe FIRST (before new tabs) to get clean results.
Run: cd scraper && python3 test_ninja_iframe_first.py
"""
import asyncio
import time
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080}, locale="en-US")
        page = await context.new_page()
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
        if "searchcondition" not in page.url:
            print("Login failed!")
            return
        print("Logged in!")

        # Mitsuoka (small maker)
        await page.evaluate("() => seniBrand('19')")
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
        if len(vehicles) == 0:
            print("No vehicles!")
            await browser.close()
            return

        test_count = min(4, len(vehicles))

        # ===== IFRAME FIRST (clean session) =====
        print(f"\n{'='*60}")
        print(f"TEST 1: IFRAME (clean session, {test_count} vehicles)")
        print(f"{'='*60}")
        t0 = time.time()
        sheets_iframe = 0
        for v in vehicles[:test_count]:
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
                                let sheet = '';
                                doc.querySelectorAll('img').forEach(img => {
                                    if (img.src.includes('get_ex_image')) sheet = img.src;
                                });
                                if (!sheet) {
                                    const m = html.match(/action=get_ex_image&amp;FilePath=([^"&]*)/);
                                    if (m) sheet = './cardetail.action?action=get_ex_image&FilePath=' + m[1];
                                }
                                resolve({
                                    sheet, htmlLen: html.length,
                                    hasEx: html.includes('get_ex_image'),
                                    loggedOut: doc.body.innerText.includes('logged out'),
                                });
                            } catch(e) { resolve({ error: e.message }); }
                        }, 2000);
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
                    setTimeout(() => resolve({ error: 'timeout' }), 15000);
                });
            }""", v)

            if result.get('loggedOut'):
                print(f"  {v['bidNo']}: SESSION DEAD!")
                break
            elif result.get('sheet'):
                sheets_iframe += 1
                print(f"  {v['bidNo']}: SHEET FOUND! html={result['htmlLen']}")
            elif result.get('error'):
                print(f"  {v['bidNo']}: ERROR: {result['error']}")
            else:
                print(f"  {v['bidNo']}: no sheet (html={result.get('htmlLen','?')}, hasEx={result.get('hasEx','?')})")
        t_iframe = time.time() - t0
        await page.evaluate("() => document.getElementById('form1')?.setAttribute('target', '')")
        print(f"  Total: {t_iframe:.2f}s | Sheets: {sheets_iframe}/{test_count}")

        # Check session
        alive = await page.evaluate("() => !!document.getElementById('form1') && !document.body.innerText.includes('logged out')")
        print(f"  Session alive: {alive}")

        if not alive:
            print("\nSession died during iframe test! Cannot continue.")
            await browser.close()
            return

        # ===== BATCH IFRAME x4 =====
        print(f"\n{'='*60}")
        print(f"TEST 2: BATCH IFRAME x{test_count} (all at once)")
        print(f"{'='*60}")
        t0 = time.time()
        sheets_batch = 0
        batch = vehicles[:test_count]
        results = await page.evaluate("""(batch) => {
            return new Promise((resolve) => {
                const results = new Array(batch.length).fill(null);
                let done = 0;
                const check = () => { done++; if (done >= batch.length) resolve(results); };

                batch.forEach((v, idx) => {
                    const fid = '_bf' + idx;
                    let f = document.getElementById(fid);
                    if (!f) {
                        f = document.createElement('iframe');
                        f.id = fid; f.name = fid;
                        f.style.cssText = 'position:absolute;left:-9999px;width:800px;height:600px';
                        document.body.appendChild(f);
                    }
                    f.onload = () => {
                        setTimeout(() => {
                            try {
                                const doc = f.contentDocument;
                                const html = doc.documentElement.innerHTML;
                                let sheet = '';
                                doc.querySelectorAll('img').forEach(img => {
                                    if (img.src.includes('get_ex_image')) sheet = img.src;
                                });
                                if (!sheet) {
                                    const m = html.match(/action=get_ex_image&amp;FilePath=([^"&]*)/);
                                    if (m) sheet = './cardetail.action?action=get_ex_image&FilePath=' + m[1];
                                }
                                results[idx] = { sheet, htmlLen: html.length, hasEx: html.includes('get_ex_image'), loggedOut: doc.body.innerText.includes('logged out') };
                            } catch(e) { results[idx] = { error: e.message }; }
                            check();
                        }, 2000);
                    };
                    const orig = document.getElementById('form1');
                    const c = orig.cloneNode(true);
                    c.style.display = 'none';
                    const set = (n, val) => { const el = c.querySelector('[name=' + n + ']'); if (el) el.value = val; };
                    set('carKindType', '1'); set('kaijoCode', v.site); set('auctionCount', v.times);
                    set('bidNo', v.bidNo); set('zaikoNo', ''); set('action', 'init');
                    c.setAttribute('action', './cardetail.action');
                    c.setAttribute('target', fid);
                    document.body.appendChild(c);
                    c.submit();
                    c.remove();
                });
                setTimeout(() => resolve(results), 20000);
            });
        }""", batch)
        for i, r in enumerate(results):
            bid = batch[i]['bidNo']
            if r and r.get('loggedOut'):
                print(f"  {bid}: SESSION DEAD!")
            elif r and r.get('sheet'):
                sheets_batch += 1
                print(f"  {bid}: SHEET FOUND! html={r['htmlLen']}")
            elif r:
                print(f"  {bid}: no sheet (html={r.get('htmlLen','?')}, hasEx={r.get('hasEx','?')})")
            else:
                print(f"  {bid}: null result")
        t_batch = time.time() - t0
        print(f"  Total: {t_batch:.2f}s | Sheets: {sheets_batch}/{test_count}")

        alive = await page.evaluate("() => !!document.getElementById('form1') && !document.body.innerText.includes('logged out')")
        print(f"  Session alive: {alive}")

        # Summary
        print(f"\n{'='*60}")
        print(f"SUMMARY")
        print(f"{'='*60}")
        print(f"  Iframe sequential: {t_iframe:.2f}s sheets={sheets_iframe}/{test_count}")
        print(f"  Batch iframe:      {t_batch:.2f}s sheets={sheets_batch}/{test_count}")

        await browser.close()

asyncio.run(main())
