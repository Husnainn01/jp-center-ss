"""Test: Fetch detail by serializing form1 with correct fields."""

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

        # === Serialize ALL form1 fields, set detail params, fetch via POST ===
        print(f"\n=== Fetch detail via form1 serialization ===")
        v = vehicles[0]
        result = await page.evaluate("""async (v) => {
            try {
                // Set the fields exactly like seniCarDetail does
                document.getElementById('carKindType').value = '1';
                document.getElementById('kaijoCode').value = v.site;
                document.getElementById('auctionCount').value = v.times;
                document.getElementById('bidNo').value = v.bidNo;
                document.getElementById('zaikoNo').value = '';
                document.getElementById('action').value = 'init';

                // Serialize form1
                const form = document.getElementById('form1');
                const fd = new FormData(form);
                const body = new URLSearchParams(fd).toString();

                const res = await fetch('./cardetail.action', {
                    method: 'POST',
                    credentials: 'include',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: body
                });

                const html = await res.text();

                // Extract exhibit sheet URLs
                const exMatches = [...html.matchAll(/get_ex_image&amp;FilePath=([^"&]*\\.JPG)/g)].map(m => m[1]);
                const exMatches2 = [...html.matchAll(/get_ex_image&FilePath=([^"&]*\\.JPG)/g)].map(m => m[1]);

                // Also try raw pattern
                const rawEx = [...html.matchAll(/get_ex_image[^"']*/g)].map(m => m[0]);

                return {
                    status: res.status,
                    len: html.length,
                    hasEx: html.includes('get_ex_image'),
                    hasCarImg: html.includes('get_image') || html.includes('get_car_image'),
                    exFilePaths: [...exMatches, ...exMatches2],
                    rawExUrls: rawEx.slice(0, 3),
                    snippet: html.substring(html.indexOf('get_ex_image') - 50, html.indexOf('get_ex_image') + 200),
                };
            } catch(e) { return { error: e.message, stack: e.stack }; }
        }""", v)

        print(f"  Status: {result.get('status')}")
        print(f"  HTML length: {result.get('len')}")
        print(f"  Has exhibit sheet: {result.get('hasEx')}")
        print(f"  Has car images: {result.get('hasCarImg')}")
        if result.get('exFilePaths'):
            for fp in result['exFilePaths']:
                print(f"  ★ FilePath: {fp[:150]}")
        if result.get('rawExUrls'):
            for u in result['rawExUrls']:
                print(f"  ★ Raw URL: {u[:200]}")
        if result.get('snippet'):
            print(f"  Snippet: {result['snippet'][:300]}")
        if result.get('error'):
            print(f"  Error: {result['error']}")

        # === Now test: can we download that exhibit sheet? ===
        if result.get('hasEx') and result.get('rawExUrls'):
            print(f"\n=== Downloading exhibit sheet ===")
            ex_path = result['rawExUrls'][0]
            # Construct full URL
            full_url = f"https://www.ninja-cartrade.jp/ninja/cardetail.action?action={ex_path}"
            dl_result = await page.evaluate("""async (url) => {
                try {
                    const res = await fetch(url, { credentials: 'include' });
                    const blob = await res.blob();
                    return { status: res.status, type: res.headers.get('content-type'), size: blob.size };
                } catch(e) { return { error: e.message }; }
            }""", full_url)
            print(f"  Download result: {dl_result}")

        # Verify main page unchanged
        print(f"\n[test] Main page URL: {page.url[:80]}")

        # Test with 2 more vehicles to confirm pattern
        for v in vehicles[1:]:
            result2 = await page.evaluate("""async (v) => {
                document.getElementById('carKindType').value = '1';
                document.getElementById('kaijoCode').value = v.site;
                document.getElementById('auctionCount').value = v.times;
                document.getElementById('bidNo').value = v.bidNo;
                document.getElementById('zaikoNo').value = '';
                document.getElementById('action').value = 'init';
                const form = document.getElementById('form1');
                const fd = new FormData(form);
                const body = new URLSearchParams(fd).toString();
                const res = await fetch('./cardetail.action', {
                    method: 'POST',
                    credentials: 'include',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: body
                });
                const html = await res.text();
                const rawEx = [...html.matchAll(/get_ex_image[^"']*/g)].map(m => m[0]);
                return { bidNo: v.bidNo, status: res.status, len: html.length, hasEx: html.includes('get_ex_image'), exUrls: rawEx.slice(0, 1) };
            }""", v)
            print(f"  Vehicle {result2.get('bidNo')}: status={result2.get('status')}, len={result2.get('len')}, hasEx={result2.get('hasEx')}")
            if result2.get('exUrls'):
                print(f"    ★ {result2['exUrls'][0][:150]}")

        await browser.close()
        print("\n[test] Done!")

if __name__ == "__main__":
    asyncio.run(main())
