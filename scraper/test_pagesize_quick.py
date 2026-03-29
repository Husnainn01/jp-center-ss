"""Quick page size test — minimal delays.
Run: cd scraper && python3 test_pagesize_quick.py
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

        # Login
        await page.goto("https://www.ninja-cartrade.jp/ninja/", wait_until="networkidle", timeout=60000)
        await asyncio.sleep(2)
        await page.fill("#loginId", "L4013V80")
        await page.fill("#password", "93493493")
        await page.evaluate("() => login()")
        await asyncio.sleep(8)
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass

        body = await page.inner_text("body")
        if "different user" in body.lower():
            print("Force login...")
            await page.evaluate("""() => { for (const a of document.querySelectorAll('a')) if (a.textContent.trim() === 'Login') { a.click(); return; } }""")
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(5)

        url = page.url
        print(f"URL: {url}")
        if "searchcondition" not in url:
            print(f"Not on search page!")
            body = await page.inner_text("body")
            print(body[:300])
            await page.screenshot(path="ninja_login_debug.png")
            await browser.close()
            return

        print("Logged in!")

        # MINI (small, <1000)
        await page.evaluate("() => seniBrand('56')")
        try:
            await page.wait_for_load_state("networkidle", timeout=30000)
        except:
            pass
        await asyncio.sleep(3)

        # Select all body types
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="bodytype"]').forEach(cb => {
                if (!cb.checked) cb.click();
            });
        }""")
        await asyncio.sleep(1)

        # Wait for allSearch
        for _ in range(15):
            has = await page.evaluate("() => typeof allSearch === 'function'")
            if has:
                break
            await asyncio.sleep(1)

        # Check what functions are available
        funcs = await page.evaluate("""() => ({
            allSearch: typeof allSearch,
            makerListChoiceCarCat: typeof makerListChoiceCarCat,
            seniBrand: typeof seniBrand,
            url: location.href,
        })""")
        print(f"Available: {funcs}")

        # If allSearch not available, click a model instead
        if funcs['allSearch'] != 'function':
            print("allSearch not available, clicking first model...")
            clicked = await page.evaluate("""() => {
                const a = document.querySelector('a[onclick*="makerListChoiceCarCat"]');
                if (a) { a.click(); return a.textContent.trim(); }
                return '';
            }""")
            print(f"Clicked model: {clicked}")
        else:
            print("Calling allSearch...")
            await page.evaluate("() => allSearch()")

        try:
            await page.wait_for_load_state("networkidle", timeout=30000)
        except:
            pass
        await asyncio.sleep(5)

        # Wait for results
        for _ in range(15):
            cnt = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
            if cnt > 0:
                break
            await asyncio.sleep(1)

        # Check what we got
        rows = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
        unique = await page.evaluate("""() => {
            const seen = new Set();
            document.querySelectorAll('[onclick*=seniCarDetail]').forEach(el => {
                const m = el.getAttribute('onclick').match(/seniCarDetail\\('\\d+',\\s*'[^']*',\\s*'[^']*',\\s*'([^']*)',/);
                if (m) seen.add(m[1]);
            });
            return seen.size;
        }""")
        print(f"\nDefault: {rows} rows, {unique} unique vehicles")

        if unique == 0:
            await page.screenshot(path="ninja_no_results.png")
            body = await page.inner_text("body")
            print(f"Page: {body[:300]}")
            await browser.close()
            return

        # Find page size controls
        controls = await page.evaluate("""() => {
            const r = { selects: [], links: [] };
            document.querySelectorAll('select').forEach(s => {
                if (s.offsetParent !== null) {
                    r.selects.push({
                        id: s.id, name: s.name, class: s.className,
                        options: Array.from(s.options).map(o => ({ val: o.value, text: o.text, selected: o.selected })),
                    });
                }
            });
            document.querySelectorAll('a').forEach(a => {
                const text = a.textContent.trim();
                const onclick = a.getAttribute('onclick') || '';
                if ((text === '20' || text === '50' || text === '100') && onclick.includes('changeDisp')) {
                    r.links.push({ text, onclick: onclick.substring(0, 80), visible: a.offsetParent !== null });
                }
            });
            return r;
        }""")

        print(f"\nVisible selects: {len(controls['selects'])}")
        for s in controls['selects']:
            print(f"  id='{s['id']}' class='{s['class']}'")
            for o in s['options']:
                sel = " ← SELECTED" if o['selected'] else ""
                print(f"    {o['val']}: '{o['text']}'{sel}")

        print(f"\nchangeDisp links: {len(controls['links'])}")
        for l in controls['links']:
            print(f"  '{l['text']}' onclick='{l['onclick']}' visible={l['visible']}")

        # Try switching to 100
        if controls['links']:
            link100 = next((l for l in controls['links'] if l['text'] == '100'), None)
            if link100:
                print(f"\nClicking '100' link...")
                await page.evaluate("""() => {
                    for (const a of document.querySelectorAll('a')) {
                        if (a.textContent.trim() === '100' && a.getAttribute('onclick')?.includes('changeDisp')) {
                            a.click(); return;
                        }
                    }
                }""")
                await asyncio.sleep(5)
                for _ in range(10):
                    cnt = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
                    if cnt > rows: break
                    await asyncio.sleep(1)

                rows_after = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
                unique_after = await page.evaluate("""() => {
                    const seen = new Set();
                    document.querySelectorAll('[onclick*=seniCarDetail]').forEach(el => {
                        const m = el.getAttribute('onclick').match(/seniCarDetail\\('\\d+',\\s*'[^']*',\\s*'[^']*',\\s*'([^']*)',/);
                        if (m) seen.add(m[1]);
                    });
                    return seen.size;
                }""")
                print(f"After 100/page: {rows_after} rows, {unique_after} unique vehicles")
        elif controls['selects']:
            sel = controls['selects'][0]
            print(f"\nTrying select dropdown '{sel['class']}'...")
            try:
                await page.select_option(f".{sel['class'].split()[0]}", "100")
                await asyncio.sleep(5)
                rows_after = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
                print(f"After select: {rows_after} rows")
            except Exception as e:
                print(f"Select failed: {e}")

        await page.screenshot(path="ninja_pagesize_result.png")
        print("\nScreenshot saved")
        await browser.close()

asyncio.run(main())
