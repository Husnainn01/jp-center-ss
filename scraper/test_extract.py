"""
Quick script: Login, search, extract FULL structured vehicle data.
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

        # LOGIN
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
            print(f"FAILED: {page.url}")
            await browser.close()
            return

        buy_href = await page.evaluate("""() => {
            for (const a of document.querySelectorAll('a'))
                if (a.textContent.trim().includes('買いメニュー')) return a.href;
        }""")
        print("Logged in!")

        # LOAD SEARCH
        await page.goto(buy_href, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(10)

        # SELECT ALL MAKERS
        await page.evaluate("""() => {
            document.querySelectorAll('.chk_makers').forEach(c => { if(!c.checked) c.click(); });
        }""")
        await asyncio.sleep(1)

        # SEARCH
        await page.evaluate("""() => {
            for (const a of document.querySelectorAll('a'))
                if (a.textContent.includes('この条件で一覧表示')) { a.click(); return; }
        }""")

        # WAIT FOR RESULTS
        for i in range(30):
            await asyncio.sleep(2)
            count = await page.evaluate("() => document.getElementById('results_list')?.children.length || 0")
            if count > 0:
                print(f"Results loaded: {count} items at {i*2}s")
                break
        else:
            print("No results after 60s")
            await browser.close()
            return

        await asyncio.sleep(3)  # Extra wait for full render

        # EXTRACT ALL VEHICLE DATA
        vehicles = await page.evaluate("""() => {
            const list = document.getElementById('results_list');
            if (!list) return [];

            return Array.from(list.querySelectorAll('li')).map(li => {
                const get = (sel) => {
                    const el = li.querySelector(sel);
                    return el ? el.textContent.trim() : null;
                };
                const getImg = (sel) => {
                    const el = li.querySelector(sel);
                    return el ? el.src : null;
                };

                return {
                    item_id: li.getAttribute('data-item_id'),

                    // col_2: date + location
                    auction_datetime: get('.col_2 div:nth-child(1) .ellipsis'),
                    location: get('.col_2 div:nth-child(2) .ellipsis'),

                    // col_3: auction house + lot number
                    auction_house: get('.col_3 div:nth-child(1) .ellipsis'),
                    lot_number: get('.col_3 div:nth-child(2) .ellipsis'),

                    // col_4: year, make/model, grade
                    col_4_texts: Array.from(li.querySelectorAll('.col_4 .ellipsis')).map(e => e.textContent.trim()),

                    // col_5: mileage, inspection
                    col_5_texts: Array.from(li.querySelectorAll('.col_5 .ellipsis')).map(e => e.textContent.trim()),

                    // col_6: evaluation/rating
                    col_6_texts: Array.from(li.querySelectorAll('.col_6 .ellipsis')).map(e => e.textContent.trim()),

                    // col_7: start price
                    col_7_texts: Array.from(li.querySelectorAll('.col_7 .ellipsis')).map(e => e.textContent.trim()),

                    // col_8+: other columns
                    col_8_texts: Array.from(li.querySelectorAll('.col_8 .ellipsis')).map(e => e.textContent.trim()),
                    col_9_texts: Array.from(li.querySelectorAll('.col_9 .ellipsis')).map(e => e.textContent.trim()),
                    col_10_texts: Array.from(li.querySelectorAll('.col_10 .ellipsis')).map(e => e.textContent.trim()),

                    // Images
                    main_image: getImg('.prod_img img'),
                    exhibit_sheet: li.querySelector('.exhibit_sheet_img')?.getAttribute('data-expand-img') || null,

                    // All text for debugging
                    full_text: li.textContent.trim().substring(0, 400),
                };
            });
        }""")

        print(f"\nExtracted {len(vehicles)} vehicles:\n")
        for i, v in enumerate(vehicles[:5]):
            print(f"=== Vehicle {i+1} ===")
            print(f"  Item ID:      {v['item_id']}")
            print(f"  DateTime:     {v['auction_datetime']}")
            print(f"  Location:     {v['location']}")
            print(f"  House:        {v['auction_house']}")
            print(f"  Lot:          {v['lot_number']}")
            print(f"  Col4 (year/model): {v['col_4_texts']}")
            print(f"  Col5 (km/insp):    {v['col_5_texts']}")
            print(f"  Col6 (rating):     {v['col_6_texts']}")
            print(f"  Col7 (price):      {v['col_7_texts']}")
            print(f"  Col8:              {v['col_8_texts']}")
            print(f"  Col9:              {v['col_9_texts']}")
            print(f"  Col10:             {v['col_10_texts']}")
            print(f"  Image:        {v['main_image']}")
            print(f"  Sheet:        {v['exhibit_sheet']}")
            print()

        with open("vehicles_structured.json", "w") as f:
            json.dump(vehicles, f, indent=2, ensure_ascii=False)
        print(f"Saved all {len(vehicles)} vehicles to vehicles_structured.json")

        await browser.close()

asyncio.run(main())
