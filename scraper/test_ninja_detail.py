"""Test: Login → search → click a vehicle to open detail → get ALL images."""
import asyncio
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
        await page.goto("https://www.ninja-cartrade.jp/ninja/", wait_until="networkidle", timeout=60000)
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
        print(f"    OK")

        # Search LEXUS (small maker, <1000 results)
        print("[2] LEXUS search...")
        await page.evaluate("""() => { for (const a of document.querySelectorAll('a')) { if (a.textContent.trim() === '・LEXUS') { a.click(); return; } } }""")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(3)
        await page.evaluate("() => conditionSearch()")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(3)
        # All models
        await page.evaluate("() => allSearch()")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(8)

        # Find the first car image and click it to open detail
        print("[3] Clicking first vehicle image...")

        # Get the onclick/href from the image's parent
        click_info = await page.evaluate("""() => {
            const imgs = Array.from(document.querySelectorAll('img'))
                .filter(i => i.src && i.src.includes('get_car_image'));
            if (!imgs.length) return null;

            const img = imgs[0];
            // Check parent chain for clickable elements
            let el = img;
            for (let i = 0; i < 5; i++) {
                const onclick = el.getAttribute('onclick') || '';
                const href = el.getAttribute('href') || '';
                if (onclick) return { type: 'onclick', value: onclick };
                if (href && href !== '#') return { type: 'href', value: href };
                el = el.parentElement;
                if (!el) break;
            }

            // Also check if the image itself is clickable
            return { type: 'info', tag: img.parentElement?.tagName, parentOnclick: img.parentElement?.getAttribute('onclick'), src: img.src.substring(0, 100) };
        }""")
        print(f"    Click info: {click_info}")

        # Try clicking the image directly
        print("[4] Direct click on image...")
        try:
            async with ctx.expect_page(timeout=10000) as popup_info:
                await page.evaluate("""() => {
                    const imgs = Array.from(document.querySelectorAll('img'))
                        .filter(i => i.src && i.src.includes('get_car_image'));
                    if (imgs[0]) {
                        // Click the image's parent link/td
                        let el = imgs[0];
                        while (el) {
                            if (el.tagName === 'A' || el.getAttribute('onclick')) {
                                el.click();
                                return;
                            }
                            el = el.parentElement;
                        }
                        // Just click the image
                        imgs[0].click();
                    }
                }""")
            popup = await popup_info.value
            await popup.wait_for_load_state("networkidle", timeout=15000)
            await asyncio.sleep(5)
            target = popup
            print(f"    Popup opened: {popup.url}")
        except Exception as e:
            print(f"    No popup: {e}")
            # Check if page navigated
            await asyncio.sleep(3)
            target = page
            print(f"    Current URL: {page.url}")

            # Check all pages
            if len(ctx.pages) > 1:
                target = ctx.pages[-1]
                await target.wait_for_load_state("networkidle", timeout=10000)
                await asyncio.sleep(3)
                print(f"    Last page URL: {target.url}")

        await target.screenshot(path="ninja_vehicle_detail.png", full_page=True)

        # Get ALL images from the detail page
        print("\n[5] Extracting ALL images from detail...")
        all_imgs = await target.evaluate("""() => {
            return Array.from(document.querySelectorAll('img'))
                .filter(i => i.src && i.src.startsWith('http'))
                .map(i => ({
                    src: i.src,
                    w: i.naturalWidth || i.width,
                    h: i.naturalHeight || i.height,
                    alt: i.alt || '',
                    parent: i.parentElement?.tagName || '',
                }))
                .filter(i => i.w > 30 || i.src.includes('car_image') || i.src.includes('photo') || i.src.includes('jpg'))
        }""")

        print(f"    Total images: {len(all_imgs)}")
        for img in all_imgs:
            is_car = 'car_image' in img['src'] or 'photo' in img['src'] or img['w'] > 100
            label = "CAR" if is_car else "ui"
            print(f"      [{label}] {img['w']}x{img['h']} {img['src'][:150]}")

        # Get page text
        text = await target.inner_text("body")
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        print(f"\n    Page text ({len(lines)} lines):")
        for line in lines[:40]:
            print(f"      {line[:120]}")

        # Save detail HTML
        html = await target.content()
        with open("ninja_detail_full.html", "w") as f:
            f.write(html)

        await browser.close()
        print("\n[Done]")

asyncio.run(main())
