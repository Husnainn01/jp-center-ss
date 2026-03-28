"""Check ALL auction sites on iAUC for Monday — dump every name, check what's selected.
Looking for: HONDA TOKYO, HONDA KANSAI, HONDA KYUSHU, SENDAI, HOKKAIDO, JU TOKYO, NOAA, OSAKA MOTA, AUCNET
Run: cd scraper && python3 test_monday_sites.py
"""

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from playwright.async_api import async_playwright
from iauc_login import iauc_login, iauc_logout

SEARCH_TERMS = ["honda", "aucnet", "sendai", "hokkaido", "ju ", "noaa", "osaka", "mota", "kansai", "kyush", "tokyo"]


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

        # === DUMP ALL AUCTION SITE NAMES ===
        # Get all checkboxes with their labels, section headers, and day grouping
        all_data = await page.evaluate("""() => {
            const result = { sections: [], dayButtons: [], allSites: [] };

            // Get day buttons
            document.querySelectorAll('a.day-button4g, button.day-button4g').forEach(b => {
                if (b.offsetParent !== null) {
                    result.dayButtons.push(b.textContent.trim());
                }
            });

            // Get ALL checkboxes - both e[] (auction types) and d[] (auction sites)
            document.querySelectorAll('input[name="e[]"]').forEach(inp => {
                const parent = inp.closest('label, li, div');
                const label = parent ? parent.textContent.trim() : inp.value;
                result.sections.push({ type: 'auction_type', value: inp.value, label, checked: inp.checked });
            });

            document.querySelectorAll('input[name="d[]"]').forEach(inp => {
                const parent = inp.closest('label, li, div');
                const label = parent ? parent.textContent.trim() : inp.value;
                result.allSites.push({ type: 'auction_site', value: inp.value, label, checked: inp.checked });
            });

            return result;
        }""")

        print(f"=== DAY BUTTONS ===")
        for db in all_data['dayButtons']:
            print(f"  {db}")

        print(f"\n=== AUCTION TYPES (e[] checkboxes): {len(all_data['sections'])} ===")
        for s in all_data['sections']:
            print(f"  {'[x]' if s['checked'] else '[ ]'} {s['label'][:80]}")

        print(f"\n=== ALL AUCTION SITES (d[] checkboxes): {len(all_data['allSites'])} ===")
        for i, s in enumerate(all_data['allSites']):
            # Highlight sites matching our search terms
            label_lower = s['label'].lower()
            match = any(t in label_lower for t in SEARCH_TERMS)
            marker = " <<<" if match else ""
            print(f"  {i+1:3}. {'[x]' if s['checked'] else '[ ]'} {s['label'][:80]}{marker}")

        # === NOW DO THE SCRAPER SELECTION ===
        print(f"\n{'='*60}")
        print(f"APPLYING SCRAPER SELECTION LOGIC...")
        print(f"{'='*60}\n")

        # Clear all
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="e[]"]:checked').forEach(cb => cb.click());
            document.querySelectorAll('input[name="d[]"]:checked').forEach(cb => cb.click());
        }""")
        await asyncio.sleep(1)

        # Select All (blue button only, not green Kyoyuzaiko)
        await page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('a.title-button.checkbox_on_all'));
            for (const b of btns) {
                if (!b.classList.contains('title-green-button')) { b.click(); return; }
            }
        }""")
        await asyncio.sleep(1)

        # Check what's selected BEFORE unchecking today
        before_uncheck = await page.evaluate("""() => {
            const checked = [];
            const unchecked = [];
            document.querySelectorAll('input[name="d[]"]').forEach(inp => {
                const parent = inp.closest('label, li, div');
                const label = parent ? parent.textContent.trim() : inp.value;
                if (inp.checked) checked.push(label);
                else unchecked.push(label);
            });
            return { checked, unchecked };
        }""")
        print(f"AFTER 'Select All': {len(before_uncheck['checked'])} selected, {len(before_uncheck['unchecked'])} NOT selected")

        if before_uncheck['unchecked']:
            print(f"\n  NOT selected by 'Select All':")
            for label in before_uncheck['unchecked']:
                label_lower = label.lower()
                match = any(t in label_lower for t in SEARCH_TERMS)
                marker = " <<< MISSING TARGET" if match else ""
                print(f"    [ ] {label[:80]}{marker}")

        # Uncheck Today
        await page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('a.day-button4g, button.day-button4g'));
            for (const b of btns) {
                if (b.textContent.trim().toUpperCase() === 'TODAY' && b.offsetParent !== null) {
                    b.click(); return;
                }
            }
        }""")
        await asyncio.sleep(1)

        # Check what's selected AFTER unchecking today
        after_uncheck = await page.evaluate("""() => {
            const checked = [];
            const unchecked = [];
            document.querySelectorAll('input[name="d[]"]').forEach(inp => {
                const parent = inp.closest('label, li, div');
                const label = parent ? parent.textContent.trim() : inp.value;
                if (inp.checked) checked.push(label);
                else unchecked.push(label);
            });
            return { checked, unchecked };
        }""")
        print(f"\nAFTER uncheck Today: {len(after_uncheck['checked'])} selected, {len(after_uncheck['unchecked'])} NOT selected")

        # Show which of our target sites are missing
        print(f"\n=== TARGET SITE STATUS ===")
        for label in after_uncheck['checked']:
            label_lower = label.lower()
            if any(t in label_lower for t in SEARCH_TERMS):
                print(f"  [SELECTED]     {label[:80]}")
        for label in after_uncheck['unchecked']:
            label_lower = label.lower()
            if any(t in label_lower for t in SEARCH_TERMS):
                print(f"  [NOT SELECTED] {label[:80]}")

        # === CHECK MONDAY SPECIFICALLY ===
        print(f"\n=== MONDAY SITES ===")
        # Click MON button to see what's available
        await page.evaluate("""() => {
            // First clear all
            document.querySelectorAll('input[name="d[]"]:checked').forEach(cb => cb.click());
        }""")
        await asyncio.sleep(0.5)

        # Click MON day button
        await page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('a.day-button4g, button.day-button4g'));
            for (const b of btns) {
                if (b.textContent.trim().toUpperCase() === 'MON' && b.offsetParent !== null) {
                    b.click(); return;
                }
            }
        }""")
        await asyncio.sleep(1)

        monday_sites = await page.evaluate("""() => {
            const checked = [];
            document.querySelectorAll('input[name="d[]"]:checked').forEach(inp => {
                const parent = inp.closest('label, li, div');
                const label = parent ? parent.textContent.trim() : inp.value;
                checked.push(label);
            });
            return checked;
        }""")

        print(f"Monday has {len(monday_sites)} auction sites:")
        for label in monday_sites:
            label_lower = label.lower()
            match = any(t in label_lower for t in SEARCH_TERMS)
            marker = " <<< TARGET" if match else ""
            print(f"  {label[:80]}{marker}")

        # Check if there are Kyoyuzaiko/green section sites we're missing
        print(f"\n=== CHECKING KYOYUZAIKO (GREEN) SECTION ===")
        green_info = await page.evaluate("""() => {
            const greenBtns = Array.from(document.querySelectorAll('a.title-button.checkbox_on_all.title-green-button'));
            const result = { greenBtnCount: greenBtns.length, greenBtnTexts: [] };
            greenBtns.forEach(b => result.greenBtnTexts.push(b.textContent.trim()));

            // Check if there are separate sections
            const sections = document.querySelectorAll('.section-title, .title-button');
            result.sectionTitles = [];
            sections.forEach(s => result.sectionTitles.push(s.textContent.trim()));

            return result;
        }""")
        print(f"Green (Kyoyuzaiko) buttons: {green_info['greenBtnCount']}")
        for t in green_info['greenBtnTexts']:
            print(f"  {t}")

        print(f"\n{'='*60}")
        print("TEST COMPLETE")
        print(f"{'='*60}")

        await iauc_logout(page)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
