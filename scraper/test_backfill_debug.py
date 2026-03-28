"""Debug why backfill returns 0/200.
Tests: __tid availability, detail page access, image extraction.
Run: cd scraper && python3 test_backfill_debug.py
"""

import asyncio
import os
import re
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
        print("Logged in!\n")

        # === TEST 1: Check __tid on the search/home page (where backfill gets called) ===
        print("=== TEST 1: __tid on current page ===")
        current_url = page.url
        print(f"Current URL: {current_url}")

        tid_from_links = await page.evaluate("""() => {
            for (const a of document.querySelectorAll('a[href*="__tid"]')) {
                const m = a.href.match(/__tid=([^&#]+)/);
                if (m) return m[1];
            }
            return '';
        }""")
        print(f"__tid from links: {'FOUND: ' + tid_from_links[:20] + '...' if tid_from_links else 'NOT FOUND'}")

        tid_from_html = await page.evaluate("""() => {
            const m = document.body.innerHTML.match(/__tid=([a-f0-9]+)/);
            return m ? m[1] : '';
        }""")
        print(f"__tid from HTML: {'FOUND: ' + tid_from_html[:20] + '...' if tid_from_html else 'NOT FOUND'}")

        # === TEST 2: Navigate to search page (simulating end of scraper) ===
        print(f"\n=== TEST 2: Simulating post-scraper state ===")

        # Do a quick search to get to results page (like the scraper does)
        # Select all sites
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="d[]"]').forEach(cb => { if (!cb.checked) cb.click(); });
            document.querySelectorAll('input[name="e[]"]').forEach(cb => { if (!cb.checked) cb.click(); });
        }""")
        await asyncio.sleep(1)

        # Go to Make & Model
        await page.evaluate('() => check_sites(document.querySelector(".page-next-button"))')
        for _ in range(20):
            await asyncio.sleep(2)
            if "#maker" in page.url or "search" in page.url:
                break
        await asyncio.sleep(3)

        print(f"On Make & Model page: {page.url[:60]}...")
        search_base_url = page.url.split("#")[0]

        # Check __tid on Make & Model page
        tid_maker = await page.evaluate("""() => {
            for (const a of document.querySelectorAll('a[href*="__tid"]')) {
                const m = a.href.match(/__tid=([^&#]+)/);
                if (m) return m[1];
            }
            return '';
        }""")
        print(f"__tid on Make & Model page: {'FOUND: ' + tid_maker[:20] + '...' if tid_maker else 'NOT FOUND'}")

        tid_html_maker = await page.evaluate("""() => {
            const m = document.body.innerHTML.match(/__tid=([a-f0-9]+)/);
            return m ? m[1] : '';
        }""")
        print(f"__tid from HTML on Make & Model: {'FOUND: ' + tid_html_maker[:20] + '...' if tid_html_maker else 'NOT FOUND'}")

        # Use whatever tid we found
        tid = tid_from_links or tid_from_html or tid_maker or tid_html_maker
        if not tid:
            print("\nNO __tid found anywhere! This is why backfill fails.")
            print("The session page doesn't expose __tid after scraping.")
            await iauc_logout(page)
            await browser.close()
            return

        print(f"\nUsing __tid: {tid[:20]}...")

        # === TEST 3: Try opening a detail page ===
        print(f"\n=== TEST 3: Detail page access ===")
        # Use a known vehicle ID from the test earlier
        test_vid = "163-813-5007"
        detail_url = f"https://www.iauc.co.jp/detail/?vehicleId={test_vid}&owner_id=&from=vehicle&id=&__tid={tid}"
        print(f"Trying: {detail_url[:80]}...")

        detail_page = await context.new_page()
        await detail_page.goto(detail_url, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(3)

        detail_current = detail_page.url
        print(f"Landed on: {detail_current[:80]}")
        is_detail = "detail" in detail_current
        print(f"Is detail page: {is_detail}")

        if not is_detail:
            # Check if redirected to login or error
            body_text = await detail_page.evaluate("() => document.body.innerText.substring(0, 200)")
            print(f"Page content: {body_text[:200]}")
            await detail_page.close()

            # Try without __tid
            print(f"\nTrying WITHOUT __tid...")
            detail_url2 = f"https://www.iauc.co.jp/detail/?vehicleId={test_vid}"
            detail_page2 = await context.new_page()
            await detail_page2.goto(detail_url2, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(3)
            print(f"Landed on: {detail_page2.url[:80]}")
            print(f"Is detail: {'detail' in detail_page2.url}")
            await detail_page2.close()
        else:
            # === TEST 4: Image extraction on detail page ===
            print(f"\n=== TEST 4: Image extraction ===")

            all_imgs = await detail_page.evaluate("""() => {
                return Array.from(document.querySelectorAll('img')).map(i => ({
                    src: i.src,
                    width: i.naturalWidth,
                    height: i.naturalHeight,
                    hasIaucPic: i.src.includes('iauc_pic'),
                }));
            }""")

            iauc_imgs = [i for i in all_imgs if i['hasIaucPic']]
            print(f"Total images on page: {len(all_imgs)}")
            print(f"iAUC images (iauc_pic): {len(iauc_imgs)}")

            for img in iauc_imgs:
                size_ok = img['width'] > 100
                print(f"  {'OK' if size_ok else 'TOO SMALL'} [{img['width']}x{img['height']}] {img['src'][:100]}")

            # Check with the exact filter used by backfill
            filtered = await detail_page.evaluate("""() => {
                const placeholders = ['now_printing', 'noimage', 'no_image', 'dummy', 'blank', 'placeholder'];
                return Array.from(document.querySelectorAll('img'))
                    .filter(i => {
                        if (!i.src || !i.src.includes('iauc_pic') || i.naturalWidth <= 100) return false;
                        const lower = i.src.toLowerCase();
                        return !placeholders.some(p => lower.includes(p));
                    })
                    .map(i => ({ src: i.src, width: i.naturalWidth }));
            }""")
            print(f"\nAfter backfill filter (iauc_pic + width>100 + no placeholders): {len(filtered)}")
            for f in filtered:
                print(f"  [{f['width']}px] {f['src'][:100]}")

            # === TEST 5: Try downloading one image ===
            if filtered:
                print(f"\n=== TEST 5: Image download test ===")
                test_url = filtered[0]['src']
                dl_result = await detail_page.evaluate("""async (url) => {
                    try {
                        const res = await fetch(url, { credentials: 'include' });
                        if (!res.ok) return { ok: false, status: res.status };
                        const blob = await res.blob();
                        return { ok: true, size: blob.size, type: blob.type };
                    } catch (e) { return { ok: false, error: e.message }; }
                }""", test_url)
                print(f"Download result: {dl_result}")

            await detail_page.close()

        print(f"\n{'='*60}")
        print("BACKFILL DEBUG COMPLETE")
        print(f"{'='*60}")

        await iauc_logout(page)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
