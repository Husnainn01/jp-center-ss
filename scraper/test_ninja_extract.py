"""Test: Login → TOYOTA PRIUS → Extract from rendered DOM + open detail."""
import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await ctx.new_page()

        # Login
        print("[1] Logging in...")
        await page.goto("https://www.ninja-cartrade.jp/ninja/", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)
        await page.fill("#loginId", "L4013V80")
        await page.fill("#password", "93493493")
        await page.evaluate("() => login()")
        await asyncio.sleep(5)
        body = await page.inner_text("body")
        if "different user" in body.lower():
            await page.evaluate("""() => { for (const a of document.querySelectorAll('a')) { if (a.textContent.trim() === 'Login') { a.click(); return; } } }""")
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(3)

        # TOYOTA → PRIUS
        print("[2] TOYOTA → PRIUS search...")
        await page.evaluate("""() => { for (const a of document.querySelectorAll('a')) { if (a.textContent.trim() === '・TOYOTA') { a.click(); return; } } }""")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(3)
        await page.evaluate("() => conditionSearch()")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(3)

        # Click PRIUS model
        await page.evaluate("""() => {
            const els = document.querySelectorAll('[onclick*=makerListCheckSearch]');
            for (const el of els) {
                if (el.textContent.includes('PRIUS') && el.textContent.match(/PRIUS \\(\\d+\\)/)) {
                    el.click(); return;
                }
            }
        }""")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(8)
        print(f"    URL: {page.url}")

        # Extract vehicles from rendered DOM
        print("\n[3] Extracting from DOM...")
        vehicles = await page.evaluate("""() => {
            const results = [];
            // Get all images on page
            const allImgs = document.querySelectorAll('img');
            const carImgs = Array.from(allImgs).filter(i =>
                i.src && i.src.includes('get_car_image') && i.naturalWidth > 50
            );

            // Each car image corresponds to a vehicle — get surrounding data
            for (const img of carImgs) {
                // Walk up to find the vehicle container (likely a table row or div)
                let container = img.closest('tr') || img.closest('div') || img.parentElement?.parentElement;
                if (!container) continue;

                // Get the full text block around this image
                // Try getting the parent table row and next few rows
                const parentRow = img.closest('tr');
                if (!parentRow) continue;

                const rows = [];
                let row = parentRow;
                for (let i = 0; i < 5 && row; i++) {
                    rows.push(row.textContent.trim());
                    row = row.nextElementSibling;
                }

                results.push({
                    image_src: img.src,
                    text_block: rows.join(' | ').substring(0, 500),
                    img_width: img.naturalWidth,
                    img_height: img.naturalHeight,
                    // Check for onclick on image or its parent
                    onclick: img.getAttribute('onclick') || img.parentElement?.getAttribute('onclick') || '',
                    parent_onclick: img.closest('a')?.getAttribute('onclick') || img.closest('[onclick]')?.getAttribute('onclick') || '',
                });
            }

            return results.slice(0, 5);
        }""")

        print(f"    Found {len(vehicles)} vehicles with images")
        for i, v in enumerate(vehicles[:5]):
            print(f"\n    === Vehicle {i+1} ===")
            print(f"    Image: {v['image_src'][:150]}")
            print(f"    Size: {v['img_width']}x{v['img_height']}")
            print(f"    onclick: {v['onclick'][:100]}")
            print(f"    parent_onclick: {v['parent_onclick'][:100]}")
            print(f"    Text: {v['text_block'][:200]}")

        # Try clicking the first vehicle image to open detail
        if vehicles and vehicles[0].get('parent_onclick'):
            print(f"\n[4] Clicking vehicle detail: {vehicles[0]['parent_onclick'][:80]}")
            try:
                async with ctx.expect_page(timeout=10000) as popup_info:
                    await page.evaluate(f"() => {{ {vehicles[0]['parent_onclick']} }}")
                popup = await popup_info.value
                await popup.wait_for_load_state("networkidle", timeout=15000)
                await asyncio.sleep(5)
            except Exception as e:
                print(f"    No popup: {e}")
                # Try clicking the image directly
                await page.evaluate("""() => {
                    const imgs = document.querySelectorAll('img');
                    for (const i of imgs) {
                        if (i.src.includes('get_car_image')) { i.click(); break; }
                    }
                }""")
                await asyncio.sleep(5)
                popup = ctx.pages[-1] if len(ctx.pages) > 1 else page

            print(f"    Detail URL: {popup.url}")
            await popup.screenshot(path="ninja_detail.png", full_page=True)

            # Get ALL images from detail page
            detail_imgs = await popup.evaluate("""() =>
                Array.from(document.querySelectorAll('img'))
                    .filter(i => i.src && i.naturalWidth > 30)
                    .map(i => ({ src: i.src.substring(0, 200), w: i.naturalWidth, h: i.naturalHeight }))
            """)
            print(f"    Detail images: {len(detail_imgs)}")
            for img in detail_imgs:
                print(f"      {img['w']}x{img['h']} {img['src']}")

            # Get detail page text
            detail_text = await popup.inner_text("body")
            detail_lines = [l.strip() for l in detail_text.split("\n") if l.strip()][:30]
            print(f"\n    Detail text:")
            for line in detail_lines:
                print(f"      {line[:120]}")

        await browser.close()
        print("\n[Done]")

asyncio.run(main())
