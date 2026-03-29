"""Test iframe with HTML parsing for exhibit sheets (Toyota ROOMY).
Run: cd scraper && python3 test_ninja_html_iframe.py
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

        # TOYOTA → ROOMY
        await page.evaluate("() => seniBrand('01')")
        await asyncio.sleep(3)
        await page.evaluate("""() => {
            document.querySelectorAll('a[onclick*="makerListChoiceCarCat"]').forEach(a => {
                if (a.textContent.includes('ROOMY')) a.click();
            });
        }""")
        await asyncio.sleep(5)

        for _ in range(10):
            cnt = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
            if cnt > 0:
                break
            await asyncio.sleep(1)

        vehicles = await page.evaluate("""() => {
            const r = [];
            document.querySelectorAll('[onclick*=seniCarDetail]').forEach(el => {
                const m = el.getAttribute('onclick').match(/seniCarDetail\\('(\\d+)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)'/);
                if (m) r.push({ index: m[1], site: m[2], times: m[3], bidNo: m[4], zaikoNo: m[5] });
            });
            return r;
        }""")
        print(f"Vehicles: {len(vehicles)}")
        test_count = min(10, len(vehicles))

        # ===== A: New tabs (baseline) =====
        print(f"\n=== A: New tabs ({test_count} vehicles) ===")
        t0 = time.time()
        sheets_a = 0
        for v in vehicles[:test_count]:
            try:
                np = context.wait_for_event("page", timeout=10000)
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
                }""", v)
                dp = await np
                await dp.wait_for_load_state("domcontentloaded", timeout=10000)
                await asyncio.sleep(0.5)
                s = await dp.evaluate("() => { for (const i of document.querySelectorAll('img')) if (i.src.includes('get_ex_image')) return i.src; return ''; }")
                await dp.close()
                if s:
                    sheets_a += 1
                    print(f"  {v['bidNo']}: FOUND")
                else:
                    print(f"  {v['bidNo']}: none")
            except:
                for extra in context.pages[1:]:
                    try: await extra.close()
                    except: pass
        ta = time.time() - t0
        await page.evaluate("() => document.getElementById('form1').setAttribute('target', '')")
        print(f"  TOTAL: {ta:.2f}s | {ta/test_count:.2f}s/v | Sheets: {sheets_a}/{test_count}")

        # ===== B: Batch iframes x5 with HTML parsing =====
        print(f"\n=== B: Batch iframes x5 + HTML parsing ({test_count} vehicles) ===")
        t0 = time.time()
        sheets_b = 0
        batch_size = 5
        for bi in range(0, test_count, batch_size):
            batch = vehicles[bi:bi + batch_size]
            results = await page.evaluate("""(batch) => {
                return new Promise((resolve) => {
                    const results = new Array(batch.length).fill('');
                    let done = 0;
                    const check = () => { done++; if (done >= batch.length) resolve(results); };

                    batch.forEach((v, idx) => {
                        const fid = '_bf' + idx;
                        let f = document.getElementById(fid);
                        if (!f) {
                            f = document.createElement('iframe');
                            f.id = fid; f.name = fid;
                            f.style.cssText = 'position:absolute;left:-9999px;width:1px;height:1px';
                            document.body.appendChild(f);
                        }
                        f.onload = () => {
                            try {
                                // Parse HTML source for get_ex_image URL (don't wait for img render)
                                const html = f.contentDocument.documentElement.innerHTML;
                                const m = html.match(/action=get_ex_image&amp;FilePath=([^"&]*)/);
                                if (m) {
                                    results[idx] = './cardetail.action?action=get_ex_image&FilePath=' + m[1];
                                }
                            } catch(e) {}
                            check();
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
                    setTimeout(() => resolve(results), 15000);
                });
            }""", batch)
            for i, r in enumerate(results):
                bid = batch[i]['bidNo']
                if r:
                    sheets_b += 1
                    print(f"  {bid}: FOUND")
                else:
                    print(f"  {bid}: none")
        tb = time.time() - t0
        print(f"  TOTAL: {tb:.2f}s | {tb/test_count:.2f}s/v | Sheets: {sheets_b}/{test_count}")

        # Session check
        alive = await page.evaluate("() => !!document.getElementById('form1')")
        print(f"\nSession alive: {alive}")

        # Summary
        print(f"\n{'='*60}")
        print(f"RESULTS ({test_count} vehicles - TOYOTA ROOMY)")
        print(f"{'='*60}")
        print(f"  A) New tabs:              {ta:.2f}s ({ta/test_count:.2f}s/v) sheets={sheets_a}/{test_count}")
        print(f"  B) Batch iframe x5+HTML:  {tb:.2f}s ({tb/test_count:.2f}s/v) sheets={sheets_b}/{test_count}")
        if ta > 0 and tb > 0:
            print(f"\n  Speedup: {ta/tb:.1f}x faster")
        print(f"  Same results: {sheets_a == sheets_b}")

        await browser.close()

asyncio.run(main())
