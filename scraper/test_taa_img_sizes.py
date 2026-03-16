"""Test: Check TAA image size variants by downloading through authenticated session."""
import asyncio
from playwright.async_api import async_playwright
import base64

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
        print("Logged in")

        # Test different size suffixes for the same image
        base = "/data/img/20260316/336/B/B06009"
        for suffix in [1, 2, 3, 4, 5]:
            url = f"https://taacaa.jp{base}_{suffix}.jpg"
            size = await page.evaluate("""async (url) => {
                try {
                    const res = await fetch(url, { credentials: 'include' });
                    if (!res.ok) return { status: res.status, size: 0 };
                    const blob = await res.blob();
                    return { status: res.status, size: blob.size, type: blob.type };
                } catch(e) { return { error: e.message }; }
            }""", url)
            print(f"  _{suffix}.jpg → {size}")

        # Also test carImageFile.do wrapper with different suffixes
        print("\nWith carImageFile.do wrapper:")
        for suffix in [1, 2, 3, 4, 5]:
            url = f"https://taacaa.jp/app/common/carImageFile.do?path=/data/img/20260316/336/B/B06009_{suffix}.jpg"
            size = await page.evaluate("""async (url) => {
                try {
                    const res = await fetch(url, { credentials: 'include' });
                    if (!res.ok) return { status: res.status, size: 0 };
                    const blob = await res.blob();
                    return { status: res.status, size: blob.size, type: blob.type };
                } catch(e) { return { error: e.message }; }
            }""", url)
            print(f"  _{suffix}.jpg → {size}")

        # Test A section (auction sheet) sizes
        print("\nAuction sheet (A section):")
        for suffix in [1, 2, 3, 4, 5]:
            url = f"https://taacaa.jp/app/common/carImageFile.do?path=/data/img/20260316/336/A/A06009_{suffix}.jpg"
            size = await page.evaluate("""async (url) => {
                try {
                    const res = await fetch(url, { credentials: 'include' });
                    if (!res.ok) return { status: res.status, size: 0 };
                    const blob = await res.blob();
                    return { status: res.status, size: blob.size, type: blob.type };
                } catch(e) { return { error: e.message }; }
            }""", url)
            print(f"  A_{suffix}.jpg → {size}")

        await browser.close()

asyncio.run(main())
