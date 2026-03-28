"""Check if Honda auction is being selected and has vehicles for Monday.
Run: cd scraper && python3 test_honda_check.py
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

        # === STEP 1: Check ALL auction sites before any selection ===
        all_sites = await page.evaluate("""() => {
            const sites = [];
            document.querySelectorAll('input[name="d[]"]').forEach(inp => {
                const label = inp.parentElement?.textContent?.trim() || '';
                const val = inp.value;
                sites.push({ value: val, label, checked: inp.checked });
            });
            return sites;
        }""")

        print(f"=== ALL AUCTION SITES ({len(all_sites)} total) ===")
        honda_sites = [s for s in all_sites if 'honda' in s['label'].lower() or 'ホンダ' in s['label']]
        print(f"\nHonda-related sites found: {len(honda_sites)}")
        for s in honda_sites:
            print(f"  [{s['value']}] {s['label']} (checked: {s['checked']})")

        if not honda_sites:
            print("\n  >>> NO Honda sites found! Checking all site names for similar...")
            for s in all_sites:
                if any(kw in s['label'].lower() for kw in ['honda', 'hnd', 'hnda']):
                    print(f"  [{s['value']}] {s['label']}")

        # === STEP 2: Check day buttons ===
        print(f"\n=== DAY BUTTONS ===")
        day_buttons = await page.evaluate("""() => {
            const btns = [];
            document.querySelectorAll('a.day-button4g, button.day-button4g').forEach(b => {
                if (b.offsetParent !== null) {
                    btns.push({ text: b.textContent.trim(), active: b.classList.contains('active') || b.classList.contains('on') });
                }
            });
            return btns;
        }""")
        for db in day_buttons:
            print(f"  {db['text']} (active: {db['active']})")

        # === STEP 3: Do the same selection as the real scraper ===
        print(f"\n=== SELECTING (same as real scraper) ===")

        # Clear all
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="e[]"]:checked').forEach(cb => cb.click());
            document.querySelectorAll('input[name="d[]"]:checked').forEach(cb => cb.click());
        }""")
        await asyncio.sleep(1)

        # Select All auctions
        await page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('a.title-button.checkbox_on_all'));
            for (const b of btns) {
                if (!b.classList.contains('title-green-button')) { b.click(); return; }
            }
        }""")
        await asyncio.sleep(1)

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

        # Check Honda after selection
        honda_after = await page.evaluate("""() => {
            const sites = [];
            document.querySelectorAll('input[name="d[]"]').forEach(inp => {
                const label = inp.parentElement?.textContent?.trim() || '';
                if (label.toLowerCase().includes('honda') || label.includes('ホンダ')) {
                    sites.push({ value: inp.value, label, checked: inp.checked });
                }
            });
            return sites;
        }""")

        print(f"\nHonda sites after scraper selection:")
        for s in honda_after:
            status = "SELECTED" if s['checked'] else "NOT SELECTED"
            print(f"  [{s['value']}] {s['label']} -> {status}")

        selected_info = await page.evaluate("""() => ({
            eChecked: document.querySelectorAll('input[name="e[]"]:checked').length,
            dChecked: document.querySelectorAll('input[name="d[]"]:checked').length,
            dTotal: document.querySelectorAll('input[name="d[]"]').length,
        })""")
        print(f"\nTotal selected: {selected_info['dChecked']}/{selected_info['dTotal']} sites")

        # === STEP 4: Check each day's sites to see if Honda is on Monday ===
        print(f"\n=== CHECKING EACH DAY ===")
        for db in day_buttons:
            day_text = db['text']
            # Click the day button to see its sites
            await page.evaluate(f"""() => {{
                const btns = Array.from(document.querySelectorAll('a.day-button4g, button.day-button4g'));
                for (const b of btns) {{
                    if (b.textContent.trim() === '{day_text}' && b.offsetParent !== null) {{
                        b.click(); return;
                    }}
                }}
            }}""")
            await asyncio.sleep(1)

            day_sites = await page.evaluate("""() => {
                const checked = [];
                document.querySelectorAll('input[name="d[]"]:checked').forEach(inp => {
                    const label = inp.parentElement?.textContent?.trim() || '';
                    checked.push(label);
                });
                return checked;
            }""")

            honda_in_day = [s for s in day_sites if 'honda' in s.lower() or 'ホンダ' in s]
            count = len(day_sites)
            print(f"  {day_text}: {count} sites selected | Honda: {honda_in_day if honda_in_day else 'NOT FOUND'}")

        # === STEP 5: Navigate to maker/model to check Honda vehicle count ===
        print(f"\n=== CHECKING HONDA VEHICLE COUNT ===")

        # Re-select all + uncheck today (reset from day button clicking)
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="e[]"]:checked').forEach(cb => cb.click());
            document.querySelectorAll('input[name="d[]"]:checked').forEach(cb => cb.click());
        }""")
        await asyncio.sleep(0.5)
        await page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('a.title-button.checkbox_on_all'));
            for (const b of btns) {
                if (!b.classList.contains('title-green-button')) { b.click(); return; }
            }
        }""")
        await asyncio.sleep(0.5)
        await page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('a.day-button4g, button.day-button4g'));
            for (const b of btns) {
                if (b.textContent.trim().toUpperCase() === 'TODAY' && b.offsetParent !== null) {
                    b.click(); return;
                }
            }
        }""")
        await asyncio.sleep(1)

        # Go to Make & Model page
        await page.evaluate('() => check_sites(document.querySelector(".page-next-button"))')
        for _ in range(20):
            await asyncio.sleep(2)
            if "#maker" in page.url or "search" in page.url:
                break
        await asyncio.sleep(3)

        if "#maker" not in page.url and "search" not in page.url:
            print(f"Failed to reach Make & Model page! URL: {page.url}")
        else:
            # Select All makers
            await page.evaluate("""() => {
                const allBtns = Array.from(document.querySelectorAll('button'))
                    .filter(b => b.textContent.trim() === 'All' && b.offsetParent !== null);
                allBtns.forEach(b => b.click());
            }""")
            await asyncio.sleep(2)

            # Find Honda maker checkbox
            honda_maker = await page.evaluate("""() => {
                const results = [];
                document.querySelectorAll('input[name="maker[]"]').forEach(inp => {
                    const name = inp.getAttribute('data-name') || '';
                    if (name.toLowerCase().includes('honda') || name.includes('ホンダ')) {
                        results.push({ name, checked: inp.checked, value: inp.value });
                    }
                });
                return results;
            }""")
            print(f"Honda maker checkbox: {honda_maker}")

            # Get Honda models and counts
            honda_models = await page.evaluate("""() => {
                const results = [];
                document.querySelectorAll('input[name="type[]"]').forEach(inp => {
                    const name = inp.getAttribute('data-name') || '';
                    const cnt = parseInt(inp.getAttribute('data-cnt') || '0');
                    const maker = inp.closest('[data-maker]')?.getAttribute('data-maker') || '';
                    // Check the parent structure for Honda grouping
                    const parent = inp.closest('.maker-group, .type-group, [class*="maker"]');
                    const parentText = parent?.querySelector('.maker-name, .group-name, h3, h4')?.textContent || '';
                    if (name.toLowerCase().includes('honda') || parentText.toLowerCase().includes('honda') || maker.toLowerCase().includes('honda')) {
                        results.push({ name, cnt, maker: maker || parentText });
                    }
                });
                // Also try: all types with Honda in the preceding maker heading
                return results;
            }""")

            if honda_models:
                total_honda = sum(m['cnt'] for m in honda_models)
                print(f"\nHonda models found: {len(honda_models)} ({total_honda} vehicles total)")
                for m in honda_models[:10]:
                    print(f"  {m['name']}: {m['cnt']}")
            else:
                print("No Honda models found in type list!")

                # Debug: print ALL maker names
                all_makers = await page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('input[name="maker[]"]'))
                        .map(inp => ({ name: inp.getAttribute('data-name') || '', checked: inp.checked }))
                        .filter(m => m.name);
                }""")
                print(f"\nAll makers ({len(all_makers)}):")
                for m in all_makers:
                    print(f"  {'[x]' if m['checked'] else '[ ]'} {m['name']}")

        print(f"\n{'='*60}")
        print("TEST COMPLETE")
        print(f"{'='*60}")

        await iauc_logout(page)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
