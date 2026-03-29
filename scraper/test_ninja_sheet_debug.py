"""Debug: compare new tab HTML vs iframe HTML for exhibit sheet detection.
Run: cd scraper && python3 test_ninja_sheet_debug.py
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

        # Get FIRST vehicle (deduplicated)
        v = await page.evaluate("""() => {
            const seen = new Set();
            for (const el of document.querySelectorAll('[onclick*=seniCarDetail]')) {
                const m = el.getAttribute('onclick').match(/seniCarDetail\\('(\\d+)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)'/);
                if (m && !seen.has(m[4])) {
                    seen.add(m[4]);
                    return { index: m[1], site: m[2], times: m[3], bidNo: m[4], zaikoNo: m[5] };
                }
            }
            return null;
        }""")
        print(f"Vehicle: bidNo={v['bidNo']} site={v['site']} times={v['times']}")

        # ===== METHOD 1: New tab — get full HTML and sheet URL =====
        print(f"\n{'='*60}")
        print("METHOD 1: New tab (baseline)")
        print(f"{'='*60}")
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
        await dp.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(2)

        tab_info = await dp.evaluate("""() => {
            const html = document.documentElement.innerHTML;
            const imgs = Array.from(document.querySelectorAll('img'))
                .filter(i => i.src.includes('get_ex_image'))
                .map(i => i.src);
            const htmlMatches = [...html.matchAll(/get_ex_image[^"']{0,200}/g)].map(m => m[0]);
            return {
                htmlLen: html.length,
                title: document.title,
                imgSheets: imgs,
                htmlSheets: htmlMatches,
                hasGetExInHtml: html.includes('get_ex_image'),
                bodyLen: document.body.innerText.length,
            };
        }""")
        await dp.close()
        await page.evaluate("() => document.getElementById('form1').setAttribute('target', '')")

        print(f"  HTML length: {tab_info['htmlLen']}")
        print(f"  Title: {tab_info['title']}")
        print(f"  Body text length: {tab_info['bodyLen']}")
        print(f"  get_ex_image in HTML: {tab_info['hasGetExInHtml']}")
        print(f"  Sheet from img tags: {len(tab_info['imgSheets'])}")
        for s in tab_info['imgSheets'][:2]:
            print(f"    {s[:120]}")
        print(f"  Sheet from HTML regex: {len(tab_info['htmlSheets'])}")
        for s in tab_info['htmlSheets'][:2]:
            print(f"    {s[:120]}")

        # ===== METHOD 2: Iframe — get HTML =====
        print(f"\n{'='*60}")
        print("METHOD 2: Iframe")
        print(f"{'='*60}")

        iframe_info = await page.evaluate("""(v) => {
            return new Promise((resolve) => {
                let f = document.getElementById('_debug_frame');
                if (!f) {
                    f = document.createElement('iframe');
                    f.id = '_debug_frame';
                    f.name = '_debug_frame';
                    f.style.cssText = 'position:absolute;left:-9999px;width:800px;height:600px';
                    document.body.appendChild(f);
                }
                f.onload = function() {
                    // Wait a bit for any JS to execute inside iframe
                    setTimeout(() => {
                        try {
                            const doc = f.contentDocument;
                            const html = doc.documentElement.innerHTML;
                            const imgs = Array.from(doc.querySelectorAll('img'))
                                .filter(i => i.src.includes('get_ex_image'))
                                .map(i => i.src);
                            const htmlMatches = [...html.matchAll(/get_ex_image[^"'\\s]{0,200}/g)].map(m => m[0]);
                            resolve({
                                htmlLen: html.length,
                                title: doc.title,
                                imgSheets: imgs,
                                htmlSheets: htmlMatches,
                                hasGetExInHtml: html.includes('get_ex_image'),
                                bodyLen: doc.body ? doc.body.innerText.length : 0,
                                bodySnippet: doc.body ? doc.body.innerText.substring(0, 200) : '',
                            });
                        } catch(e) {
                            resolve({ error: e.message });
                        }
                    }, 2000);  // Wait 2s for JS rendering
                };

                document.getElementById('carKindType').value = '1';
                document.getElementById('kaijoCode').value = v.site;
                document.getElementById('auctionCount').value = v.times;
                document.getElementById('bidNo').value = v.bidNo;
                document.getElementById('zaikoNo').value = '';
                document.getElementById('action').value = 'init';
                var form = document.getElementById('form1');
                form.setAttribute('action', './cardetail.action');
                form.setAttribute('target', '_debug_frame');
                form.submit();

                setTimeout(() => resolve({ error: 'timeout after 15s' }), 15000);
            });
        }""", v)
        await page.evaluate("() => document.getElementById('form1').setAttribute('target', '')")

        print(f"  HTML length: {iframe_info.get('htmlLen', '?')}")
        print(f"  Title: {iframe_info.get('title', '?')}")
        print(f"  Body text length: {iframe_info.get('bodyLen', '?')}")
        print(f"  get_ex_image in HTML: {iframe_info.get('hasGetExInHtml', '?')}")
        print(f"  Sheet from img tags: {len(iframe_info.get('imgSheets', []))}")
        for s in iframe_info.get('imgSheets', [])[:2]:
            print(f"    {s[:120]}")
        print(f"  Sheet from HTML regex: {len(iframe_info.get('htmlSheets', []))}")
        for s in iframe_info.get('htmlSheets', [])[:2]:
            print(f"    {s[:120]}")
        if iframe_info.get('bodySnippet'):
            print(f"  Body: {iframe_info['bodySnippet'][:150]}")
        if iframe_info.get('error'):
            print(f"  ERROR: {iframe_info['error']}")

        # Compare
        print(f"\n{'='*60}")
        print("COMPARISON")
        print(f"{'='*60}")
        tab_has = tab_info.get('hasGetExInHtml', False)
        iframe_has = iframe_info.get('hasGetExInHtml', False)
        print(f"  New tab has get_ex_image:  {tab_has}")
        print(f"  Iframe has get_ex_image:   {iframe_has}")
        if tab_has and not iframe_has:
            print(f"\n  >>> IFRAME IS MISSING THE SHEET!")
            print(f"  Tab HTML: {tab_info['htmlLen']} chars")
            print(f"  Iframe HTML: {iframe_info.get('htmlLen', '?')} chars")
            if iframe_info.get('htmlLen', 0) < tab_info['htmlLen'] / 2:
                print(f"  >>> Iframe HTML is much shorter — page likely didn't render fully")

        alive = await page.evaluate("() => !!document.getElementById('form1')")
        print(f"\nSession alive: {alive}")

        await browser.close()

asyncio.run(main())
