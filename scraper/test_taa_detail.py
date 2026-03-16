"""Test: Login → Search → Click first vehicle detail → Capture images."""
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
        await page.goto("https://taacaa.jp/index-e.html", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)
        await page.fill("#kainNo", "CN5005")
        await page.fill("#kainTantoId", "xxund7qt")
        await page.fill("#password", "L57Sxyqha4B4")
        await page.evaluate("() => loginAction()")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(2)
        body = await page.inner_text("body")
        if "already logged" in body.lower():
            await page.evaluate("() => compulsionLogin()")
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(3)
        print(f"    OK: {page.url}")

        # Navigate to search
        print("[2] Going to search...")
        await page.evaluate("""() => {
            const img = document.querySelector('img[name="navi01"]');
            if (img) img.closest('a')?.click();
        }""")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(3)

        # Select all makers + models + submit
        print("[3] Selecting all + searching...")
        await page.evaluate("() => document.querySelectorAll('input[name=\"carMakerArr\"]').forEach(cb => { if(!cb.checked) cb.click(); })")
        await asyncio.sleep(2)
        await page.evaluate("() => document.querySelectorAll('input[name=\"syasyu2\"]').forEach(cb => { if(!cb.checked) cb.click(); })")
        await asyncio.sleep(1)
        await page.evaluate("""() => {
            var fm = document.getElementById("SearchForm");
            fm.action = "./CarListSpecification.do";
            if (typeof formAddKey === 'function') formAddKey(fm);
            fm.submit();
        }""")
        await page.wait_for_load_state("networkidle", timeout=60000)
        await asyncio.sleep(5)
        print(f"    Results: {page.url}")

        # Click first vehicle detail popup
        print("\n[4] Opening first vehicle detail...")

        # Listen for popup windows
        async with ctx.expect_page(timeout=15000) as popup_info:
            await page.evaluate("() => popDetail(1)")

        try:
            popup = await popup_info.value
            await popup.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(5)
            print(f"    Popup URL: {popup.url}")
            await popup.screenshot(path="taa_detail_popup.png", full_page=True)

            # Find ALL images
            images = await popup.evaluate("""() => {
                const imgs = [];
                document.querySelectorAll('img').forEach(img => {
                    const src = img.src || '';
                    if (src && src.startsWith('http') && !src.includes('icon') && !src.includes('btn_') && !src.includes('logo') && !src.includes('.gif')) {
                        imgs.push(src);
                    }
                });
                // Also check background images and data attributes
                document.querySelectorAll('[style*=background], [data-src], [data-original]').forEach(el => {
                    const bg = el.style.backgroundImage;
                    if (bg) {
                        const url = bg.match(/url\\(['\"]?([^'\"\\)]+)/);
                        if (url) imgs.push(url[1]);
                    }
                    ['data-src', 'data-original', 'data-img'].forEach(attr => {
                        const v = el.getAttribute(attr);
                        if (v && v.startsWith('http')) imgs.push(v);
                    });
                });
                return [...new Set(imgs)];
            }""")
            print(f"    Images found: {len(images)}")
            for img in images:
                print(f"      {img[:120]}")

            # Get all text data
            text = await popup.inner_text("body")
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            print(f"\n    Detail text ({len(lines)} lines):")
            for line in lines[:30]:
                print(f"      {line[:100]}")

            # Save HTML
            html = await popup.content()
            with open("taa_detail.html", "w") as f:
                f.write(html)
            print("\n    HTML saved: taa_detail.html")

        except Exception as e:
            print(f"    No popup opened: {e}")
            # Maybe it opens in same page or iframe
            await page.screenshot(path="taa_detail_same.png", full_page=True)
            iframes = await page.query_selector_all("iframe")
            print(f"    Iframes on page: {len(iframes)}")

        await browser.close()
        print("\n[Done]")

asyncio.run(main())
