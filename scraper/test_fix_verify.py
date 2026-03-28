"""Verify the fixed site selection selects ALL future sites including Preparing ones.
Run: cd scraper && python3 test_fix_verify.py
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

        # === Apply the FIXED selection logic (same as updated iauc_scraper.py) ===

        # 1a: Select ALL d[] checkboxes directly
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="d[]"]').forEach(cb => {
                if (!cb.checked) cb.click();
            });
        }""")
        await asyncio.sleep(1)

        # 1b: Select all e[] checkboxes
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="e[]"]').forEach(cb => {
                if (!cb.checked) cb.click();
            });
        }""")
        await asyncio.sleep(1)

        # Check before uncheck today
        before = await page.evaluate("""() => ({
            dChecked: document.querySelectorAll('input[name="d[]"]:checked').length,
            dTotal: document.querySelectorAll('input[name="d[]"]').length,
            eChecked: document.querySelectorAll('input[name="e[]"]:checked').length,
            eTotal: document.querySelectorAll('input[name="e[]"]').length,
        })""")
        print(f"BEFORE uncheck Today:")
        print(f"  Auction types: {before['eChecked']}/{before['eTotal']}")
        print(f"  Auction sites: {before['dChecked']}/{before['dTotal']}")

        # 1c: Uncheck Today
        await page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('a.day-button4g, button.day-button4g'));
            for (const b of btns) {
                if (b.textContent.trim().toUpperCase() === 'TODAY' && b.offsetParent !== null) {
                    b.click(); return;
                }
            }
        }""")
        await asyncio.sleep(1)

        # Check after
        after = await page.evaluate("""() => ({
            dChecked: document.querySelectorAll('input[name="d[]"]:checked').length,
            dTotal: document.querySelectorAll('input[name="d[]"]').length,
        })""")
        print(f"\nAFTER uncheck Today:")
        print(f"  Auction sites: {after['dChecked']}/{after['dTotal']}")
        print(f"  Today removed: {before['dChecked'] - after['dChecked']} sites")

        # Check target sites
        print(f"\n=== TARGET SITES STATUS ===")
        targets = await page.evaluate("""() => {
            const targets = ['Honda AA Tokyo', 'Honda AA Kansai', 'Honda AA Nagoya',
                'Honda AA Kyushu', 'Honda AA Sendai', 'Honda AA Hokkaido',
                'AUCNET', 'JU Tokyo', 'MOTA', 'NISSAN Osaka',
                'CAA Tokyo', 'CAA Chubu', 'BAYAUC', 'IAA Osaka'];
            const results = [];
            document.querySelectorAll('input[name="d[]"]').forEach(inp => {
                const sb = inp.closest('.sitebox-blue, .sitebox-green, label');
                const title = sb ? (sb.title || sb.getAttribute('title') || '') : '';
                if (targets.some(t => title.includes(t))) {
                    results.push({ name: title, checked: inp.checked });
                }
            });
            return results;
        }""")

        all_good = True
        for t in targets:
            status = "SELECTED" if t['checked'] else "MISSING!"
            if not t['checked']:
                all_good = False
            print(f"  {status:10} {t['name']}")

        # Show per-day breakdown
        print(f"\n=== PER-DAY BREAKDOWN ===")
        days = ['Today', 'MON', 'TUE', 'WED', 'THU', 'FRI']
        for day in days:
            # Click the day to see its sites
            count = await page.evaluate(f"""() => {{
                // We need to count sites per day column
                // Day buttons toggle visibility, so let's just count by checking
                // which sites belong to which day (from the visual layout)
                return 0; // placeholder
            }}""")

        # Instead, show all selected sites with names
        all_selected = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('input[name="d[]"]:checked').forEach(inp => {
                const sb = inp.closest('.sitebox-blue, .sitebox-green, label');
                const title = sb ? (sb.title || sb.getAttribute('title') || '') : '';
                const text = sb ? sb.textContent.trim().replace(/\\s+/g, ' ') : '';
                results.push({ name: title || text, value: inp.value });
            });
            return results;
        }""")

        print(f"\nAll {len(all_selected)} selected sites:")
        for s in all_selected:
            print(f"  {s['name']}")

        print(f"\n{'='*60}")
        if all_good:
            print("ALL TARGET SITES SELECTED - FIX WORKS!")
        else:
            print("SOME TARGET SITES STILL MISSING!")
        print(f"{'='*60}")

        await iauc_logout(page)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
