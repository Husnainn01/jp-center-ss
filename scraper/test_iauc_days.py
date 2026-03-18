"""Test: Select All → uncheck all days except target."""
import asyncio
from dotenv import load_dotenv
load_dotenv()
from playwright.async_api import async_playwright
from iauc_login import iauc_login

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()
        ok = await iauc_login(page, "A124332", "emlo4732")
        if not ok:
            await browser.close()
            return

        days = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('button.day-button')).map(btn => {
                const r = btn.getBoundingClientRect();
                return { text: btn.textContent.trim(), x: r.x + r.width/2, y: r.y + r.height/2 };
            });
        }""")
        print(f"Days: {[d['text'] for d in days]}")

        # For each upcoming day, test: Select All → uncheck all others
        for target_day in days:
            if target_day["text"] == "Today":
                continue

            # Reset: uncheck all d[]
            await page.evaluate("""() => {
                document.querySelectorAll('input[name="e[]"]').forEach(cb => { if (cb.checked) cb.click(); });
                document.querySelectorAll('input[name="d[]"]').forEach(cb => { if (cb.checked) cb.click(); });
            }""")
            await asyncio.sleep(0.5)

            # Select All Auction & Tender
            await page.click("a.title-button.checkbox_on_all")
            await asyncio.sleep(1)

            # Uncheck every day EXCEPT target
            for day in days:
                if day["text"] != target_day["text"]:
                    await page.mouse.click(day["x"], day["y"])
                    await asyncio.sleep(0.5)

            await asyncio.sleep(1)
            count = await page.evaluate('() => document.querySelectorAll(\'input[name="d[]"]:checked\').length')
            print(f"  {target_day['text']}: {count} sites")

        await browser.close()
        print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
