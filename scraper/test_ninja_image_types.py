"""Test: what imageKindType values produce car images?
Can we get multiple car photos from the list page without detail pages?
Run: cd scraper && python3 test_ninja_image_types.py
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

        # MAZDA
        await page.evaluate("() => seniBrand('10')")
        await asyncio.sleep(3)
        await page.evaluate("() => allSearch()")
        await asyncio.sleep(5)
        for _ in range(10):
            cnt = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
            if cnt > 0: break
            await asyncio.sleep(1)

        # Get first vehicle's image URL
        img_info = await page.evaluate("""() => {
            const img = document.querySelector('img[src*=get_car_image]');
            if (!img) return null;
            return { src: img.src, full: img.src };
        }""")

        if not img_info:
            print("No car image found!")
            await browser.close()
            return

        base_url = img_info['src']
        print(f"Base image URL: {base_url[:150]}")

        # Test imageKindType 1-20
        print(f"\n{'='*60}")
        print("imageKindType test (1-20)")
        print(f"{'='*60}")

        results = await page.evaluate("""async (baseUrl) => {
            const results = [];
            for (let kind = 1; kind <= 20; kind++) {
                const url = baseUrl.replace(/imageKindType=\\d+/, 'imageKindType=' + kind);
                try {
                    const res = await fetch(url, { credentials: 'include' });
                    const blob = await res.blob();
                    results.push({
                        kind,
                        status: res.status,
                        type: res.headers.get('content-type'),
                        size: blob.size,
                    });
                } catch(e) {
                    results.push({ kind, error: e.message });
                }
            }
            return results;
        }""", base_url)

        for r in results:
            if r.get('size', 0) > 1000:
                print(f"  imageKindType={r['kind']}: {r['size']} bytes ({r['type']}) ★ REAL IMAGE")
            elif r.get('size', 0) > 0:
                print(f"  imageKindType={r['kind']}: {r['size']} bytes ({r['type']})")
            else:
                print(f"  imageKindType={r['kind']}: {r.get('status', '?')} {r.get('error', '')}")

        # Also test: can we construct exhibit sheet URL from carKeyStr?
        print(f"\n{'='*60}")
        print("carKeyStr → exhibit sheet URL construction test")
        print(f"{'='*60}")

        car_key = await page.evaluate("""() => {
            const inp = document.querySelector('input[name^=carKeyStr]');
            return inp ? inp.value : '';
        }""")
        print(f"carKeyStr: {car_key}")

        if car_key:
            # Parse the carKeyStr: 1жYKж1087ж30203жж/auction/bid_image/...
            parts = car_key.split('ж')
            if len(parts) >= 6:
                filepath = parts[-1]  # The image path
                print(f"FilePath from carKeyStr: {filepath}")

                # Try get_ex_image with this filepath
                ex_url = f"https://www.ninja-cartrade.jp/ninja/cardetail.action?action=get_ex_image&FilePath={filepath}"
                result = await page.evaluate("""async (url) => {
                    try {
                        const res = await fetch(url, { credentials: 'include' });
                        const blob = await res.blob();
                        return { status: res.status, size: blob.size, type: res.headers.get('content-type') };
                    } catch(e) { return { error: e.message }; }
                }""", ex_url)
                print(f"get_ex_image with carKeyStr path: {result}")

                # Try common.action with get_ex_image
                ex_url2 = base_url.replace('get_car_image', 'get_ex_image')
                result2 = await page.evaluate("""async (url) => {
                    try {
                        const res = await fetch(url, { credentials: 'include' });
                        const blob = await res.blob();
                        return { status: res.status, size: blob.size, type: res.headers.get('content-type') };
                    } catch(e) { return { error: e.message }; }
                }""", ex_url2)
                print(f"common.action with get_ex_image: {result2}")

        # Test: can we get exhibit sheet via imageKindType on common.action?
        print(f"\n{'='*60}")
        print("Can common.action serve exhibit sheets?")
        print(f"{'='*60}")

        # Types that might be exhibit sheet: 0, 10, 11, 99, etc.
        for kind in [0, 10, 11, 12, 20, 50, 99]:
            url = base_url.replace('imageKindType=1', f'imageKindType={kind}')
            result = await page.evaluate("""async (url) => {
                try {
                    const res = await fetch(url, { credentials: 'include' });
                    const blob = await res.blob();
                    return { size: blob.size, type: res.headers.get('content-type') };
                } catch(e) { return { error: e.message }; }
            }""", url)
            if result.get('size', 0) > 1000:
                print(f"  imageKindType={kind}: {result['size']} bytes ★")
            else:
                print(f"  imageKindType={kind}: {result.get('size', 0)} bytes")

        print(f"\nSession alive: {await page.evaluate('() => !!document.getElementById(\"form1\")')}")
        await browser.close()

asyncio.run(main())
