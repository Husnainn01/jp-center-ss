"""Check actual image URLs on iAUC detail page.
Run: cd scraper && python3 test_backfill_imgs.py
"""

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from playwright.async_api import async_playwright
from iauc_login import iauc_login, iauc_logout


async def main():
    user_id = os.getenv("IAUC_USER_ID", "")
    password = os.getenv("IAUC_PASSWORD", "")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        print("Logging in...")
        ok = await iauc_login(page, user_id, password)
        if not ok:
            print("LOGIN FAILED!")
            await browser.close()
            return

        tid = await page.evaluate("""() => {
            for (const a of document.querySelectorAll('a[href*="__tid"]')) {
                const m = a.href.match(/__tid=([^&#]+)/);
                if (m) return m[1];
            }
            return '';
        }""")

        # Test with a few different vehicles
        test_vids = ["163-813-5007", "3-1832-36052", "89-2349-80016"]

        for vid in test_vids:
            print(f"\n{'='*60}")
            print(f"Vehicle: {vid}")
            print(f"{'='*60}")

            detail_page = await context.new_page()
            detail_url = f"https://www.iauc.co.jp/detail/?vehicleId={vid}&owner_id=&from=vehicle&id=&__tid={tid}"
            await detail_page.goto(detail_url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(3)

            if "detail" not in detail_page.url:
                print(f"  Failed to load detail page")
                await detail_page.close()
                continue

            # Dump ALL images on the page
            all_imgs = await detail_page.evaluate("""() => {
                return Array.from(document.querySelectorAll('img')).map(i => ({
                    src: i.src,
                    width: i.naturalWidth,
                    height: i.naturalHeight,
                    alt: i.alt || '',
                    className: i.className || '',
                    parentClass: i.parentElement?.className || '',
                })).filter(i => i.width > 50 || i.src.includes('iauc'));
            }""")

            print(f"\nAll significant images ({len(all_imgs)}):")
            for img in all_imgs:
                print(f"  [{img['width']}x{img['height']}] class='{img['className']}' parent='{img['parentClass']}'")
                print(f"    {img['src'][:120]}")

            # Also check for lazy-loaded or background images
            bg_imgs = await detail_page.evaluate("""() => {
                const results = [];
                document.querySelectorAll('[style*="background"], [data-src], [data-original]').forEach(el => {
                    const style = el.getAttribute('style') || '';
                    const dataSrc = el.getAttribute('data-src') || '';
                    const dataOrig = el.getAttribute('data-original') || '';
                    if (style.includes('url(') || dataSrc || dataOrig) {
                        results.push({
                            tag: el.tagName,
                            style: style.substring(0, 150),
                            dataSrc,
                            dataOriginal: dataOrig,
                            className: el.className,
                        });
                    }
                });
                return results;
            }""")

            if bg_imgs:
                print(f"\nLazy/background images ({len(bg_imgs)}):")
                for bg in bg_imgs:
                    print(f"  <{bg['tag']}> class='{bg['className']}'")
                    if bg['dataSrc']: print(f"    data-src: {bg['dataSrc'][:120]}")
                    if bg['dataOriginal']: print(f"    data-original: {bg['dataOriginal'][:120]}")
                    if bg['style']: print(f"    style: {bg['style'][:120]}")

            # Wait longer for lazy images to load
            await asyncio.sleep(5)

            # Re-check after wait
            after_wait = await detail_page.evaluate("""() => {
                return Array.from(document.querySelectorAll('img'))
                    .filter(i => i.naturalWidth > 100)
                    .map(i => ({ src: i.src, width: i.naturalWidth, height: i.naturalHeight }));
            }""")
            if len(after_wait) != len([i for i in all_imgs if i['width'] > 100]):
                print(f"\nAfter 5s wait — new images loaded:")
                for img in after_wait:
                    print(f"  [{img['width']}x{img['height']}] {img['src'][:120]}")

            await detail_page.close()

        await iauc_logout(page)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
