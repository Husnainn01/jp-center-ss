"""Test Ninja with small maker + iframe sheet fetching.
Run: cd scraper && python3 test_ninja_fetch3.py
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

        # Select MITSUOKA (very small maker)
        await page.evaluate("() => seniBrand('19')")
        await asyncio.sleep(3)

        models = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('a[onclick*="makerListChoiceCarCat"]').forEach(a => {
                const text = a.textContent.trim();
                const countMatch = text.match(/\\(([\\d,]+)\\)/);
                const count = countMatch ? parseInt(countMatch[1].replace(',', '')) : 0;
                results.push({ name: text, count });
            });
            return results;
        }""")
        total = sum(m['count'] for m in models)
        print(f"MITSUOKA: {len(models)} models, {total} vehicles")
        if total == 0:
            # Try ALFA ROMEO
            print("Trying ALFA ROMEO...")
            await page.evaluate("() => seniToSearchcondition()")
            await asyncio.sleep(2)
            await page.evaluate("() => seniBrand('73')")
            await asyncio.sleep(3)
            models = await page.evaluate("""() => {
                const results = [];
                document.querySelectorAll('a[onclick*="makerListChoiceCarCat"]').forEach(a => {
                    const text = a.textContent.trim();
                    const countMatch = text.match(/\\(([\\d,]+)\\)/);
                    const count = countMatch ? parseInt(countMatch[1].replace(',', '')) : 0;
                    results.push({ name: text, count });
                });
                return results;
            }""")
            total = sum(m['count'] for m in models)
            print(f"ALFA ROMEO: {len(models)} models, {total} vehicles")

        if total == 0:
            # Try VOLVO
            print("Trying VOLVO...")
            await page.evaluate("() => seniToSearchcondition()")
            await asyncio.sleep(2)
            await page.evaluate("() => seniBrand('90')")
            await asyncio.sleep(3)
            models = await page.evaluate("""() => {
                const results = [];
                document.querySelectorAll('a[onclick*="makerListChoiceCarCat"]').forEach(a => {
                    const text = a.textContent.trim();
                    const countMatch = text.match(/\\(([\\d,]+)\\)/);
                    const count = countMatch ? parseInt(countMatch[1].replace(',', '')) : 0;
                    results.push({ name: text, count });
                });
                return results;
            }""")
            total = sum(m['count'] for m in models)
            print(f"VOLVO: {len(models)} models, {total} vehicles")

        for m in models[:5]:
            print(f"  {m['name']}: {m['count']}")

        if total == 0 or total > 1000:
            print(f"Bad total ({total}), can't test. Need a maker with 1-999 vehicles.")
            await browser.close()
            return

        # allSearch
        print(f"\nSearching {total} vehicles...")
        await page.evaluate("() => allSearch()")
        await asyncio.sleep(5)

        # Switch to 100/page
        await page.evaluate("""() => {
            const sel = document.querySelector('.selDisplayedItems');
            if (sel) { sel.value = '100'; sel.dispatchEvent(new Event('change')); }
        }""")
        await asyncio.sleep(3)

        rows = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
        print(f"Rows on page: {rows}")

        if rows == 0:
            # Take screenshot for debug
            await page.screenshot(path="ninja_debug.png")
            text = await page.evaluate("() => document.body.innerText.substring(0, 500)")
            print(f"Page text: {text[:300]}")
            await browser.close()
            return

        # Get 5 vehicles
        vehicles = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('[onclick*=seniCarDetail]').forEach(el => {
                const m = el.getAttribute('onclick').match(/seniCarDetail\\('(\\d+)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)'/);
                if (m && results.length < 5) results.push({ index: m[1], site: m[2], times: m[3], bidNo: m[4], zaikoNo: m[5] });
            });
            return results;
        }""")
        print(f"Test vehicles: {len(vehicles)}")

        # === TEST 1: New tab (baseline) ===
        print(f"\n=== TEST 1: New tab (1 vehicle) ===")
        v = vehicles[0]
        t0 = time.time()
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
        await asyncio.sleep(1)
        sheet = await dp.evaluate("""() => {
            for (const img of document.querySelectorAll('img'))
                if (img.src && img.src.includes('get_ex_image')) return img.src;
            return '';
        }""")
        await dp.close()
        t1 = time.time()
        print(f"  Time: {t1-t0:.2f}s | Sheet: {sheet[:80] if sheet else 'NONE'}")
        await page.evaluate("() => document.getElementById('form1').setAttribute('target', '')")

        # === TEST 2: Hidden iframe ===
        print(f"\n=== TEST 2: Hidden iframe (1 vehicle) ===")
        t0 = time.time()
        result = await page.evaluate("""(v) => {
            return new Promise((resolve) => {
                let iframe = document.getElementById('_sf');
                if (!iframe) {
                    iframe = document.createElement('iframe');
                    iframe.id = '_sf';
                    iframe.name = '_sf';
                    iframe.style.cssText = 'position:absolute;left:-9999px;width:1px;height:1px;';
                    document.body.appendChild(iframe);
                }
                iframe.onload = function() {
                    try {
                        const doc = iframe.contentDocument;
                        let s = '';
                        doc.querySelectorAll('img').forEach(img => {
                            if (img.src.includes('get_ex_image')) s = img.src;
                        });
                        resolve({ ok: true, sheet: s });
                    } catch(e) { resolve({ ok: false, error: e.message }); }
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
                setTimeout(() => resolve({ ok: false, error: 'timeout' }), 10000);
            });
        }""", v)
        t1 = time.time()
        print(f"  Time: {t1-t0:.2f}s | Result: {result}")
        await page.evaluate("() => document.getElementById('form1').setAttribute('target', '')")

        # === TEST 3: Sequential new tabs (3 vehicles) ===
        print(f"\n=== TEST 3: Sequential new tabs (3 vehicles) ===")
        t0 = time.time()
        for i, v in enumerate(vehicles[:3]):
            np = context.wait_for_event("page", timeout=10000)
            await page.evaluate("""(v) => {
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
            s = await dp.evaluate("""() => {
                for (const img of document.querySelectorAll('img'))
                    if (img.src && img.src.includes('get_ex_image')) return img.src;
                return '';
            }""")
            await dp.close()
            print(f"  Vehicle {i+1}: {'YES' if s else 'NO'}")
        t1 = time.time()
        print(f"  Total: {t1-t0:.2f}s for 3 vehicles")
        await page.evaluate("() => document.getElementById('form1').setAttribute('target', '')")

        # === TEST 4: Sequential iframes (3 vehicles) ===
        print(f"\n=== TEST 4: Sequential iframes (3 vehicles) ===")
        t0 = time.time()
        for i, v in enumerate(vehicles[:3]):
            r = await page.evaluate("""(v) => {
                return new Promise((resolve) => {
                    let iframe = document.getElementById('_sf');
                    if (!iframe) {
                        iframe = document.createElement('iframe');
                        iframe.id = '_sf'; iframe.name = '_sf';
                        iframe.style.cssText = 'position:absolute;left:-9999px;width:1px;height:1px;';
                        document.body.appendChild(iframe);
                    }
                    iframe.onload = function() {
                        try {
                            const doc = iframe.contentDocument;
                            let s = '';
                            doc.querySelectorAll('img').forEach(img => {
                                if (img.src.includes('get_ex_image')) s = img.src;
                            });
                            resolve(s);
                        } catch(e) { resolve(''); }
                    };
                    document.getElementById('kaijoCode').value = v.site;
                    document.getElementById('auctionCount').value = v.times;
                    document.getElementById('bidNo').value = v.bidNo;
                    document.getElementById('zaikoNo').value = '';
                    document.getElementById('action').value = 'init';
                    var form = document.getElementById('form1');
                    form.setAttribute('action', './cardetail.action');
                    form.setAttribute('target', '_sf');
                    form.submit();
                    setTimeout(() => resolve(''), 10000);
                });
            }""", v)
            print(f"  Vehicle {i+1}: {'YES' if r else 'NO'}")
        t1 = time.time()
        print(f"  Total: {t1-t0:.2f}s for 3 vehicles")
        await page.evaluate("() => document.getElementById('form1').setAttribute('target', '')")

        # Session check
        alive = await page.evaluate("() => !!document.getElementById('form1')")
        print(f"\nSession alive: {alive}")

        print(f"\n{'='*60}")
        print("DONE")
        print(f"{'='*60}")
        await browser.close()

asyncio.run(main())
