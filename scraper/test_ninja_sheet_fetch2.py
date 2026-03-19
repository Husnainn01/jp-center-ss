"""Test: Fetch detail via form2 fields, or use new tab approach."""

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

        # Get to results: ISUZU → BIGHORN
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
        print(f"[test] Searching: {target['name']} ({target['count']} vehicles)")
        await page.evaluate(f"() => makerListChoiceCarCat('{target['catId']}')")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(5)

        # Get first 3 vehicles
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
        print(f"[test] Found {len(vehicles)} vehicles to test")

        # === TEST 1: Fetch with form2 field names ===
        print(f"\n=== TEST 1: POST with form2 field names ===")
        v = vehicles[0]
        result = await page.evaluate("""async (v) => {
            try {
                const fd = new URLSearchParams();
                fd.append('language', '1');
                fd.append('action2', '');
                fd.append('site', '2');
                fd.append('memberCode', 'L4013');
                fd.append('branchCode', '001');
                fd.append('buyerId', 'V80');
                fd.append('kaijoCode2', v.site);
                fd.append('auctionCount2', v.times);
                fd.append('bidNo2', v.bidNo);
                fd.append('carKindType2', '1');
                fd.append('selectIndex', v.index);

                const res = await fetch('./cardetail.action', {
                    method: 'POST',
                    credentials: 'include',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: fd.toString()
                });
                const html = await res.text();
                const exMatches = [...html.matchAll(/get_ex_image[^"'\\s]*/g)].map(m => m[0]);
                return {
                    status: res.status,
                    len: html.length,
                    hasEx: html.includes('get_ex_image'),
                    exUrls: exMatches.slice(0, 2),
                    title: html.match(/<title>([^<]*)<\/title>/)?.[1] || '',
                };
            } catch(e) { return { error: e.message }; }
        }""", v)
        print(f"  Status: {result.get('status')}, len: {result.get('len')}, hasEx: {result.get('hasEx')}, title: {result.get('title')}")
        if result.get('exUrls'):
            for u in result['exUrls']:
                print(f"  ★ {u[:150]}")

        # === TEST 2: Use seniCarDetail JS source to understand form submission ===
        print(f"\n=== TEST 2: seniCarDetail function source ===")
        fn_src = await page.evaluate("""() => {
            if (typeof seniCarDetail === 'function') return seniCarDetail.toString();
            return 'not found';
        }""")
        print(f"  {fn_src[:800]}")

        # === TEST 3: New tab approach — open detail in separate tab ===
        print(f"\n=== TEST 3: New tab approach ===")
        for i, v in enumerate(vehicles[:2]):
            new_page = await context.new_page()
            try:
                # Clone session cookies are shared via context
                # Set form fields and submit in new page
                # First load the results page in new tab to get same state
                # Actually, try navigating directly using the JS call

                # Approach: go to search page, select maker, search, then detail
                # Too slow. Let's try: just evaluate seniCarDetail on a new page with the right URL

                # Better: use the form action URL with POST directly in the new page
                await new_page.goto("https://www.ninja-cartrade.jp/ninja/searchresultlist.action", wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(2)

                # Post the form data
                result = await new_page.evaluate("""async (v) => {
                    try {
                        const fd = new URLSearchParams();
                        fd.append('kaijoCode2', v.site);
                        fd.append('auctionCount2', v.times);
                        fd.append('bidNo2', v.bidNo);
                        fd.append('carKindType2', '1');
                        fd.append('language', '1');
                        fd.append('memberCode', 'L4013');
                        fd.append('branchCode', '001');
                        fd.append('buyerId', 'V80');

                        const res = await fetch('./cardetail.action', {
                            method: 'POST',
                            credentials: 'include',
                            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                            body: fd.toString()
                        });
                        const html = await res.text();
                        const exMatches = [...html.matchAll(/get_ex_image[^"'\\s]*/g)].map(m => m[0]);
                        return {
                            status: res.status,
                            len: html.length,
                            hasEx: html.includes('get_ex_image'),
                            exUrls: exMatches.slice(0, 2),
                        };
                    } catch(e) { return { error: e.message }; }
                }""", v)
                print(f"  Vehicle {v['bidNo']}: status={result.get('status')}, len={result.get('len')}, hasEx={result.get('hasEx')}")
                if result.get('exUrls'):
                    for u in result['exUrls']:
                        print(f"    ★ {u[:150]}")
            finally:
                await new_page.close()

        # Verify main page is still on list
        print(f"\n[test] Main page still on list? {page.url[:80]}")

        await browser.close()
        print("[test] Done!")

if __name__ == "__main__":
    asyncio.run(main())
