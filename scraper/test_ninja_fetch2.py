"""Test Ninja: try iframe-based and XMLHttpRequest approaches for sheet fetching.
Run: cd scraper && python3 test_ninja_fetch2.py
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
            await page.evaluate("""() => {
                for (const a of document.querySelectorAll('a'))
                    if (a.textContent.trim() === 'Login') { a.click(); return; }
            }""")
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(3)

        if "searchcondition" not in page.url:
            print("Login failed!")
            await browser.close()
            return
        print("Logged in!")

        # Select MINI and search
        await page.evaluate("() => seniBrand('56')")  # MINI
        await asyncio.sleep(3)
        await page.evaluate("() => allSearch()")
        await asyncio.sleep(5)

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
        print(f"Vehicles: {len(vehicles)}")

        if not vehicles:
            await browser.close()
            return

        v = vehicles[0]
        print(f"\nTest vehicle: bidNo={v['bidNo']} site={v['site']} times={v['times']}")

        # === TEST 1: New tab (current approach) — baseline ===
        print(f"\n--- TEST 1: New tab (baseline) ---")
        t0 = time.time()
        try:
            new_page_promise = context.wait_for_event("page", timeout=10000)
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
            detail_page = await new_page_promise
            await detail_page.wait_for_load_state("domcontentloaded", timeout=10000)
            await asyncio.sleep(1)

            sheet_url = await detail_page.evaluate("""() => {
                for (const img of document.querySelectorAll('img')) {
                    if (img.src && img.src.includes('get_ex_image')) return img.src;
                }
                return '';
            }""")

            # Get ALL image URLs for reference
            all_imgs = await detail_page.evaluate("""() => {
                return Array.from(document.querySelectorAll('img'))
                    .filter(i => i.src && !i.src.includes('spacer') && i.naturalWidth > 10)
                    .map(i => i.src.substring(0, 120));
            }""")

            await detail_page.close()
            t1 = time.time()
            print(f"  Time: {t1-t0:.2f}s")
            print(f"  Sheet: {sheet_url[:100] if sheet_url else 'NOT FOUND'}")
            print(f"  Images ({len(all_imgs)}):")
            for img in all_imgs[:5]:
                print(f"    {img}")

            # Reset form target
            await page.evaluate("() => document.getElementById('form1').setAttribute('target', '')")
        except Exception as e:
            t1 = time.time()
            print(f"  ERROR: {e} ({t1-t0:.2f}s)")
            for extra in context.pages[1:]:
                try: await extra.close()
                except: pass

        # === TEST 2: Hidden iframe ===
        print(f"\n--- TEST 2: Hidden iframe ---")
        t0 = time.time()
        result = await page.evaluate("""async (v) => {
            return new Promise((resolve) => {
                // Create hidden iframe
                let iframe = document.getElementById('_test_iframe');
                if (!iframe) {
                    iframe = document.createElement('iframe');
                    iframe.id = '_test_iframe';
                    iframe.style.display = 'none';
                    document.body.appendChild(iframe);
                }

                iframe.onload = function() {
                    try {
                        const doc = iframe.contentDocument || iframe.contentWindow.document;
                        const imgs = doc.querySelectorAll('img');
                        let sheetUrl = '';
                        const allImgs = [];
                        imgs.forEach(img => {
                            if (img.src.includes('get_ex_image')) sheetUrl = img.src;
                            if (img.src && !img.src.includes('spacer') && img.naturalWidth > 10) {
                                allImgs.push(img.src.substring(0, 120));
                            }
                        });
                        resolve({ success: true, sheetUrl, imgCount: allImgs.length, imgs: allImgs.slice(0, 5) });
                    } catch(e) {
                        resolve({ success: false, error: e.message });
                    }
                };

                // Submit form to iframe
                document.getElementById('carKindType').value = '1';
                document.getElementById('kaijoCode').value = v.site;
                document.getElementById('auctionCount').value = v.times;
                document.getElementById('bidNo').value = v.bidNo;
                document.getElementById('zaikoNo').value = '';
                document.getElementById('action').value = 'init';
                var form = document.getElementById('form1');
                form.setAttribute('action', './cardetail.action');
                form.setAttribute('target', '_test_iframe');
                form.submit();

                // Timeout after 10s
                setTimeout(() => resolve({ success: false, error: 'timeout' }), 10000);
            });
        }""", v)
        t1 = time.time()
        print(f"  Time: {t1-t0:.2f}s")
        print(f"  Result: {result}")

        # Reset form target
        await page.evaluate("() => document.getElementById('form1')?.setAttribute('target', '')")

        # === TEST 3: XHR with proper headers ===
        print(f"\n--- TEST 3: XHR with form submission headers ---")
        t0 = time.time()
        result = await page.evaluate("""async (v) => {
            document.getElementById('carKindType').value = '1';
            document.getElementById('kaijoCode').value = v.site;
            document.getElementById('auctionCount').value = v.times;
            document.getElementById('bidNo').value = v.bidNo;
            document.getElementById('zaikoNo').value = '';
            document.getElementById('action').value = 'init';
            const form = document.getElementById('form1');
            const fd = new FormData(form);

            try {
                const res = await fetch('./cardetail.action', {
                    method: 'POST',
                    credentials: 'include',
                    body: fd,  // Send as multipart/form-data (not URLSearchParams)
                });
                const html = await res.text();
                const hasEx = html.includes('get_ex_image');
                const exUrls = [...html.matchAll(/get_ex_image[^"']*/g)].map(m => m[0]);
                return { status: res.status, htmlLen: html.length, hasEx, exUrl: exUrls[0] || '' };
            } catch(e) {
                return { error: e.message };
            }
        }""", v)
        t1 = time.time()
        print(f"  Time: {t1-t0:.2f}s")
        print(f"  Result: {result}")

        # === Session check ===
        still_ok = await page.evaluate("""() => {
            return !document.body.innerText.includes('different user') &&
                   !!document.getElementById('form1');
        }""")
        print(f"\nSession alive: {still_ok}")

        print(f"\n{'='*60}")
        print("TEST COMPLETE")
        print(f"{'='*60}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
