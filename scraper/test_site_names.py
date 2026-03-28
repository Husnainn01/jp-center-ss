"""Extract actual auction site names from iAUC page structure.
Run: cd scraper && python3 test_site_names.py
"""

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from playwright.async_api import async_playwright
from iauc_login import iauc_login, iauc_logout

SEARCH = ["honda", "aucnet", "sendai", "hokkaido", "ju ", "noaa", "osaka", "mota", "kansai", "kyush", "tokyo"]


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

        # Get FULL HTML of each sitebox to understand structure
        print("=== FIRST 5 SITE BOXES (full HTML) ===\n")
        html_samples = await page.evaluate("""() => {
            const boxes = document.querySelectorAll('.sitebox-blue, .sitebox-green');
            return Array.from(boxes).slice(0, 5).map(b => b.outerHTML.substring(0, 500));
        }""")
        for i, html in enumerate(html_samples):
            print(f"--- Box {i+1} ---")
            print(html)
            print()

        # Now try to get names from the day-column headers or the box structure
        print("=== EXTRACTING SITE NAMES ===\n")
        sites = await page.evaluate("""() => {
            const results = [];
            const boxes = document.querySelectorAll('.sitebox-blue, .sitebox-green');
            boxes.forEach((sb, idx) => {
                const inp = sb.querySelector('input[name="d[]"]');
                if (!inp) return;

                // Try every possible name source
                const img = sb.querySelector('img');
                const imgAlt = img ? (img.alt || '') : '';
                const imgTitle = img ? (img.title || '') : '';
                const imgSrc = img ? img.src : '';

                // Check for any text nodes directly
                let directText = '';
                sb.childNodes.forEach(n => {
                    if (n.nodeType === 3 && n.textContent.trim()) {
                        directText += n.textContent.trim() + ' ';
                    }
                });

                // Check data attributes on the sitebox
                const dataAttrs = {};
                for (const attr of sb.attributes) {
                    if (attr.name.startsWith('data-')) {
                        dataAttrs[attr.name] = attr.value;
                    }
                }

                // Check the parent day-site-box for column header
                const dayBox = sb.closest('.day-site-box');
                const dayHeader = dayBox ? (dayBox.querySelector('.day-header, .column-header, h3, h4')?.textContent?.trim() || '') : '';

                // Check onclick or other JS attributes
                const onclick = sb.getAttribute('onclick') || inp.getAttribute('onclick') || '';

                results.push({
                    idx,
                    value: inp.value,
                    checked: inp.checked,
                    imgAlt,
                    imgTitle,
                    imgFile: imgSrc.split('/').pop() || '',
                    directText: directText.trim(),
                    dataAttrs,
                    dayHeader,
                    onclick: onclick.substring(0, 100),
                    allText: sb.textContent.trim().replace(/\\s+/g, ' ').substring(0, 80),
                    className: sb.className,
                });
            });
            return results;
        }""")

        for s in sites:
            # Build the best name we can find
            name = s['imgAlt'] or s['imgTitle'] or s['directText'] or ''
            data_info = str(s['dataAttrs']) if s['dataAttrs'] else ''

            label_lower = (name + s['allText'] + data_info + s['imgFile']).lower()
            match = any(t in label_lower for t in SEARCH)
            marker = " <<<" if match else ""

            status = "[x]" if s['checked'] else "[ ]"
            print(f"{s['idx']+1:3}. {status} val={s['value']} name='{name}' text='{s['allText'][:50]}' img={s['imgFile'][:30]} data={data_info[:60]}{marker}")

        # Also check: are there day column headers above the boxes?
        print(f"\n=== DAY COLUMN STRUCTURE ===")
        columns = await page.evaluate("""() => {
            const cols = [];
            document.querySelectorAll('.day-site-box').forEach(box => {
                const checkboxes = box.querySelectorAll('input[name="d[]"]');
                const header = box.previousElementSibling?.textContent?.trim() || '';
                const boxClass = box.className;
                cols.push({
                    header,
                    class: boxClass,
                    siteCount: checkboxes.length,
                    firstValue: checkboxes[0]?.value || '',
                });
            });
            return cols;
        }""")
        for c in columns:
            print(f"  header='{c['header'][:40]}' class='{c['class'][:40]}' sites={c['siteCount']}")

        print(f"\n=== TOTAL: {len(sites)} site checkboxes ===")

        await iauc_logout(page)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
