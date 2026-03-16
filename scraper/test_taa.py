"""
Test: Login to TAA → Search By Maker/Model → Monday only → Select all → Get results.
"""

import asyncio
from playwright.async_api import async_playwright

LOGIN_URL = "https://taacaa.jp/index-e.html"
NUMBER = "CN5005"
USER_ID = "xxund7qt"
PASSWORD = "L57Sxyqha4B4"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        # === LOGIN ===
        print("[1] Logging in...")
        await page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)
        await page.fill("#kainNo", NUMBER)
        await page.fill("#kainTantoId", USER_ID)
        await page.fill("#password", PASSWORD)
        await page.evaluate("() => loginAction()")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(3)

        # Force login if needed
        body = await page.inner_text("body")
        if "already logged" in body.lower():
            print("    Force login...")
            await page.evaluate("() => compulsionLogin()")
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(3)

        print(f"    Logged in: {page.url}")

        # === NAVIGATE TO SEARCH ===
        print("\n[2] Going to Search (By Maker/Model)...")
        await page.evaluate("""() => {
            const img = document.querySelector('img[name="navi01"]');
            if (img) { const link = img.closest('a'); if (link) link.click(); }
        }""")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(5)
        print(f"    URL: {page.url}")

        # === SELECT MONDAY + ALL MAKERS ===
        print("\n[3] Setting search: Monday + All makers...")

        # Monday should already be checked, but let's verify
        mon_checked = await page.evaluate("""() => {
            const cbs = document.querySelectorAll('input[name="checkHallYobi"]');
            const states = {};
            cbs.forEach(cb => {
                const label = cb.parentElement?.textContent?.trim() || cb.value;
                states[label] = cb.checked;
            });
            return states;
        }""")
        print(f"    Day states: {mon_checked}")

        # Select all makers
        print("    Selecting all makers...")
        await page.evaluate("""() => {
            // Click every maker checkbox
            document.querySelectorAll('input[name="carMakerArr"]').forEach(cb => {
                if (!cb.checked) cb.click();
            });
        }""")
        await asyncio.sleep(2)

        # Now select all MODELS (syasyu2) — they should have loaded after makers were selected
        print("    Selecting all models...")
        await page.evaluate("""() => {
            // Click Select All for models
            const links = document.querySelectorAll('a.textlink');
            for (const a of links) {
                const href = a.href || '';
                if (href.includes('syasyu2') && a.textContent.includes('Select All')) {
                    a.click();
                    break;
                }
            }
            // Also manually check all model checkboxes
            document.querySelectorAll('input[name="syasyu2"]').forEach(cb => {
                if (!cb.checked) cb.click();
            });
        }""")
        await asyncio.sleep(1)

        model_count = await page.evaluate("() => document.querySelectorAll('input[name=\"syasyu2\"]:checked').length")
        print(f"    Selected {model_count} models")

        await page.screenshot(path="taa_05_ready.png", full_page=True)

        # === SUBMIT SEARCH ===
        print("\n[4] Submitting search...")
        # Call getListDetail directly — it sets form action and submits
        await page.evaluate("""() => {
            var fm = document.getElementById("SearchForm");
            fm.action = "./CarListSpecification.do";
            if (typeof formAddKey === 'function') formAddKey(fm);
            fm.submit();
        }""")
        await page.wait_for_load_state("networkidle", timeout=60000)
        await asyncio.sleep(8)

        print(f"    URL: {page.url}")
        await page.screenshot(path="taa_06_results.png", full_page=True)

        # === ANALYZE RESULTS ===
        print("\n[5] Analyzing results...")
        text_lines = await page.evaluate("""() =>
            document.body.innerText.split('\\n').filter(l => l.trim()).slice(0, 40)
        """)
        for line in text_lines:
            print(f"    {line[:120]}")

        # Find table rows with vehicle data
        tables = await page.evaluate("""() => {
            const tables = document.querySelectorAll('table');
            return Array.from(tables).map(t => ({
                rows: t.rows.length,
                class: t.className.substring(0, 40),
                id: t.id || '',
            })).filter(t => t.rows > 3);
        }""")
        print(f"\n    Tables with >3 rows: {len(tables)}")
        for t in tables[:5]:
            print(f"      id={t['id']} class={t['class']} rows={t['rows']}")

        # Try to extract vehicle data from the first result rows
        vehicles = await page.evaluate("""() => {
            const rows = document.querySelectorAll('tr');
            const results = [];
            for (const row of rows) {
                const cells = row.querySelectorAll('td');
                if (cells.length >= 5) {
                    const texts = Array.from(cells).map(c => c.textContent.trim().substring(0, 50));
                    const imgs = Array.from(row.querySelectorAll('img')).map(i => i.src).filter(s => s.includes('jpg') || s.includes('png'));
                    if (texts.some(t => t.length > 3)) {
                        results.push({ cells: texts, images: imgs.slice(0, 3) });
                    }
                }
            }
            return results.slice(0, 5);
        }""")

        print(f"\n    Vehicle-like rows: {len(vehicles)}")
        for i, v in enumerate(vehicles[:5]):
            print(f"\n    Row {i}:")
            for j, cell in enumerate(v['cells'][:8]):
                if cell:
                    print(f"      [{j}] {cell}")
            if v['images']:
                print(f"      imgs: {v['images'][:2]}")

        # Save HTML
        html = await page.content()
        with open("taa_results.html", "w") as f:
            f.write(html)
        print("\n    HTML saved: taa_results.html")

        await browser.close()
        print("\n[Done]")

asyncio.run(main())
