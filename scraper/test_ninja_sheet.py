"""Test: Find ways to get exhibit/auction sheet without going to detail page."""

import asyncio
from playwright.async_api import async_playwright
from ninja_login import ninja_login


async def main():
    user_id, password = "L4013V80", "93493493"

    print(f"[test] Logging in as {user_id}...")

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

        page = context.pages[0] if context.pages else await context.new_page()

        # Select ISUZU → GIGA (small set)
        await page.evaluate("() => seniBrand('17')")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(3)

        await page.evaluate("""() => {
            document.querySelectorAll('input[name="bodytype"]').forEach(cb => {
                if (!cb.checked) cb.click();
            });
        }""")
        await asyncio.sleep(0.5)

        # Find GIGA model
        models = await page.evaluate("""() => {
            const models = [];
            document.querySelectorAll('a').forEach(a => {
                const onclick = a.getAttribute('onclick') || '';
                const match = onclick.match(/makerListChoiceCarCat\\('(\\d+)'\\)/);
                if (match) {
                    const text = a.textContent.trim();
                    const countMatch = text.match(/(.+?)\\s*\\((\\d+)\\)/);
                    if (countMatch && parseInt(countMatch[2]) > 0) {
                        models.push({ name: countMatch[1], count: parseInt(countMatch[2]), catId: match[1] });
                    }
                }
            });
            return models;
        }""")

        target = next((m for m in models if 3 <= m['count'] <= 20), models[0])
        print(f"[test] Searching: {target['name']} ({target['count']} vehicles)")
        await page.evaluate(f"() => makerListChoiceCarCat('{target['catId']}')")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(5)

        # Get first vehicle's car image URL and carKeyStr
        first = await page.evaluate("""() => {
            const row = document.querySelector('tr:has([onclick*=seniCarDetail])');
            if (!row) return null;
            const img = row.querySelector('img[src*=get_car_image]');
            const key = row.querySelector('input[name^=carKeyStr]');
            const link = row.querySelector('[onclick*=seniCarDetail]');
            const onclick = link ? link.getAttribute('onclick') : '';
            const match = onclick.match(/seniCarDetail\\('(\\d+)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)'/);
            return {
                imgSrc: img ? img.src : '',
                keyVal: key ? key.value : '',
                params: match ? { index: match[1], site: match[2], times: match[3], bidNo: match[4] } : null,
            };
        }""")

        if not first:
            print("[test] No vehicle found!")
            await browser.close()
            return

        print(f"\n=== FIRST VEHICLE ===")
        print(f"Car image URL: {first['imgSrc'][:150]}")
        print(f"carKeyStr: {first['keyVal']}")
        print(f"Params: {first['params']}")

        # === TEST 1: Try changing action to get_ex_image ===
        print(f"\n=== TEST 1: get_ex_image with same params ===")
        if first['imgSrc']:
            ex_url = first['imgSrc'].replace('get_car_image', 'get_ex_image')
            result = await page.evaluate("""async (url) => {
                try {
                    const res = await fetch(url, { credentials: 'include' });
                    return { status: res.status, type: res.headers.get('content-type'), size: (await res.blob()).size };
                } catch(e) { return { error: e.message }; }
            }""", ex_url)
            print(f"  get_ex_image result: {result}")

        # === TEST 2: Try different imageKindType values ===
        print(f"\n=== TEST 2: Different imageKindType values ===")
        if first['imgSrc']:
            for kind in [2, 3, 4, 5, 6, 7, 8, 9, 10]:
                test_url = first['imgSrc'].replace('imageKindType=1', f'imageKindType={kind}')
                result = await page.evaluate("""async (url) => {
                    try {
                        const res = await fetch(url, { credentials: 'include' });
                        const blob = await res.blob();
                        return { kind: url.match(/imageKindType=(\\d+)/)[1], status: res.status, type: res.headers.get('content-type'), size: blob.size };
                    } catch(e) { return { error: e.message }; }
                }""", test_url)
                if result.get('size', 0) > 500:
                    print(f"  imageKindType={kind}: {result} ★ HAS CONTENT")
                else:
                    print(f"  imageKindType={kind}: {result}")

        # === TEST 3: Go to detail page and capture exhibit sheet URL pattern ===
        print(f"\n=== TEST 3: Detail page exhibit sheet URLs ===")
        params = first['params']
        await page.evaluate(f"() => seniCarDetail('{params['index']}', '{params['site']}', '{params['times']}', '{params['bidNo']}', '')")
        await page.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(2)

        all_imgs = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('img'))
                .filter(i => i.src && i.src.startsWith('http'))
                .map(i => ({ src: i.src, w: i.naturalWidth, h: i.naturalHeight }));
        }""")
        print(f"  Total images on detail page: {len(all_imgs)}")
        for img in all_imgs:
            tag = ""
            if 'get_ex_image' in img['src']:
                tag = " ★ EXHIBIT SHEET"
            elif 'get_car_image' in img['src'] or 'get_image' in img['src']:
                tag = " [car photo]"
            print(f"  {img['w']}x{img['h']} {img['src'][:160]}{tag}")

        # === TEST 4: Check all links/buttons on detail page for sheet-related actions ===
        print(f"\n=== TEST 4: Sheet-related elements on detail page ===")
        elements = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('a, button, img').forEach(el => {
                const text = (el.textContent || el.alt || '').trim();
                const onclick = el.getAttribute('onclick') || '';
                const src = el.src || el.href || '';
                if (text.toLowerCase().includes('sheet') || text.toLowerCase().includes('exhibit') ||
                    text.toLowerCase().includes('hyouka') || text.toLowerCase().includes('score') ||
                    onclick.includes('ex_image') || onclick.includes('hyouka') ||
                    src.includes('ex_image') || src.includes('hyouka')) {
                    results.push({ tag: el.tagName, text: text.substring(0, 80), onclick: onclick.substring(0, 200), src: src.substring(0, 200) });
                }
            });
            return results;
        }""")
        for el in elements:
            print(f"  <{el['tag']}> text='{el['text']}' onclick={el['onclick']} src={el['src']}")

        # === TEST 5: Full HTML dump of exhibit sheet image for URL pattern ===
        print(f"\n=== TEST 5: Exhibit sheet img full HTML ===")
        sheet_html = await page.evaluate("""() => {
            const imgs = document.querySelectorAll('img');
            for (const img of imgs) {
                if (img.src && img.src.includes('get_ex_image')) {
                    return { src: img.src, parentHTML: img.parentElement.outerHTML.substring(0, 500) };
                }
            }
            return null;
        }""")
        if sheet_html:
            print(f"  Full src: {sheet_html['src']}")
            print(f"  Parent HTML: {sheet_html['parentHTML']}")
        else:
            print("  No exhibit sheet image found on detail page")

        await browser.close()
        print("\n[test] Done!")


if __name__ == "__main__":
    asyncio.run(main())
