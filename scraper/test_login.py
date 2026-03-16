"""
Test: Login → Search → Extract vehicle data.
Focus on properly triggering the search and waiting for WebSocket results.
"""

import asyncio
import json
from playwright.async_api import async_playwright

LOGIN_URL = "https://www.aucneostation.com/"
USER_ID = "A124332"
PASSWORD = "Japanesemango1289"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        # === LOGIN ===
        print("[1] Logging in...")
        await page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
        await page.fill("#userid-pc", USER_ID)
        await page.fill("#password-pc", PASSWORD)
        await page.click("button[type='submit']")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(2)

        if "login-error-force" in page.url:
            await page.click("input[name='force_login']")
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(3)

        if "login-error" in page.url:
            print(f"    FAILED: {page.url}")
            await browser.close()
            return

        buy_href = await page.evaluate("""() => {
            for (const a of document.querySelectorAll('a')) {
                if (a.textContent.trim().includes('買いメニュー')) return a.href;
            }
        }""")
        print("    OK!")

        # === LOAD SEARCH PAGE ===
        print("[2] Loading search page...")
        await page.goto(buy_href, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(10)

        # === SELECT ALL MAKERS using the actual checkbox ===
        print("[3] Selecting all makers...")
        # Click the 全て選択 link — find the one near メーカー section
        selected = await page.evaluate("""() => {
            // Find all checkboxes for makers and check them
            const chks = document.querySelectorAll('.chk_makers');
            let count = 0;
            for (const chk of chks) {
                if (!chk.checked) {
                    chk.click();
                    count++;
                }
            }
            return count;
        }""")
        print(f"    Selected {selected} makers")

        await page.screenshot(path="screenshot_after_select.png")

        # === CLICK SEARCH BUTTON ===
        print("[4] Searching...")

        # JS click the search button
        clicked = await page.evaluate("""() => {
            const links = document.querySelectorAll('a');
            for (const a of links) {
                if (a.textContent.includes('この条件で一覧表示')) {
                    a.click();
                    return true;
                }
            }
            return false;
        }""")
        print(f"    Search button clicked: {clicked}")

        # Wait for results - poll for results_list to have children
        print("    Waiting for vehicle data to load...")
        for attempt in range(30):
            await asyncio.sleep(2)
            result = await page.evaluate("""() => {
                const list = document.getElementById('results_list');
                if (list) return { id: 'results_list', children: list.children.length, html: list.innerHTML.substring(0, 500) };
                return null;
            }""")
            if result and result['children'] > 0:
                print(f"    Results appeared at {attempt*2}s! {result['children']} items in results_list")
                break

            # Also check the count display
            count_text = await page.evaluate("""() => {
                const body = document.body.innerText;
                const match = body.match(/(\\d+)台/);
                return match ? match[0] : null;
            }""")
            if attempt % 5 == 0:
                print(f"      [{attempt*2}s] results_list children: {result['children'] if result else 'N/A'}, count: {count_text}")
        else:
            print("    No results appeared after 60s")

        await page.screenshot(path="screenshot_results.png", full_page=True)

        # === EXTRACT DATA ===
        print("\n[5] Extracting vehicle data...")
        vehicles = await page.evaluate("""() => {
            const list = document.getElementById('results_list');
            if (!list) return [];

            const items = list.querySelectorAll('li');
            const result = [];

            for (const item of items) {
                const data = {};

                // Get all text content organized
                data.fullText = item.textContent.trim().substring(0, 500);
                data.html = item.innerHTML.substring(0, 2000);

                // Try to get images
                const imgs = item.querySelectorAll('img');
                data.images = Array.from(imgs).map(i => i.src).slice(0, 5);

                // Try to get links
                const links = item.querySelectorAll('a');
                data.links = Array.from(links).map(a => ({ text: a.textContent.trim().substring(0, 50), href: a.href })).slice(0, 5);

                // Get data attributes
                const attrs = {};
                for (const attr of item.attributes) {
                    if (attr.name.startsWith('data-')) {
                        attrs[attr.name] = attr.value.substring(0, 100);
                    }
                }
                data.dataAttrs = attrs;

                result.push(data);
            }

            return result.slice(0, 5);
        }""")

        print(f"    Extracted {len(vehicles)} vehicles")
        for i, v in enumerate(vehicles[:3]):
            print(f"\n    --- Vehicle {i} ---")
            print(f"    Text: {v['fullText'][:200]}")
            print(f"    Images: {v['images'][:2]}")
            print(f"    Links: {v['links'][:3]}")
            print(f"    Data attrs: {v['dataAttrs']}")

        with open("vehicles_data.json", "w") as f:
            json.dump(vehicles, f, indent=2, default=str, ensure_ascii=False)
        print(f"\n    Saved: vehicles_data.json")

        await browser.close()
        print("\n[Done]")

asyncio.run(main())
