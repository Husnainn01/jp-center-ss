"""Test the batch reload scenario — simulates what happens after Batch 2.
Selects sites → makers → searches Batch 1 → reloads maker page → tries Batch 2.
Tests: maker selection survives reload, page size selector works on batch 2.

Run: cd scraper && python3 test_batch_reload.py
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
        print("Logged in!\n")

        # === Select all sites ===
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="d[]"]').forEach(cb => { if (!cb.checked) cb.click(); });
            document.querySelectorAll('input[name="e[]"]').forEach(cb => { if (!cb.checked) cb.click(); });
        }""")
        await asyncio.sleep(1)
        await page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('a.day-button4g, button.day-button4g'));
            for (const b of btns) {
                if (b.textContent.trim().toUpperCase() === 'TODAY' && b.offsetParent !== null) { b.click(); return; }
            }
        }""")
        await asyncio.sleep(1)

        # === Go to Make & Model ===
        await page.evaluate('() => check_sites(document.querySelector(".page-next-button"))')
        for _ in range(20):
            await asyncio.sleep(2)
            if "#maker" in page.url:
                break
        await asyncio.sleep(3)

        search_base_url = page.url.split("#")[0]
        print(f"Search URL: {search_base_url[:60]}...")

        # =============================================
        # BATCH 1: Select makers + pick a small model
        # =============================================
        print(f"\n{'='*60}")
        print("BATCH 1: Initial selection")
        print(f"{'='*60}")

        # Select makers using the FIXED logic
        await page.evaluate("""() => {
            const d = document.getElementById('maker-domestic-all');
            const f = document.getElementById('maker-foreign-all');
            if (d) d.click();
            if (f) f.click();
        }""")
        await asyncio.sleep(2)
        makers1 = await page.evaluate("""() => document.querySelectorAll('input[name="maker[]"]:checked').length""")
        print(f"Makers selected: {makers1}")

        if makers1 == 0:
            print("Fallback: direct checkbox click...")
            await page.evaluate("""() => {
                document.querySelectorAll('input[name="maker[]"]').forEach(cb => { if (!cb.checked) cb.click(); });
            }""")
            await asyncio.sleep(1)
            makers1 = await page.evaluate("""() => document.querySelectorAll('input[name="maker[]"]:checked').length""")
            print(f"After fallback: {makers1}")

        # Pick first model with >500 count
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="type[]"]:checked').forEach(i => i.click());
        }""")
        await asyncio.sleep(0.5)
        await page.evaluate("""() => {
            for (const inp of document.querySelectorAll('input[name="type[]"]')) {
                if (parseInt(inp.getAttribute('data-cnt') || '0') > 500) {
                    if (!inp.checked) inp.click();
                    return;
                }
            }
        }""")
        await asyncio.sleep(1)

        # Search
        await page.evaluate('() => { var b = document.querySelector("#next-bottom"); if (b) { b.disabled = false; b.click(); } }')
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass
        await asyncio.sleep(4)

        for _ in range(10):
            cnt = await page.evaluate("() => document.querySelectorAll('tr.scroll-anchor.line-auction').length")
            if cnt > 0:
                break
            await asyncio.sleep(1)

        rows1 = await page.evaluate("() => document.querySelectorAll('tr.scroll-anchor.line-auction').length")
        has_selector1 = await page.evaluate("() => !!document.getElementById('select_limit')")
        print(f"Results: {rows1} rows")
        print(f"Page size selector: {'FOUND' if has_selector1 else 'NOT FOUND'}")

        # =============================================
        # BATCH 2: Reload Make & Model (same as scraper does)
        # =============================================
        print(f"\n{'='*60}")
        print("BATCH 2: After reload (OLD way — just goto + sleep 3)")
        print(f"{'='*60}")

        search_url = search_base_url + "#maker"
        await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(3)  # OLD: only 3 seconds

        makers2_before = await page.evaluate("""() => document.querySelectorAll('input[name="maker[]"]').length""")
        print(f"Maker checkboxes on page (OLD wait): {makers2_before}")

        # Try All buttons
        await page.evaluate("""() => {
            const d = document.getElementById('maker-domestic-all');
            const f = document.getElementById('maker-foreign-all');
            if (d) d.click();
            if (f) f.click();
        }""")
        await asyncio.sleep(2)
        makers2 = await page.evaluate("""() => document.querySelectorAll('input[name="maker[]"]:checked').length""")
        print(f"Makers checked (OLD way): {makers2}")

        # =============================================
        # BATCH 3: Reload Make & Model (NEW way — wait for checkboxes)
        # =============================================
        print(f"\n{'='*60}")
        print("BATCH 3: After reload (NEW way — wait for checkboxes)")
        print(f"{'='*60}")

        await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)

        # NEW: Wait for maker checkboxes to render
        for attempt in range(15):
            await asyncio.sleep(1)
            maker_count = await page.evaluate("""() => document.querySelectorAll('input[name="maker[]"]').length""")
            if maker_count > 0:
                print(f"Maker checkboxes appeared after {attempt + 1}s: {maker_count}")
                break
        else:
            print(f"Maker checkboxes NEVER appeared after 15s!")

        await asyncio.sleep(1)

        # Try All buttons
        await page.evaluate("""() => {
            const d = document.getElementById('maker-domestic-all');
            const f = document.getElementById('maker-foreign-all');
            if (d) d.click();
            if (f) f.click();
        }""")
        await asyncio.sleep(2)
        makers3 = await page.evaluate("""() => document.querySelectorAll('input[name="maker[]"]:checked').length""")
        print(f"Makers checked (NEW way): {makers3}")

        if makers3 == 0:
            print("Fallback: direct checkbox click...")
            await page.evaluate("""() => {
                document.querySelectorAll('input[name="maker[]"]').forEach(cb => { if (!cb.checked) cb.click(); });
            }""")
            await asyncio.sleep(1)
            makers3 = await page.evaluate("""() => document.querySelectorAll('input[name="maker[]"]:checked').length""")
            print(f"After fallback: {makers3}")

        # Pick a different model and search
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="type[]"]:checked').forEach(i => i.click());
        }""")
        await asyncio.sleep(0.5)
        # Pick second model
        await page.evaluate("""() => {
            const inputs = Array.from(document.querySelectorAll('input[name="type[]"]'));
            const sorted = inputs.filter(i => parseInt(i.getAttribute('data-cnt') || '0') > 200);
            if (sorted.length > 1 && !sorted[1].checked) sorted[1].click();
            else if (sorted.length > 0 && !sorted[0].checked) sorted[0].click();
        }""")
        await asyncio.sleep(1)

        await page.evaluate('() => { var b = document.querySelector("#next-bottom"); if (b) { b.disabled = false; b.click(); } }')
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass
        await asyncio.sleep(4)

        for _ in range(10):
            cnt = await page.evaluate("() => document.querySelectorAll('tr.scroll-anchor.line-auction').length")
            if cnt > 0:
                break
            await asyncio.sleep(1)

        rows3 = await page.evaluate("() => document.querySelectorAll('tr.scroll-anchor.line-auction').length")
        has_selector3 = await page.evaluate("() => !!document.getElementById('select_limit')")
        print(f"Results: {rows3} rows")
        print(f"Page size selector: {'FOUND' if has_selector3 else 'NOT FOUND'}")

        # =============================================
        # SUMMARY
        # =============================================
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"Batch 1 (fresh):      {makers1} makers, {rows1} rows, selector={'YES' if has_selector1 else 'NO'}")
        print(f"Batch 2 (OLD reload): {makers2} makers (3s wait)")
        print(f"Batch 3 (NEW reload): {makers3} makers, {rows3} rows, selector={'YES' if has_selector3 else 'NO'}")

        if makers3 > 0 and has_selector3:
            print("\nFIX WORKS!")
        elif makers3 > 0:
            print("\nMakers fixed, but page size selector still missing")
        else:
            print("\nSTILL BROKEN — need different approach")

        await iauc_logout(page)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
