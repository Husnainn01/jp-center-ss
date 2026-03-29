"""Test: does the Ninja 100/page selector actually work?
Run: cd scraper && python3 test_ninja_pagesize.py
"""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080}, locale="en-US")
        page = await context.new_page()
        await page.goto("https://www.ninja-cartrade.jp/ninja/", wait_until="networkidle", timeout=60000)
        await asyncio.sleep(2)
        await page.fill("#loginId", "L4013V80")
        await page.fill("#password", "93493493")
        await page.evaluate("() => login()")
        await asyncio.sleep(5)
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass
        body = await page.inner_text("body")
        if "different user" in body.lower():
            await page.evaluate("""() => { for (const a of document.querySelectorAll('a')) if (a.textContent.trim() === 'Login') { a.click(); return; } }""")
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(3)
        if "searchcondition" not in page.url:
            print("Login failed!")
            return
        print("Logged in!")

        # MAZDA (under 1000)
        await page.evaluate("() => seniBrand('10')")
        await asyncio.sleep(3)
        # Wait for allSearch to be available
        for _ in range(10):
            has = await page.evaluate("() => typeof allSearch === 'function'")
            if has: break
            await asyncio.sleep(1)
        await page.evaluate("() => allSearch()")
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass
        await asyncio.sleep(3)
        for _ in range(10):
            cnt = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
            if cnt > 0: break
            await asyncio.sleep(1)

        # Count before
        rows_before = await page.evaluate("""() => {
            const seen = new Set();
            document.querySelectorAll('[onclick*=seniCarDetail]').forEach(el => {
                const m = el.getAttribute('onclick').match(/seniCarDetail\\('\\d+',\\s*'[^']*',\\s*'[^']*',\\s*'([^']*)',/);
                if (m) seen.add(m[1]);
            });
            return seen.size;
        }""")
        print(f"\nBefore page size change: {rows_before} unique vehicles")

        # Check what page size controls exist
        controls = await page.evaluate("""() => {
            const results = [];
            // Check for select dropdown
            document.querySelectorAll('select').forEach(s => {
                results.push({
                    type: 'select',
                    id: s.id,
                    name: s.name,
                    class: s.className,
                    options: Array.from(s.options).map(o => o.value),
                    visible: s.offsetParent !== null,
                });
            });
            // Check for links with changeDisp or page size
            document.querySelectorAll('a').forEach(a => {
                const onclick = a.getAttribute('onclick') || '';
                const text = a.textContent.trim();
                if (onclick.includes('changeDisp') || (text.match(/^\\d+$/) && parseInt(text) >= 20)) {
                    results.push({
                        type: 'link',
                        text,
                        onclick: onclick.substring(0, 100),
                        visible: a.offsetParent !== null,
                    });
                }
            });
            return results;
        }""")

        print(f"\nPage size controls:")
        for c in controls:
            print(f"  {c['type']}: ", end="")
            if c['type'] == 'select':
                print(f"id='{c['id']}' class='{c['class']}' options={c['options']} visible={c['visible']}")
            else:
                print(f"text='{c['text']}' onclick='{c['onclick']}' visible={c['visible']}")

        # Try METHOD 1: select dropdown (.selDisplayedItems)
        print(f"\n--- Method 1: select_option ---")
        try:
            await page.select_option(".selDisplayedItems", "100")
            await asyncio.sleep(5)
            for _ in range(10):
                cnt = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
                if cnt > rows_before * 2: break
                await asyncio.sleep(1)
            rows_after1 = await page.evaluate("""() => {
                const seen = new Set();
                document.querySelectorAll('[onclick*=seniCarDetail]').forEach(el => {
                    const m = el.getAttribute('onclick').match(/seniCarDetail\\('\\d+',\\s*'[^']*',\\s*'[^']*',\\s*'([^']*)',/);
                    if (m) seen.add(m[1]);
                });
                return seen.size;
            }""")
            print(f"  After select_option: {rows_after1} unique vehicles")
        except Exception as e:
            print(f"  select_option failed: {e}")

        # Try METHOD 2: click the '100' link
        print(f"\n--- Method 2: click '100' link ---")
        # First go back to default
        try:
            await page.select_option(".selDisplayedItems", "20")
            await asyncio.sleep(3)
        except:
            pass

        clicked = await page.evaluate("""() => {
            const links = document.querySelectorAll('a');
            for (const a of links) {
                if (a.textContent.trim() === '100' && a.getAttribute('onclick')
                    && a.getAttribute('onclick').includes('changeDisp')) {
                    a.click();
                    return a.getAttribute('onclick');
                }
            }
            return '';
        }""")
        if clicked:
            print(f"  Clicked: {clicked[:80]}")
            await asyncio.sleep(5)
            for _ in range(10):
                cnt = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
                if cnt > rows_before * 2: break
                await asyncio.sleep(1)
            rows_after2 = await page.evaluate("""() => {
                const seen = new Set();
                document.querySelectorAll('[onclick*=seniCarDetail]').forEach(el => {
                    const m = el.getAttribute('onclick').match(/seniCarDetail\\('\\d+',\\s*'[^']*',\\s*'[^']*',\\s*'([^']*)',/);
                    if (m) seen.add(m[1]);
                });
                return seen.size;
            }""")
            print(f"  After click: {rows_after2} unique vehicles")
        else:
            print("  No '100' link found")

        # Check total available
        total = await page.evaluate("""() => {
            const text = document.body.innerText;
            const m = text.match(/(\\d[\\d,]*)\\s*items/i);
            return m ? m[1] : '?';
        }""")
        print(f"\nTotal available: {total}")

        # Take screenshot
        await page.screenshot(path="ninja_pagesize.png")
        print("Screenshot: ninja_pagesize.png")

        await browser.close()

asyncio.run(main())
