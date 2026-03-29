"""Test Ninja iframe sheet fetching with Toyota (big maker, should have sheets).
Pick a small Toyota model to stay under 1000 limit.
Run: cd scraper && python3 test_ninja_toyota.py
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

        # Select TOYOTA
        await page.evaluate("() => seniBrand('01')")
        await asyncio.sleep(3)

        # Get models
        models = await page.evaluate("""() => {
            const r = [];
            document.querySelectorAll('a[onclick*="makerListChoiceCarCat"]').forEach(a => {
                const text = a.textContent.trim();
                const m = text.match(/\\(([\\d,]+)\\)/);
                const count = m ? parseInt(m[1].replace(',', '')) : 0;
                const name = text.replace(/\\([\\d,]+\\)/, '').trim();
                const onclick = a.getAttribute('onclick') || '';
                r.push({ name, count, onclick: onclick.substring(0, 100) });
            });
            r.sort((a, b) => a.count - b.count);
            return r;
        }""")
        total = sum(m['count'] for m in models)
        print(f"TOYOTA: {len(models)} models, {total} total vehicles")

        # Find a model with 20-200 vehicles (good test size)
        test_model = None
        for m in models:
            if 20 <= m['count'] <= 200:
                test_model = m
                break
        if not test_model:
            for m in models:
                if m['count'] > 5:
                    test_model = m
                    break

        if not test_model:
            print("No suitable model found!")
            await browser.close()
            return

        print(f"\nSelected model: {test_model['name']} ({test_model['count']} vehicles)")

        # Click the model
        await page.evaluate(f"() => {{ {test_model['onclick']} }}")
        await asyncio.sleep(5)

        # Wait for results
        for _ in range(15):
            cnt = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
            if cnt > 0:
                break
            await asyncio.sleep(1)

        rows = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
        print(f"Rows on page: {rows}")

        if rows == 0:
            txt = await page.evaluate("() => document.body.innerText.substring(0, 300)")
            print(f"Page: {txt[:200]}")

            # Maybe >1000 — check
            if "1,000" in txt or "More than" in txt:
                print("Over 1000! Trying smaller model...")
                # Go back and pick smallest model with vehicles
                await page.evaluate("() => seniToSearchcondition()")
                await asyncio.sleep(2)
                await page.evaluate("() => seniBrand('01')")
                await asyncio.sleep(3)
                # Pick model with smallest count > 0
                for m in models:
                    if 1 <= m['count'] <= 50:
                        test_model = m
                        break
                print(f"Trying: {test_model['name']} ({test_model['count']} vehicles)")
                await page.evaluate(f"() => {{ {test_model['onclick']} }}")
                await asyncio.sleep(5)
                for _ in range(10):
                    cnt = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
                    if cnt > 0: break
                    await asyncio.sleep(1)
                rows = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
                print(f"Rows: {rows}")

            if rows == 0:
                await browser.close()
                return

        # Switch to 100/page
        try:
            await page.select_option(".selDisplayedItems", "100")
            await asyncio.sleep(4)
            for _ in range(10):
                cnt = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
                if cnt > rows: break
                await asyncio.sleep(1)
        except:
            pass

        vehicles = await page.evaluate("""() => {
            const r = [];
            document.querySelectorAll('[onclick*=seniCarDetail]').forEach(el => {
                const m = el.getAttribute('onclick').match(/seniCarDetail\\('(\\d+)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)'/);
                if (m) r.push({ index: m[1], site: m[2], times: m[3], bidNo: m[4], zaikoNo: m[5] });
            });
            return r;
        }""")
        print(f"Total vehicles: {len(vehicles)}")

        test_count = min(10, len(vehicles))

        # ===== A: New tabs =====
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
                    print(f"  Vehicle {v['bidNo']}: SHEET FOUND")
                else:
                    print(f"  Vehicle {v['bidNo']}: no sheet")
            except Exception as e:
                print(f"  Vehicle {v['bidNo']}: ERROR {e}")
                for extra in context.pages[1:]:
                    try: await extra.close()
                    except: pass
        ta = time.time() - t0
        await page.evaluate("() => document.getElementById('form1').setAttribute('target', '')")
        print(f"  Total: {ta:.2f}s | {ta/test_count:.2f}s/v | Sheets: {sheets_a}/{test_count}")

        # ===== B: Batch iframes x5 =====
        print(f"\n=== B: Batch iframes x5 ({test_count} vehicles) ===")
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
                        if (!f) { f=document.createElement('iframe'); f.id=fid; f.name=fid; f.style.cssText='position:absolute;left:-9999px;width:1px;height:1px'; document.body.appendChild(f); }
                        f.onload = () => {
                            try { f.contentDocument.querySelectorAll('img').forEach(i => { if (i.src.includes('get_ex_image')) results[idx]=i.src; }); } catch(e) {}
                            check();
                        };
                        const orig = document.getElementById('form1');
                        const c = orig.cloneNode(true);
                        c.style.display='none';
                        const set = (n,val) => { const el=c.querySelector('[name='+n+']'); if(el) el.value=val; };
                        set('carKindType','1'); set('kaijoCode',v.site); set('auctionCount',v.times);
                        set('bidNo',v.bidNo); set('zaikoNo',''); set('action','init');
                        c.setAttribute('action','./cardetail.action');
                        c.setAttribute('target',fid);
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
                    print(f"  Vehicle {bid}: SHEET FOUND")
                else:
                    print(f"  Vehicle {bid}: no sheet")
        tb = time.time() - t0
        print(f"  Total: {tb:.2f}s | {tb/test_count:.2f}s/v | Sheets: {sheets_b}/{test_count}")

        # Session
        alive = await page.evaluate("() => !!document.getElementById('form1')")
        print(f"\nSession alive: {alive}")

        # Summary
        print(f"\n{'='*60}")
        print(f"RESULTS ({test_count} vehicles - {test_model['name']})")
        print(f"{'='*60}")
        print(f"  A) New tabs:        {ta:.2f}s ({ta/test_count:.2f}s/v) sheets={sheets_a}/{test_count}")
        print(f"  B) Batch iframe x5: {tb:.2f}s ({tb/test_count:.2f}s/v) sheets={sheets_b}/{test_count}")
        if ta > 0 and tb > 0:
            print(f"\n  Iframe is {ta/tb:.1f}x faster")
        print(f"  Same sheets found: {sheets_a == sheets_b}")

        await browser.close()

asyncio.run(main())
