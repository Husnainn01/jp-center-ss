"""Test ALL image sections (A-J) with ALL suffixes (1-5) to find best quality."""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent="Mozilla/5.0")
        page = await ctx.new_page()

        # Login
        await page.goto("https://taacaa.jp/index-e.html", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(1)
        await page.fill("#kainNo", "CN5005")
        await page.fill("#kainTantoId", "xxund7qt")
        await page.fill("#password", "L57Sxyqha4B4")
        await page.evaluate("() => loginAction()")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(2)
        body = await page.inner_text("body")
        if "already logged" in body.lower():
            await page.evaluate("() => compulsionLogin()")
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(2)
        print("Logged in\n")

        ref = "06009"
        date_hall = "20260316/336"

        print("Section | _1      | _2      | _3      | _4      | _5")
        print("--------|---------|---------|---------|---------|--------")

        for section in "ABCDEFGHIJ":
            row = f"   {section}    |"
            for suffix in range(1, 6):
                url = f"https://taacaa.jp/data/img/{date_hall}/{section}/{section}{ref}_{suffix}.jpg"
                size = await page.evaluate("""async (url) => {
                    try {
                        const res = await fetch(url, { credentials: 'include' });
                        if (!res.ok) return 0;
                        const blob = await res.blob();
                        return blob.size;
                    } catch { return -1; }
                }""", url)
                if size > 100:
                    row += f" {size:>6} |"
                else:
                    row += f"     — |"
            print(row)

        # Also test with carImageFile.do wrapper
        print("\n\nWith carImageFile.do wrapper:")
        print("Section | _1      | _2      | _3      | _4      | _5")
        print("--------|---------|---------|---------|---------|--------")

        for section in "ABCDEFGHIJ":
            row = f"   {section}    |"
            for suffix in range(1, 6):
                path = f"/data/img/{date_hall}/{section}/{section}{ref}_{suffix}.jpg"
                url = f"https://taacaa.jp/app/common/carImageFile.do?path={path}"
                size = await page.evaluate("""async (url) => {
                    try {
                        const res = await fetch(url, { credentials: 'include' });
                        if (!res.ok) return 0;
                        const blob = await res.blob();
                        if (blob.type === 'text/html') return 0;
                        return blob.size;
                    } catch { return -1; }
                }""", url)
                if size > 100:
                    row += f" {size:>6} |"
                else:
                    row += f"     — |"
            print(row)

        await browser.close()

asyncio.run(main())
