"""Quick test: login, get one vehicle detail page, capture all images."""
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
        await page.goto("https://www.aucneostation.com/", wait_until="networkidle", timeout=30000)
        await page.fill("#userid-pc", "A124332")
        await page.fill("#password-pc", "Japanesemango1289")
        await page.click("button[type='submit']")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(2)
        if "login-error-force" in page.url:
            await page.click("input[name='force_login']")
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(3)

        buy = await page.evaluate("""() => {
            for (const a of document.querySelectorAll('a'))
                if (a.textContent.trim().includes('買いメニュー')) return a.href;
        }""")
        print("Logged in")

        # Load search, select all, search
        await page.goto(buy, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(8)
        await page.evaluate("() => document.querySelectorAll('.chk_makers').forEach(c => { if(!c.checked) c.click(); })")
        await asyncio.sleep(0.5)
        await page.evaluate("""() => {
            for (const a of document.querySelectorAll('a'))
                if (a.textContent.includes('この条件で一覧表示')) { a.click(); return; }
        }""")

        for _ in range(30):
            await asyncio.sleep(2)
            n = await page.evaluate("() => document.querySelectorAll('#results_list li[data-item_id]').length")
            if n > 0: break
        print(f"Got {n} results")

        # Get the first vehicle's item_id
        first_id = await page.evaluate("() => document.querySelector('#results_list li[data-item_id]')?.getAttribute('data-item_id')")
        print(f"First vehicle item_id: {first_id}")

        # Check what images are available in LIST view
        list_images = await page.evaluate("""() => {
            const li = document.querySelector('#results_list li[data-item_id]');
            if (!li) return [];
            const imgs = [];
            li.querySelectorAll('img').forEach(img => {
                if (img.src && img.src.startsWith('http')) imgs.push(img.src);
            });
            li.querySelectorAll('[data-expand-img]').forEach(el => {
                const url = el.getAttribute('data-expand-img');
                if (url) imgs.push(url);
            });
            return [...new Set(imgs)];
        }""")
        print(f"\nList view images ({len(list_images)}):")
        for img in list_images:
            print(f"  {img}")

        # Now click on the vehicle to open detail view
        print("\n=== OPENING DETAIL VIEW ===")
        await page.evaluate("""() => {
            const li = document.querySelector('#results_list li[data-item_id]');
            const link = li?.querySelector('.detailsLink');
            if (link) link.click();
        }""")
        await asyncio.sleep(5)

        # Check if a detail modal/page opened
        await page.screenshot(path="screenshot_detail.png", full_page=True)

        # Look for detail panel / modal
        detail_images = await page.evaluate("""() => {
            const imgs = new Set();

            // Check for detail modal/panel
            const selectors = [
                '.detail_view img', '.modal img', '.vehicle_detail img',
                '#detail img', '.detail img', '.popup img',
                '[class*="detail"] img', '[class*="gallery"] img',
                '[class*="photo"] img', '[class*="image"] img',
            ];

            for (const sel of selectors) {
                document.querySelectorAll(sel).forEach(img => {
                    if (img.src && img.src.startsWith('http')) imgs.add(img.src);
                });
            }

            // Also check data-expand-img in detail areas
            document.querySelectorAll('[class*="detail"] [data-expand-img], [class*="modal"] [data-expand-img]').forEach(el => {
                const url = el.getAttribute('data-expand-img');
                if (url) imgs.add(url);
            });

            // Grab ALL images on the page that are from aucnetcars
            document.querySelectorAll('img').forEach(img => {
                if (img.src && img.src.includes('aucnetcars.com')) imgs.add(img.src);
            });
            document.querySelectorAll('[data-expand-img]').forEach(el => {
                const url = el.getAttribute('data-expand-img');
                if (url && url.includes('aucnetcars.com')) imgs.add(url);
            });

            return Array.from(imgs);
        }""")

        print(f"\nAll aucnetcars images on page ({len(detail_images)}):")
        for img in detail_images:
            print(f"  {img}")

        # Check page structure for detail view
        detail_info = await page.evaluate("""() => {
            const result = {};
            // Check for visible sections that look like detail
            ['detail', 'modal', 'popup', 'overlay', 'gallery'].forEach(kw => {
                const els = document.querySelectorAll(`[class*="${kw}"]`);
                const visible = Array.from(els).filter(e => e.offsetParent !== null);
                if (visible.length > 0) {
                    result[kw] = visible.map(e => ({
                        tag: e.tagName,
                        class: e.className.substring(0, 80),
                        children: e.children.length,
                        visible: true,
                    }));
                }
            });
            return result;
        }""")
        print(f"\nDetail-like sections:")
        for kw, els in detail_info.items():
            for e in els:
                print(f"  [{kw}] <{e['tag']} class='{e['class']}'> children={e['children']}")

        await browser.close()

asyncio.run(main())
