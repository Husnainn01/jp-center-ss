"""Test: Can we fetch detail page HTML via fetch() and extract exhibit sheet URL
without actually navigating away from the list page?"""

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

        # Get to results page: ISUZU → small model
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

        print(f"[test] On results page: {page.url[:80]}")

        # Get first vehicle params
        first = await page.evaluate("""() => {
            const el = document.querySelector('[onclick*=seniCarDetail]');
            if (!el) return null;
            const onclick = el.getAttribute('onclick');
            const m = onclick.match(/seniCarDetail\\('(\\d+)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)'/);
            return m ? { index: m[1], site: m[2], times: m[3], bidNo: m[4] } : null;
        }""")
        print(f"[test] First vehicle: {first}")

        # === TEST: Fetch detail page HTML via fetch() without navigating ===
        print(f"\n=== Fetching detail page via AJAX (staying on list page) ===")

        # The detail page is loaded via form POST. Let's try to simulate it with fetch.
        # seniCarDetail submits a form. Let's check what form data it sends.
        form_info = await page.evaluate("""() => {
            // Check all forms on page
            const forms = document.querySelectorAll('form');
            const info = [];
            forms.forEach(f => {
                info.push({
                    name: f.name || f.id || '',
                    action: f.action || '',
                    method: f.method || '',
                    inputs: Array.from(f.querySelectorAll('input')).map(i => ({
                        name: i.name, type: i.type, value: i.value.substring(0, 50)
                    })).slice(0, 20)
                });
            });
            return info;
        }""")
        for f in form_info:
            print(f"\n  Form: name={f['name']} action={f['action'][:100]} method={f['method']}")
            for inp in f['inputs'][:10]:
                print(f"    <input name={inp['name']} type={inp['type']} value={inp['value']}")

        # === TEST: Open detail in a NEW TAB (doesn't affect main page) ===
        print(f"\n=== Opening detail in new tab ===")
        new_page = await context.new_page()
        # Navigate to detail directly - construct URL
        detail_url = f"https://www.ninja-cartrade.jp/ninja/cardetail.action"

        # Try POST with form data
        result = await page.evaluate("""async (params) => {
            try {
                const formData = new URLSearchParams();
                formData.append('selectIndex', params.index);
                formData.append('auctionSite', params.site);
                formData.append('auctionTimes', params.times);
                formData.append('bidNo', params.bidNo);

                const res = await fetch('./cardetail.action', {
                    method: 'POST',
                    credentials: 'include',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: formData.toString()
                });
                const html = await res.text();

                // Extract exhibit sheet URL from HTML
                const matches = [];
                const regex = /get_ex_image[^"']*/g;
                let m;
                while ((m = regex.exec(html)) !== null) {
                    matches.push(m[0]);
                }

                // Also check for car images
                const carMatches = [];
                const carRegex = /get_image[^"']*/g;
                while ((m = carRegex.exec(html)) !== null) {
                    carMatches.push(m[0]);
                }

                return {
                    status: res.status,
                    htmlLength: html.length,
                    hasExImage: html.includes('get_ex_image'),
                    exImageUrls: matches.slice(0, 3),
                    carImageUrls: carMatches.slice(0, 3),
                    snippet: html.substring(0, 300),
                };
            } catch(e) {
                return { error: e.message };
            }
        }""", first)

        print(f"  Result: status={result.get('status')}, htmlLength={result.get('htmlLength')}, hasExImage={result.get('hasExImage')}")
        if result.get('exImageUrls'):
            for url in result['exImageUrls']:
                print(f"  ★ Exhibit sheet: {url[:150]}")
        if result.get('carImageUrls'):
            for url in result['carImageUrls'][:2]:
                print(f"  Car image: {url[:150]}")
        if result.get('error'):
            print(f"  Error: {result['error']}")
        print(f"  Snippet: {result.get('snippet', '')[:200]}")

        # Verify we're still on the list page
        print(f"\n[test] Still on list page? URL: {page.url[:80]}")

        await new_page.close()
        await browser.close()
        print("[test] Done!")


if __name__ == "__main__":
    asyncio.run(main())
