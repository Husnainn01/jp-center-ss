"""Test multi-iframe sheet fetching on Ninja.
Run: cd scraper && python3 test_ninja_multi_iframe.py
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

        # VOLVO
        await page.evaluate("() => seniBrand('90')")
        await asyncio.sleep(3)
        await page.evaluate("() => allSearch()")
        await asyncio.sleep(5)

        # Wait for results
        for _ in range(10):
            cnt = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
            if cnt > 0:
                break
            await asyncio.sleep(1)

        rows_before = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
        print(f"Rows before page size: {rows_before}")

        if rows_before == 0:
            # Check what's on the page
            await page.screenshot(path="ninja_volvo.png")
            txt = await page.evaluate("() => document.body.innerText.substring(0, 500)")
            print(f"Page: {txt[:300]}")
            # Try select_option
            try:
                await page.select_option(".selDisplayedItems", "100")
                await asyncio.sleep(3)
                rows_after = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
                print(f"After select_option: {rows_after}")
            except Exception as e:
                print(f"select_option failed: {e}")
            await browser.close()
            return

        # Switch to 100/page using Playwright select
        try:
            await page.select_option(".selDisplayedItems", "100")
        except:
            await page.evaluate("""() => {
                const sel = document.querySelector('.selDisplayedItems');
                if (sel) { sel.value = '100'; sel.onchange && sel.onchange(); }
            }""")
        await asyncio.sleep(4)

        for _ in range(15):
            cnt = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
            if cnt > rows_before:
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
        if test_count < 3:
            print("Not enough vehicles")
            await browser.close()
            return

        # ===== TEST A: Sequential new tabs =====
        print(f"\n=== A: Sequential new tabs ({test_count} vehicles) ===")
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
                if s: sheets_a += 1
            except:
                for extra in context.pages[1:]:
                    try: await extra.close()
                    except: pass
        ta = time.time() - t0
        await page.evaluate("() => document.getElementById('form1').setAttribute('target', '')")
        print(f"  {ta:.2f}s total | {ta/test_count:.2f}s/vehicle | Sheets: {sheets_a}/{test_count}")

        # ===== TEST B: Sequential iframe =====
        print(f"\n=== B: Sequential iframe ({test_count} vehicles) ===")
        t0 = time.time()
        sheets_b = 0
        for v in vehicles[:test_count]:
            r = await page.evaluate("""(v) => {
                return new Promise((resolve) => {
                    let f = document.getElementById('_sf');
                    if (!f) { f = document.createElement('iframe'); f.id='_sf'; f.name='_sf'; f.style.cssText='position:absolute;left:-9999px;width:1px;height:1px'; document.body.appendChild(f); }
                    f.onload = () => { try { let s=''; f.contentDocument.querySelectorAll('img').forEach(i => { if (i.src.includes('get_ex_image')) s=i.src; }); resolve(s); } catch(e) { resolve(''); } };
                    document.getElementById('carKindType').value='1';
                    document.getElementById('kaijoCode').value=v.site;
                    document.getElementById('auctionCount').value=v.times;
                    document.getElementById('bidNo').value=v.bidNo;
                    document.getElementById('zaikoNo').value='';
                    document.getElementById('action').value='init';
                    var form=document.getElementById('form1'); form.setAttribute('action','./cardetail.action'); form.setAttribute('target','_sf'); form.submit();
                    setTimeout(() => resolve(''), 10000);
                });
            }""", v)
            if r: sheets_b += 1
        tb = time.time() - t0
        await page.evaluate("() => document.getElementById('form1').setAttribute('target', '')")
        print(f"  {tb:.2f}s total | {tb/test_count:.2f}s/vehicle | Sheets: {sheets_b}/{test_count}")

        # ===== TEST C: Batch cloned forms → multiple iframes =====
        print(f"\n=== C: Batch iframes x3 ({test_count} vehicles) ===")
        t0 = time.time()
        sheets_c = 0
        batch_size = 3
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
                        // Clone form and submit to this iframe
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
            sheets_c += sum(1 for r in results if r)
        tc = time.time() - t0
        print(f"  {tc:.2f}s total | {tc/test_count:.2f}s/vehicle | Sheets: {sheets_c}/{test_count}")

        # ===== TEST D: Batch iframes x5 =====
        print(f"\n=== D: Batch iframes x5 ({test_count} vehicles) ===")
        t0 = time.time()
        sheets_d = 0
        batch_size = 5
        for bi in range(0, test_count, batch_size):
            batch = vehicles[bi:bi + batch_size]
            results = await page.evaluate("""(batch) => {
                return new Promise((resolve) => {
                    const results = new Array(batch.length).fill('');
                    let done = 0;
                    const check = () => { done++; if (done >= batch.length) resolve(results); };

                    batch.forEach((v, idx) => {
                        const fid = '_df' + idx;
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
            sheets_d += sum(1 for r in results if r)
        td = time.time() - t0
        print(f"  {td:.2f}s total | {td/test_count:.2f}s/vehicle | Sheets: {sheets_d}/{test_count}")

        # Session check
        alive = await page.evaluate("() => !!document.getElementById('form1')")
        print(f"\nSession alive: {alive}")

        print(f"\n{'='*60}")
        print(f"SPEED COMPARISON ({test_count} vehicles)")
        print(f"{'='*60}")
        print(f"  A) New tabs (sequential):  {ta:.2f}s ({ta/test_count:.2f}s/v) sheets={sheets_a}")
        print(f"  B) Single iframe (seq):    {tb:.2f}s ({tb/test_count:.2f}s/v) sheets={sheets_b}")
        print(f"  C) Batch iframes x3:       {tc:.2f}s ({tc/test_count:.2f}s/v) sheets={sheets_c}")
        print(f"  D) Batch iframes x5:       {td:.2f}s ({td/test_count:.2f}s/v) sheets={sheets_d}")
        print(f"\nSpeedups vs new tabs:")
        if ta > 0:
            print(f"  B) {ta/tb:.1f}x faster")
            print(f"  C) {ta/tc:.1f}x faster")
            print(f"  D) {ta/td:.1f}x faster")

        await browser.close()

asyncio.run(main())
