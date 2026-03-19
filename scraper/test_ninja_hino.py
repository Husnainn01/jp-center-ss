"""Find HINO brand code on NINJA."""
import asyncio
from playwright.async_api import async_playwright
from ninja_login import ninja_login

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        ok = await ninja_login(context, "L4013V80", "93493493")
        if not ok:
            print("Login failed!")
            await browser.close()
            return

        page = context.pages[0]
        # Get all maker links and their brand codes
        makers = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('a').forEach(a => {
                const onclick = a.getAttribute('onclick') || '';
                const match = onclick.match(/seniBrand\\('(\\d+)'\\)/);
                if (match) {
                    results.push({ text: a.textContent.trim(), code: match[1] });
                }
            });
            return results;
        }""")
        print("All makers on NINJA:")
        for m in makers:
            print(f"  {m['text']} → code={m['code']}")

        await browser.close()

asyncio.run(main())
