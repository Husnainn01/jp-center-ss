"""Test: check if iAUC scraper correctly unchecks Today's auctions.
Skips DB — pass credentials via env: IAUC_USER_ID, IAUC_PASSWORD"""

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
        print("Set IAUC_USER_ID and IAUC_PASSWORD in .env or environment")
        return

    jst_now = now_jst()
    scrape_today = should_scrape_today()
    print(f"JST time: {jst_now.strftime('%Y-%m-%d %H:%M')}")
    print(f"should_scrape_today(): {scrape_today}")
    print(f"Expected: Today button should be UNCHECKED\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        print("Logging in to iAUC...")
        ok = await iauc_login(page, user_id, password)
        if not ok:
            print("Login failed!")
            await browser.close()
            return
        print("Logged in!\n")

        # Step 1: Clear all checkboxes first
        print("Step 1: Clearing all checkboxes...")
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="e[]"]').forEach(cb => { if (cb.checked) cb.click(); });
            document.querySelectorAll('input[name="d[]"]').forEach(cb => { if (cb.checked) cb.click(); });
        }""")
        await asyncio.sleep(1)

        # Step 2: Select All Auction & Tender
        print("Step 2: Clicking 'Select All' for auction sites...")
        await page.click("a.title-button.checkbox_on_all")
        await asyncio.sleep(1)

        # Screenshot BEFORE unchecking Today
        await page.screenshot(path="iauc_before_uncheck.png", full_page=True)
        print("Screenshot saved: iauc_before_uncheck.png")

        # Check day buttons state BEFORE
        days_before = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('button.day-button')).map(btn => ({
                text: btn.textContent.trim(),
                classes: btn.className
            }));
        }""")
        print(f"\nDay buttons BEFORE uncheck:")
        for d in days_before:
            print(f"  '{d['text']}' — classes: {d['classes']}")

        # Step 3: Uncheck Today (same logic as scraper)
        if not scrape_today:
            print("\nStep 3: Unchecking 'Today' button...")
            days = await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('button.day-button')).map(btn => {
                    const r = btn.getBoundingClientRect();
                    return { text: btn.textContent.trim(), x: r.x + r.width/2, y: r.y + r.height/2 };
                });
            }""")
            today_btn = next((d for d in days if d['text'] == 'Today'), None)
            if today_btn:
                print(f"  Found 'Today' button at ({today_btn['x']}, {today_btn['y']})")
                await page.mouse.click(today_btn['x'], today_btn['y'])
                await asyncio.sleep(2)
                print("  Clicked 'Today' to uncheck it")
            else:
                print("  WARNING: No 'Today' button found!")
                for d in days:
                    print(f"    Button: '{d['text']}'")

        # Check day buttons state AFTER
        days_after = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('button.day-button')).map(btn => ({
                text: btn.textContent.trim(),
                classes: btn.className
            }));
        }""")
        print(f"\nDay buttons AFTER uncheck:")
        for d in days_after:
            print(f"  '{d['text']}' — classes: {d['classes']}")

        # Check how many auction sites are still checked
        checked = await page.evaluate('() => document.querySelectorAll(\'input[name="d[]"]:checked\').length')
        print(f"\n{checked} auction sites still selected after unchecking Today")

        # Screenshot AFTER unchecking Today
        await page.screenshot(path="iauc_after_uncheck.png", full_page=True)
        print("Screenshot saved: iauc_after_uncheck.png")

        # Save the HTML for inspection
        html = await page.content()
        with open("iauc_day_selection.html", "w") as f:
            f.write(html)
        print("HTML saved: iauc_day_selection.html")

        print("\nBrowser will stay open for 30s so you can inspect...")
        await asyncio.sleep(30)

        await browser.close()
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
