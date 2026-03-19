"""Test: Submit form1 to a new tab to get exhibit sheet without leaving list page."""

import asyncio
from playwright.async_api import async_playwright
from ninja_login import ninja_login


async def main():
    user_id, password = "L4013V80", "93493493"
    print(f"[test] Logging in...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )

        ok = await ninja_login(context, user_id, password)
        if not ok:
            print("[test] Login failed!")
            await browser.close()
            return

        page = context.pages[0]

        # Get to results: ISUZU → small model
        await page.evaluate("() => seniBrand('17')")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(3)
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="bodytype"]').forEach(cb => { if (!cb.checked) cb.click(); });
        }""")
        await asyncio.sleep(0.5)
        models = await page.evaluate("""() => {
            const m = [];
            document.querySelectorAll('a').forEach(a => {
                const onclick = a.getAttribute('onclick') || '';
                const match = onclick.match(/makerListChoiceCarCat\\('(\\d+)'\\)/);
                if (match) {
                    const text = a.textContent.trim();
                    const cm = text.match(/(.+?)\\s*\\((\\d+)\\)/);
                    if (cm && parseInt(cm[2]) > 0) m.push({ name: cm[1], count: parseInt(cm[2]), catId: match[1] });
                }
            });
            return m;
        }""")
        target = next((m for m in models if 3 <= m['count'] <= 20), models[0])
        print(f"[test] Searching: {target['name']} ({target['count']})")
        await page.evaluate(f"() => makerListChoiceCarCat('{target['catId']}')")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(5)

        vehicles = await page.evaluate("""() => {
            const results = [];
            const seen = new Set();
            document.querySelectorAll('[onclick*=seniCarDetail]').forEach(el => {
                const m = el.getAttribute('onclick').match(/seniCarDetail\\('(\\d+)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)'/);
                if (m && !seen.has(m[4])) {
                    seen.add(m[4]);
                    results.push({ index: m[1], site: m[2], times: m[3], bidNo: m[4] });
                }
            });
            return results.slice(0, 3);
        }""")
        print(f"[test] Vehicles: {[v['bidNo'] for v in vehicles]}")

        # === Submit form1 to a NEW TAB ===
        print(f"\n=== Form1 submit to new tab ===")
        for v in vehicles:
            # Listen for new page
            new_page_promise = context.wait_for_event("page")

            # Set form fields and submit to new tab
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

            new_page = await new_page_promise
            await new_page.wait_for_load_state("networkidle", timeout=15000)
            await asyncio.sleep(1)

            # Extract exhibit sheet URL from new tab
            sheet_info = await new_page.evaluate("""() => {
                const imgs = document.querySelectorAll('img');
                const sheets = [];
                const cars = [];
                for (const img of imgs) {
                    if (!img.src || !img.src.startsWith('http')) continue;
                    if (img.src.includes('get_ex_image')) sheets.push(img.src);
                    else if (img.src.includes('get_image') || img.src.includes('get_car_image')) {
                        if (img.naturalWidth > 100) cars.push(img.src);
                    }
                }
                return { sheets, cars: cars.slice(0, 2) };
            }""")

            print(f"\n  Vehicle {v['bidNo']}:")
            print(f"    Exhibit sheets: {len(sheet_info['sheets'])}")
            if sheet_info['sheets']:
                print(f"    ★ Sheet URL: {sheet_info['sheets'][0][:150]}")
            print(f"    Car images: {len(sheet_info['cars'])}")

            await new_page.close()

            # Reset form target back to normal
            await page.evaluate("""() => {
                document.getElementById('form1').setAttribute('target', '');
            }""")

        # Verify main page is still on list
        print(f"\n[test] Main page URL: {page.url[:80]}")
        still_list = await page.evaluate("""() => {
            return document.querySelectorAll('[onclick*=seniCarDetail]').length;
        }""")
        print(f"[test] Vehicles still visible on list: {still_list}")

        await browser.close()
        print("\n[test] Done!")

if __name__ == "__main__":
    asyncio.run(main())
