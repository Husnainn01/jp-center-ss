"""Test iAUC: login → English → auctions → makers → search → extract a few vehicles."""

import asyncio
from playwright.async_api import async_playwright, Page


async def iauc_login(page: Page) -> bool:
    """Login to iAUC with force-login handling."""
    await page.goto("https://www.iauc.co.jp/service/", wait_until="networkidle", timeout=30000)
    await asyncio.sleep(2)

    await page.evaluate("""() => {
        document.querySelectorAll('a, button, div').forEach(el => {
            if ((el.textContent || '').trim().includes('LOGIN')) el.click();
        });
    }""")
    await asyncio.sleep(3)

    await page.fill('input[name="id"]', "A124332")
    await page.fill('input[name="password"]', "emlo4732")
    await page.evaluate("""() => {
        document.querySelectorAll('button, input, a').forEach(el => {
            const v = (el.value || el.textContent || '').trim();
            if (v.includes('LOGIN') || v.includes('ログイン')) el.click();
        });
    }""")
    await page.wait_for_load_state("networkidle", timeout=30000)
    await asyncio.sleep(3)

    body = await page.inner_text("body")
    if "はい Yes" in body:
        print("  [iauc] Force login — clicking Yes...")
        await page.click(".button-yes")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(5)

    return "vehicle" in page.url


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        # Login
        print("[test] Login...")
        ok = await iauc_login(page)
        if not ok:
            print("  FAILED!")
            await browser.close()
            return
        print(f"  OK: {page.url}")

        # Switch to English
        print("[test] English...")
        await page.evaluate("() => { const el = document.querySelector('a.jp'); if (el) el.click(); }")
        await page.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(3)

        # Uncheck Kyoyuzaiko, keep Auction
        print("[test] Select Auction only...")
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="e[]"]').forEach(cb => { if (cb.checked) cb.click(); });
        }""")
        await asyncio.sleep(1)
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="d[]"]').forEach(cb => { if (!cb.checked) cb.click(); });
        }""")
        await asyncio.sleep(1)

        # Click Next (bottom button)
        print("[test] Click Next to Make & Model...")
        await page.evaluate("""() => {
            const btns = document.querySelectorAll('a, button');
            for (const b of btns) {
                const text = (b.textContent || '').trim();
                const cls = b.className || '';
                // Look for the Next button at the bottom, not navigation items
                if ((text === 'Next >' || text === 'Next') && !cls.includes('navbar')) {
                    b.click();
                    return;
                }
            }
        }""")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(5)
        print(f"  URL: {page.url}")

        # Click "All" for Japanese makers
        print("[test] Select all Japanese makers...")
        await page.evaluate("""() => {
            // The "All" buttons are next to "Japanese" and "Imported" headings
            // They have specific classes — find maker section All buttons
            const allBtns = document.querySelectorAll('a');
            let clickedJp = false, clickedIm = false;
            for (const btn of allBtns) {
                const text = btn.textContent.trim();
                if (text === 'All' && !clickedJp) {
                    btn.click();
                    clickedJp = true;
                } else if (text === 'All' && clickedJp && !clickedIm) {
                    btn.click();
                    clickedIm = true;
                }
            }
        }""")
        await asyncio.sleep(3)

        makers_checked = await page.evaluate('() => document.querySelectorAll(\'input[name="maker[]"]:checked\').length')
        print(f"  Makers checked: {makers_checked}")

        # Click Next to search results
        print("[test] Click Next to search...")
        await page.evaluate("""() => {
            const btns = document.querySelectorAll('a, button');
            for (const b of btns) {
                const text = (b.textContent || '').trim();
                const cls = b.className || '';
                if ((text === 'Next >' || text === 'Next') && !cls.includes('navbar')) {
                    b.click();
                    return;
                }
            }
        }""")
        await page.wait_for_load_state("networkidle", timeout=60000)
        await asyncio.sleep(8)
        print(f"  URL: {page.url}")
        await page.screenshot(path="iauc_results.png", full_page=True)

        # Check results
        print("\n[test] Results page...")
        body = await page.inner_text("body")
        print(f"  Body (first 600):")
        print(body[:600])

        # Find vehicle rows with images
        vehicles = await page.evaluate("""() => {
            const results = [];
            // Look for vehicle items - they usually have car images
            document.querySelectorAll('img').forEach(img => {
                const src = img.src || '';
                if (src.includes('http') && (src.includes('photo') || src.includes('car') || src.includes('auction') || src.includes('/img/') || src.includes('vehicle')) &&
                    !src.includes('logo') && !src.includes('icon') && !src.includes('.gif') && img.width > 50) {
                    results.push({ src: src.substring(0, 120), width: img.width, height: img.height });
                }
            });
            return results;
        }""")
        print(f"\n  Car images ({len(vehicles)}):")
        for v in vehicles[:10]:
            print(f"    {v['width']}x{v['height']} {v['src']}")

        # Find clickable vehicle items
        detail_links = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('[onclick], a[href]').forEach(el => {
                const onclick = el.getAttribute('onclick') || '';
                const href = el.getAttribute('href') || '';
                if (onclick.includes('detail') || onclick.includes('Detail') ||
                    href.includes('detail') || href.includes('Detail') ||
                    onclick.includes('popup') || onclick.includes('car_id')) {
                    const text = (el.textContent || '').trim().substring(0, 60);
                    results.push({ text, onclick: onclick.substring(0, 100), href: href.substring(0, 80) });
                }
            });
            return results;
        }""")
        print(f"\n  Detail links ({len(detail_links)}):")
        for d in detail_links[:5]:
            print(f"    [{d['text'][:40]}]")
            if d['onclick']: print(f"      onclick={d['onclick']}")
            if d['href']: print(f"      href={d['href']}")

        # If we have detail links, open the first one
        if detail_links:
            print("\n[test] Opening first vehicle detail...")
            first = detail_links[0]
            if first['onclick']:
                # Check if it opens a popup
                try:
                    async with context.expect_page(timeout=10000) as popup_info:
                        await page.evaluate(f"() => {{ {first['onclick']} }}")
                    popup = await popup_info.value
                    await popup.wait_for_load_state("networkidle", timeout=15000)
                    await asyncio.sleep(3)

                    detail_text = await popup.inner_text("body")
                    print(f"  Detail text (first 800):")
                    print(detail_text[:800])

                    # Get images from detail
                    detail_imgs = await popup.evaluate("""() => {
                        const results = [];
                        document.querySelectorAll('img').forEach(img => {
                            const src = img.src || '';
                            if (src.includes('http') && img.width > 50 && !src.includes('.gif')) {
                                results.push({ src, width: img.width, height: img.height });
                            }
                        });
                        return results;
                    }""")
                    print(f"\n  Detail images ({len(detail_imgs)}):")
                    for img in detail_imgs[:10]:
                        print(f"    {img['width']}x{img['height']} {img['src'][:120]}")

                    await popup.screenshot(path="iauc_detail.png", full_page=True)
                    await popup.close()
                except Exception as e:
                    print(f"  Popup failed, trying direct navigation: {e}")
                    # Maybe it navigates the same page
                    await page.evaluate(f"() => {{ {first['onclick']} }}")
                    await page.wait_for_load_state("networkidle", timeout=15000)
                    await asyncio.sleep(3)
                    detail_text = await page.inner_text("body")
                    print(f"  Detail text (first 500): {detail_text[:500]}")

        await asyncio.sleep(3)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
