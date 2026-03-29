"""Check what image data is available on the Ninja list page.
Can we get more images without opening detail pages?
Run: cd scraper && python3 test_ninja_listpage_data.py
"""
import asyncio
import re
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

        # MAZDA (under 1000)
        await page.evaluate("() => seniBrand('10')")
        await asyncio.sleep(3)
        await page.evaluate("() => allSearch()")
        await asyncio.sleep(5)

        for _ in range(10):
            cnt = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
            if cnt > 0:
                break
            await asyncio.sleep(1)

        print(f"\n{'='*60}")
        print("LIST PAGE DATA ANALYSIS")
        print(f"{'='*60}")

        # Get FULL data for first 5 vehicles
        vehicles = await page.evaluate("""() => {
            const results = [];
            const seen = new Set();
            const rows = document.querySelectorAll('tr');

            for (const row of rows) {
                const detailLink = row.querySelector('[onclick*=seniCarDetail]');
                if (!detailLink) continue;
                const onclick = detailLink.getAttribute('onclick') || '';
                const match = onclick.match(/seniCarDetail\\('(\\d+)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)'/);
                if (!match) continue;
                const bidNo = match[4];
                if (seen.has(bidNo)) continue;
                seen.add(bidNo);

                // Get ALL images in this row
                const imgs = Array.from(row.querySelectorAll('img')).map(img => ({
                    src: img.src,
                    alt: img.alt || '',
                    width: img.naturalWidth,
                    height: img.naturalHeight,
                    className: img.className,
                })).filter(i => i.src && !i.src.includes('spacer') && !i.src.includes('common/'));

                // Get ALL hidden inputs
                const hiddens = {};
                row.querySelectorAll('input[type=hidden]').forEach(inp => {
                    hiddens[inp.name] = inp.value;
                });

                // Get ALL links
                const links = Array.from(row.querySelectorAll('a')).map(a => ({
                    href: a.href,
                    onclick: a.getAttribute('onclick')?.substring(0, 100) || '',
                    text: a.textContent.trim().substring(0, 30),
                })).filter(l => l.href.includes('get_') || l.onclick.includes('get_'));

                // Get ALL data attributes
                const dataAttrs = {};
                for (const attr of row.attributes) {
                    if (attr.name.startsWith('data-')) dataAttrs[attr.name] = attr.value;
                }

                // Get cell data
                const cells = Array.from(row.querySelectorAll('td')).map(td => td.innerText.trim());

                results.push({
                    bidNo,
                    site: match[2],
                    times: match[3],
                    imgs,
                    hiddens,
                    links,
                    dataAttrs,
                    cellCount: cells.length,
                });

                if (results.length >= 5) break;
            }
            return results;
        }""")

        print(f"\nVehicles analyzed: {len(vehicles)}")

        for v in vehicles:
            print(f"\n--- Vehicle bidNo={v['bidNo']} site={v['site']} ---")

            print(f"  Images ({len(v['imgs'])}):")
            for img in v['imgs']:
                is_car = 'get_car_image' in img['src'] or 'get_image' in img['src']
                is_sheet = 'get_ex_image' in img['src']
                marker = ' <<< CAR' if is_car else (' <<< SHEET' if is_sheet else '')
                print(f"    [{img['width']}x{img['height']}] {img['src'][:100]}{marker}")

            print(f"  Hidden inputs ({len(v['hiddens'])}):")
            for name, val in v['hiddens'].items():
                print(f"    {name} = {val[:80]}")

            if v['links']:
                print(f"  Links with get_:")
                for l in v['links']:
                    print(f"    {l['text']}: {l['href'][:100]}")

            if v['dataAttrs']:
                print(f"  Data attributes: {v['dataAttrs']}")

        # Check if carKeyStr can be used to construct image URLs
        print(f"\n{'='*60}")
        print("IMAGE URL PATTERN ANALYSIS")
        print(f"{'='*60}")

        for v in vehicles[:3]:
            car_key = v['hiddens'].get('carKeyStr', v['hiddens'].get('carKeyStr0', ''))
            if car_key:
                print(f"\n  bidNo={v['bidNo']}:")
                print(f"  carKeyStr: {car_key}")
                # Check if we can construct more image URLs from the pattern
                for img in v['imgs']:
                    if 'get_image' in img['src'] or 'get_car_image' in img['src']:
                        print(f"  Actual img URL: {img['src'][:150]}")
                        # Parse the URL
                        src = img['src']
                        if 'FilePath=' in src:
                            filepath = src.split('FilePath=')[1].split('&')[0]
                            print(f"  FilePath: {filepath}")

        # Check the full HTML around images for any patterns
        print(f"\n{'='*60}")
        print("CHECKING FOR ADDITIONAL IMAGE SOURCES")
        print(f"{'='*60}")

        extra = await page.evaluate("""() => {
            const html = document.body.innerHTML;
            // Check for image gallery/slideshow patterns
            const patterns = {
                get_image: (html.match(/get_image/g) || []).length,
                get_car_image: (html.match(/get_car_image/g) || []).length,
                get_ex_image: (html.match(/get_ex_image/g) || []).length,
                get_cpasimage: (html.match(/get_cpasimage/g) || []).length,
                FilePath: (html.match(/FilePath/g) || []).length,
                bid_image: (html.match(/bid_image/g) || []).length,
                carKeyStr: (html.match(/carKeyStr/g) || []).length,
            };

            // Check for onclick handlers that might load more images
            const imageHandlers = [];
            document.querySelectorAll('[onclick*=image], [onclick*=photo], [onclick*=enlarge]').forEach(el => {
                imageHandlers.push({
                    tag: el.tagName,
                    onclick: el.getAttribute('onclick')?.substring(0, 150) || '',
                    text: el.textContent.trim().substring(0, 50),
                });
            });

            // Check for any JavaScript that constructs image URLs
            const scripts = [];
            document.querySelectorAll('script').forEach(s => {
                const content = s.textContent;
                if (content.includes('get_image') || content.includes('FilePath') || content.includes('carKeyStr')) {
                    scripts.push(content.substring(0, 300));
                }
            });

            return { patterns, imageHandlers: imageHandlers.slice(0, 5), scripts: scripts.slice(0, 3) };
        }""")

        print(f"\nPattern counts in HTML:")
        for k, v in extra['patterns'].items():
            print(f"  {k}: {v} occurrences")

        if extra['imageHandlers']:
            print(f"\nImage-related onclick handlers:")
            for h in extra['imageHandlers']:
                print(f"  <{h['tag']}> {h['text']}: {h['onclick']}")

        if extra['scripts']:
            print(f"\nScripts mentioning images:")
            for s in extra['scripts']:
                print(f"  {s[:200]}")

        # Check if thumbnail click opens a larger image
        print(f"\n{'='*60}")
        print("THUMBNAIL CLICK TEST")
        print(f"{'='*60}")

        thumb_info = await page.evaluate("""() => {
            const imgs = document.querySelectorAll('img[src*=get_car_image], img[src*=get_image]');
            if (imgs.length === 0) return { count: 0 };
            const first = imgs[0];
            const parent = first.closest('a, [onclick]');
            return {
                count: imgs.length,
                thumbSrc: first.src.substring(0, 150),
                parentTag: parent ? parent.tagName : 'none',
                parentOnclick: parent ? (parent.getAttribute('onclick')?.substring(0, 200) || '') : '',
                parentHref: parent ? (parent.href?.substring(0, 150) || '') : '',
            };
        }""")
        print(f"  Thumbnails: {thumb_info['count']}")
        if thumb_info.get('thumbSrc'):
            print(f"  First thumb: {thumb_info['thumbSrc']}")
            print(f"  Parent: <{thumb_info['parentTag']}> onclick='{thumb_info['parentOnclick']}'")
            if thumb_info.get('parentHref'):
                print(f"  Parent href: {thumb_info['parentHref']}")

        await browser.close()

asyncio.run(main())
