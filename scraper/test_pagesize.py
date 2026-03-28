"""Check page size selector on iAUC results page.
Run: cd scraper && python3 test_pagesize.py
"""
import asyncio, os
from dotenv import load_dotenv
load_dotenv()
from playwright.async_api import async_playwright
from iauc_login import iauc_login

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()
        ok = await iauc_login(page, os.getenv("IAUC_USER_ID"), os.getenv("IAUC_PASSWORD"))
        if not ok: print("FAIL"); return

        # Select sites, go to maker page
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="d[]"]').forEach(cb => { if (!cb.checked) cb.click(); });
            document.querySelectorAll('input[name="e[]"]').forEach(cb => { if (!cb.checked) cb.click(); });
        }""")
        await asyncio.sleep(1)
        await page.evaluate('() => check_sites(document.querySelector(".page-next-button"))')
        for _ in range(20):
            await asyncio.sleep(2)
            if "#maker" in page.url: break
        await asyncio.sleep(3)

        # Select all makers and first big model
        await page.evaluate("""() => {
            const d = document.getElementById('maker-domestic-all');
            const f = document.getElementById('maker-foreign-all');
            if (d) d.click(); if (f) f.click();
        }""")
        await asyncio.sleep(2)
        await page.evaluate("""() => {
            const inputs = document.querySelectorAll('input[name="type[]"]');
            // Pick first model with > 500 count
            for (const inp of inputs) {
                if (parseInt(inp.getAttribute('data-cnt') || '0') > 500) {
                    if (!inp.checked) inp.click();
                    break;
                }
            }
        }""")
        await asyncio.sleep(1)

        # Search
        await page.evaluate('() => { var b = document.querySelector("#next-bottom"); if (b) { b.disabled = false; b.click(); } }')
        await asyncio.sleep(8)

        # Wait for results
        for _ in range(15):
            cnt = await page.evaluate("() => document.querySelectorAll('tr.scroll-anchor.line-auction').length")
            if cnt > 0: break
            await asyncio.sleep(1)

        rows = await page.evaluate("() => document.querySelectorAll('tr.scroll-anchor.line-auction').length")
        print(f"Results rows: {rows}")

        # Find ALL select elements
        selects = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('select')).map(s => ({
                id: s.id,
                name: s.name,
                className: s.className,
                visible: s.offsetParent !== null,
                options: Array.from(s.options).map(o => ({ value: o.value, text: o.text })),
                onchange: s.getAttribute('onchange') || '',
            }));
        }""")
        print(f"\nSelect elements: {len(selects)}")
        for s in selects:
            print(f"  id='{s['id']}' name='{s['name']}' class='{s['className']}' visible={s['visible']}")
            print(f"    onchange: {s['onchange'][:80]}")
            print(f"    options: {[o['value'] for o in s['options']]}")

        # Also check for select_limit specifically
        has_select_limit = await page.evaluate("() => !!document.getElementById('select_limit')")
        print(f"\nselect_limit exists: {has_select_limit}")

        # Check for any element that controls page size
        page_size_elements = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('[onclick*="limit"], [onchange*="limit"], [id*="limit"], [class*="limit"], [name*="limit"]').forEach(el => {
                results.push({
                    tag: el.tagName,
                    id: el.id,
                    name: el.name || '',
                    text: el.textContent.trim().substring(0, 50),
                    onchange: el.getAttribute('onchange')?.substring(0, 80) || '',
                });
            });
            return results;
        }""")
        if page_size_elements:
            print(f"\nElements with 'limit': {len(page_size_elements)}")
            for el in page_size_elements:
                print(f"  <{el['tag']}> id='{el['id']}' text='{el['text']}'")

        await browser.close()

asyncio.run(main())
