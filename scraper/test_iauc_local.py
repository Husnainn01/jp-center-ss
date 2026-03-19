"""Local test copy of iAUC scraper — no DB, just login + auction selection.
Run with: python3 test_iauc_local.py
Shows browser so you can see exactly what gets selected."""

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from playwright.async_api import async_playwright
from iauc_login import iauc_login
from jst import should_scrape_today, now_jst


async def main():
    user_id = os.getenv("IAUC_USER_ID", "")
    password = os.getenv("IAUC_PASSWORD", "")
    if not user_id or not password:
        print("Set IAUC_USER_ID and IAUC_PASSWORD in .env")
        return

    jst_now = now_jst()
    scrape_today = should_scrape_today()
    print(f"JST time: {jst_now.strftime('%Y-%m-%d %H:%M')}")
    print(f"should_scrape_today(): {scrape_today}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        # === LOGIN ===
        print("Logging in...")
        ok = await iauc_login(page, user_id, password)
        if not ok:
            print("Login failed!")
            await browser.close()
            return
        print("Logged in!\n")

        # === STEP 1: Clear all checkboxes ===
        print("=== STEP 1: Clear all checkboxes ===")
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="e[]"]').forEach(cb => { if (cb.checked) cb.click(); });
            document.querySelectorAll('input[name="d[]"]').forEach(cb => { if (cb.checked) cb.click(); });
        }""")
        await asyncio.sleep(1)

        # === STEP 2: Select All Auction & Tender ===
        print("=== STEP 2: Select All ===")
        await page.click("a.title-button.checkbox_on_all")
        await asyncio.sleep(1)

        # Show state BEFORE
        checked_before = await page.evaluate('() => document.querySelectorAll(\'input[name="d[]"]:checked\').length')
        everyday_before = await page.evaluate('() => document.querySelectorAll(\'input[name="e[]"]:checked\').length')
        print(f"  BEFORE: {checked_before} day auctions + {everyday_before} everyday auctions checked")

        days_before = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('button.day-button')).map(btn => ({
                text: btn.textContent.trim(),
                active: btn.classList.contains('active'),
                target: btn.getAttribute('data-target')
            }));
        }""")
        print("  Day buttons BEFORE:")
        for d in days_before:
            status = "SELECTED" if d['active'] else "not selected"
            print(f"    {d['text']} ({d['target']}) — {status}")

        await page.screenshot(path="test_before_uncheck.png")
        print("  Screenshot: test_before_uncheck.png\n")

        # === STEP 3: Uncheck Today ===
        if not scrape_today:
            print("=== STEP 3: Unchecking Today ===")

            # Same logic as the real scraper
            days = await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('button.day-button')).map(btn => {
                    const r = btn.getBoundingClientRect();
                    return { text: btn.textContent.trim(), x: r.x + r.width/2, y: r.y + r.height/2 };
                });
            }""")
            today_btn = next((d for d in days if d['text'] == 'Today'), None)
            if today_btn:
                print(f"  Found 'Today' at ({today_btn['x']}, {today_btn['y']})")
                await page.mouse.click(today_btn['x'], today_btn['y'])
                await asyncio.sleep(2)
                print("  Mouse clicked 'Today'")
            else:
                print("  WARNING: No 'Today' button found!")

        # Show state AFTER
        checked_after = await page.evaluate('() => document.querySelectorAll(\'input[name="d[]"]:checked\').length')
        everyday_after = await page.evaluate('() => document.querySelectorAll(\'input[name="e[]"]:checked\').length')
        print(f"\n  AFTER: {checked_after} day auctions + {everyday_after} everyday auctions checked")

        days_after = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('button.day-button')).map(btn => ({
                text: btn.textContent.trim(),
                active: btn.classList.contains('active'),
                target: btn.getAttribute('data-target')
            }));
        }""")
        print("  Day buttons AFTER:")
        for d in days_after:
            status = "SELECTED" if d['active'] else "not selected"
            print(f"    {d['text']} ({d['target']}) — {status}")

        # Count today's checkboxes specifically
        today_target = next((d['target'] for d in days_after if d['text'] == 'Today'), None)
        if today_target:
            today_checked = await page.evaluate(f"""() => {{
                const section = document.querySelector('{today_target}');
                if (!section) return -1;
                return section.querySelectorAll('input[name="d[]"]:checked').length;
            }}""")
            today_total = await page.evaluate(f"""() => {{
                const section = document.querySelector('{today_target}');
                if (!section) return -1;
                return section.querySelectorAll('input[name="d[]"]').length;
            }}""")
            print(f"\n  Today's section ({today_target}): {today_checked}/{today_total} checked")

        await page.screenshot(path="test_after_uncheck.png")
        print("  Screenshot: test_after_uncheck.png")

        print(f"\n{'='*50}")
        if checked_after < checked_before:
            print(f"SUCCESS: Reduced from {checked_before} to {checked_after} checked auctions")
        else:
            print(f"PROBLEM: Still {checked_after} checked (was {checked_before}) — Today uncheck NOT working!")

        print("\nBrowser stays open 60s for inspection...")
        await asyncio.sleep(60)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
