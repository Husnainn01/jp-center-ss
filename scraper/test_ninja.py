"""Test: Login to Ninja Car Trade (USS) and explore."""
import asyncio
from playwright.async_api import async_playwright

LOGIN_URL = "https://www.ninja-cartrade.jp/ninja/"
USER_ID = "L4013V80"
PASSWORD = "93493493"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await ctx.new_page()

        # Load login page
        print("[1] Loading login page...")
        await page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        # Fill credentials using Playwright native fill
        print("[2] Filling credentials...")
        await page.fill("#loginId", USER_ID)
        await page.fill("#password", PASSWORD)

        # Call the login() JS function
        print("[3] Calling login()...")
        await page.evaluate("() => login()")
        await asyncio.sleep(5)

        # Check if the AJAX response triggered a form submit
        await page.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(3)

        print(f"    URL: {page.url}")
        await page.screenshot(path="ninja_03_after_login.png", full_page=True)

        # Check all pages
        all_pages = ctx.pages
        active = page
        if len(all_pages) > 1:
            print(f"    {len(all_pages)} pages:")
            for i, pg in enumerate(all_pages):
                print(f"      [{i}] {pg.url[:100]}")
            active = all_pages[-1]
            await active.wait_for_load_state("networkidle", timeout=10000)
            await asyncio.sleep(2)

        # Handle force login
        body = await active.inner_text("body")
        if "different user" in body.lower() or "already logged" in body.lower():
            print("    Force login — clicking Login...")
            # Find the Login link/button on this page (not the Cancel one)
            await active.evaluate("""() => {
                const links = document.querySelectorAll('a');
                for (const a of links) {
                    if (a.textContent.trim() === 'Login') { a.click(); return; }
                }
                // Try form submit
                const form = document.querySelector('form');
                if (form) form.submit();
            }""")
            await active.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(3)
            print(f"    After force: {active.url}")
            await active.screenshot(path="ninja_04_force.png", full_page=True)
            body = await active.inner_text("body")

            # Check all pages again
            all_pages = ctx.pages
            if len(all_pages) > 1:
                active = all_pages[-1]
                await active.wait_for_load_state("networkidle", timeout=10000)
                await asyncio.sleep(2)
                body = await active.inner_text("body")

        # Check errors
        if "incorrect" in body.lower()[:500] or "error" in body.lower()[:200]:
            print("    LOGIN FAILED:")
            for l in body.split("\n")[:10]:
                if l.strip(): print(f"      {l.strip()[:100]}")
            await browser.close()
            return

        print(f"    Login success! URL: {active.url}")
        print(f"    Title: {await active.title()}")
        await active.screenshot(path="ninja_04_member.png", full_page=True)

        # Explore
        print("\n[4] Exploring member area...")
        links = await active.evaluate("""() => {
            return Array.from(document.querySelectorAll('a')).map(a => ({
                text: a.textContent.trim().replace(/\\n/g, ' ').substring(0, 60),
                href: a.href.substring(0, 120),
                visible: a.offsetParent !== null,
            })).filter(l => l.text && l.visible);
        }""")
        print(f"    {len(links)} visible links:")
        for i, link in enumerate(links[:40]):
            print(f"      [{i:2d}] '{link['text']}' → {link['href']}")

        # Look for search/vehicle list
        print("\n[5] Looking for vehicle search...")
        for link in links:
            t = link['text'].lower()
            if any(kw in t for kw in ['search', 'vehicle', 'auction', 'car', 'list', 'find', 'consign', '検索']):
                print(f"    ★ '{link['text']}' → {link['href']}")

        # Page text
        lines = [l.strip() for l in body.split("\n") if l.strip()][:30]
        print(f"\n    Page text:")
        for line in lines:
            print(f"      {line[:100]}")

        # Step 6: Click TOYOTA maker link and search
        print("\n[6] Clicking TOYOTA maker...")
        await active.evaluate("""() => {
            const links = document.querySelectorAll('a');
            for (const a of links) {
                if (a.textContent.trim() === '・TOYOTA') { a.click(); return 'clicked TOYOTA'; }
            }
            return 'not found';
        }""")
        await active.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(5)

        print(f"    URL: {active.url}")
        await active.screenshot(path="ninja_05a_maker.png", full_page=True)

        # Check if we got a model selection page
        body2 = await active.inner_text("body")
        lines2 = [l.strip() for l in body2.split("\n") if l.strip()][:20]
        print("    After maker click:")
        for line in lines2:
            print(f"      {line[:100]}")

        # Now try searching from this state
        print("\n    Trying conditionSearch()...")
        await active.evaluate("() => { if (typeof conditionSearch === 'function') conditionSearch(); }")
        await active.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(5)

        print(f"    URL: {active.url}")
        await active.screenshot(path="ninja_05_results.png", full_page=True)

        # Analyze results
        body = await active.inner_text("body")
        lines = [l.strip() for l in body.split("\n") if l.strip()]
        print(f"\n    Page text (first 30):")
        for line in lines[:30]:
            print(f"      {line[:120]}")

        # Find vehicle data rows
        vehicles = await active.evaluate("""() => {
            const rows = document.querySelectorAll('tr, .vehicleItem, [class*=vehicle], [class*=item], [class*=result]');
            const results = [];
            for (const row of rows) {
                const imgs = Array.from(row.querySelectorAll('img')).map(i => i.src).filter(s => s.includes('jpg'));
                const text = row.textContent.trim();
                if (imgs.length > 0 && text.length > 20 && text.length < 2000) {
                    results.push({
                        text: text.substring(0, 300),
                        images: imgs.slice(0, 3),
                    });
                }
            }
            return results.slice(0, 5);
        }""")
        print(f"\n    Vehicle-like rows: {len(vehicles)}")
        for i, v in enumerate(vehicles[:3]):
            print(f"\n    Row {i}:")
            print(f"      Text: {v['text'][:200]}")
            print(f"      Imgs: {v['images'][:2]}")

        # Count total results
        count_text = ""
        for line in lines:
            if "hit" in line.lower() or "result" in line.lower() or "found" in line.lower() or "件" in line:
                count_text = line[:80]
                break
        print(f"\n    Results count: {count_text}")

        # Save HTML
        html = await active.content()
        with open("ninja_results.html", "w") as f:
            f.write(html)
        print("    HTML saved: ninja_results.html")

        await browser.close()
        print("\n[Done]")

asyncio.run(main())
