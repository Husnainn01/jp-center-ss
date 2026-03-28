"""Dump the FULL HTML structure around auction site checkboxes to find real names.
Run: cd scraper && python3 test_monday_sites2.py
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

        # Get full structure around d[] checkboxes
        sites = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('input[name="d[]"]').forEach((inp, idx) => {
                // Walk up to find the real name
                let name = '';
                let el = inp;

                // Check siblings, parent text, title attrs, nearby elements
                const parent = inp.parentElement;
                const grandparent = parent?.parentElement;
                const greatGrandparent = grandparent?.parentElement;

                // Try various approaches to get the site name
                const approaches = {
                    value: inp.value,
                    title: inp.title || inp.getAttribute('title') || '',
                    dataName: inp.getAttribute('data-name') || '',
                    parentTitle: parent?.title || parent?.getAttribute('title') || '',
                    parentText: parent?.textContent?.trim()?.substring(0, 100) || '',
                    grandparentText: grandparent?.textContent?.trim()?.substring(0, 150) || '',
                    prevSibling: inp.previousElementSibling?.textContent?.trim() || '',
                    nextSibling: inp.nextElementSibling?.textContent?.trim() || '',
                    labelFor: '',
                    nearbySpan: '',
                    parentClass: parent?.className || '',
                    grandparentClass: grandparent?.className || '',
                    greatGPClass: greatGrandparent?.className || '',
                    checked: inp.checked,
                };

                // Check label[for]
                const label = document.querySelector(`label[for="${inp.id}"]`);
                if (label) approaches.labelFor = label.textContent.trim().substring(0, 100);

                // Check nearby spans
                const spans = parent?.querySelectorAll('span') || [];
                approaches.nearbySpan = Array.from(spans).map(s => s.textContent.trim()).join(' | ').substring(0, 150);

                results.push(approaches);
            });
            return results;
        }""")

        print(f"=== ALL {len(sites)} AUCTION SITES — FULL DATA ===\n")
        for i, s in enumerate(sites):
            match = any(t in (s['parentText'] + s['grandparentText'] + s['value'] + s['dataName'] + s['nearbySpan']).lower() for t in SEARCH_TERMS)
            marker = " <<<" if match else ""
            print(f"--- Site {i+1}{marker} ---")
            print(f"  value: {s['value']}")
            if s['dataName']: print(f"  data-name: {s['dataName']}")
            if s['title']: print(f"  title: {s['title']}")
            if s['labelFor']: print(f"  label: {s['labelFor']}")
            print(f"  parent text: {s['parentText'][:100]}")
            if s['nearbySpan']: print(f"  spans: {s['nearbySpan'][:100]}")
            print(f"  parent class: {s['parentClass']}")
            print(f"  grandparent class: {s['grandparentClass']}")
            print(f"  checked: {s['checked']}")
            print()

            # Stop after first 15 to keep output manageable, then just show names
            if i == 14:
                print(f"\n... Showing compact view for remaining {len(sites) - 15} sites ...\n")
                break

        # Compact view of remaining
        for i, s in enumerate(sites[15:], start=16):
            name = s['dataName'] or s['labelFor'] or s['parentText'][:60] or s['value']
            match = any(t in name.lower() for t in SEARCH_TERMS)
            marker = " <<<" if match else ""
            status = "[x]" if s['checked'] else "[ ]"
            print(f"  {i:3}. {status} {name}{marker}")

        # Also try getting structure from the page's own JS data
        print(f"\n=== TRYING PAGE JS DATA ===")
        js_data = await page.evaluate("""() => {
            // Check if there's a global data object
            if (window.auctionSites) return JSON.stringify(window.auctionSites).substring(0, 2000);
            if (window.searchData) return JSON.stringify(window.searchData).substring(0, 2000);
            // Check table headers / section titles
            const headers = [];
            document.querySelectorAll('th, .section-title, .auction-name, .site-name, h3, h4, h5').forEach(el => {
                const t = el.textContent.trim();
                if (t && t.length < 100) headers.push(t);
            });
            return headers.join(' | ');
        }""")
        print(f"  {js_data[:500]}")

        # Take a screenshot for visual inspection
        await page.screenshot(path="/Users/husnain/Desktop/webs/jp-center/scraper/monday_sites.png", full_page=True)
        print(f"\nScreenshot saved: monday_sites.png")

        await iauc_logout(page)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
