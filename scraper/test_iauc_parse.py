"""Debug iAUC detail page parsing — extract structured data from DOM."""

import asyncio
from dotenv import load_dotenv
load_dotenv()
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        # Login
        await page.goto("https://www.iauc.co.jp/service/", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)
        await page.evaluate("""() => { document.querySelectorAll('a').forEach(el => { if ((el.textContent||'').trim().includes('LOGIN')) el.click(); }); }""")
        await asyncio.sleep(3)
        await page.fill('input[name="id"]', "A124332")
        await page.fill('input[name="password"]', "emlo4732")
        await page.evaluate("""() => { document.querySelectorAll('button,input,a').forEach(el => { if ((el.value||el.textContent||'').trim().includes('LOGIN')) el.click(); }); }""")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(3)
        body = await page.inner_text("body")
        if "はい Yes" in body:
            await page.click(".button-yes")
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(5)

        # English
        await page.evaluate("() => { const el = document.querySelector('a.jp'); if (el) el.click(); }")
        await page.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(3)

        # Navigate through search to get to a detail page
        # Uncheck Kyoyuzaiko, Next
        await page.evaluate("""() => { document.querySelectorAll('input[name="e[]"]').forEach(cb => { if (cb.checked) cb.click(); }); }""")
        await asyncio.sleep(1)
        await page.evaluate('() => check_sites(document.querySelector(".page-next-button"))')
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(5)

        # Select TOYOTA
        box = await page.evaluate("""() => {
            for (const li of document.querySelectorAll('li.search-maker-checkbox'))
                if (li.textContent.trim() === 'TOYOTA') {
                    const r = li.getBoundingClientRect();
                    return { x: r.x + r.width/2, y: r.y + r.height/2 };
                }
        }""")
        await page.mouse.click(box['x'], box['y'])
        await asyncio.sleep(3)

        # Select AQUA
        model_boxes = await page.evaluate("""() => {
            const items = [];
            document.querySelectorAll('input[name="type[]"]').forEach(inp => {
                const li = inp.closest('li');
                if (li) {
                    const r = li.getBoundingClientRect();
                    if (r.y > 0) items.push({ name: inp.getAttribute('data-name'), x: r.x + r.width/2, y: r.y + r.height/2 });
                }
            });
            return items;
        }""")
        for m in model_boxes:
            if m['name'] == 'AQUA':
                await page.mouse.click(m['x'], m['y'])
                break
        await asyncio.sleep(2)
        await page.click('#next-bottom')
        await page.wait_for_load_state("networkidle", timeout=60000)
        await asyncio.sleep(10)

        # Wait for images
        for _ in range(10):
            cnt = await page.evaluate("() => document.querySelectorAll('img[src*=\"iauc_pic\"]').length")
            if cnt > 0: break
            await asyncio.sleep(2)

        # Click first car image
        car_img = page.locator('img[src*="iauc_pic"]').first
        await car_img.click()
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(5)
        print(f"Detail URL: {page.url}")

        # Extract data using DOM traversal
        data = await page.evaluate("""() => {
            const result = {};
            const labels = ['Lot No.', 'Grade', 'Year', 'cc', 'Inspection', 'Transmission',
                           'Score', 'Exterior', 'Interior', 'Doors', 'Color', 'Color No.',
                           'Odometer', 'Start Price', 'Auction Site', 'Holding Date',
                           'Equipment', 'Result', 'Number of Times Held', 'Status', 'Fuel',
                           'Seats', 'Vehicle History', 'A/C', 'Bidding Deadline',
                           'Load Capacity', 'Corrections'];

            // Method 1: Find td/th pairs
            const cells = document.querySelectorAll('td, th');
            for (let i = 0; i < cells.length; i++) {
                const text = cells[i].textContent.trim();
                if (labels.includes(text) && i + 1 < cells.length) {
                    result[text] = cells[i + 1].textContent.trim().substring(0, 100);
                }
            }

            // Method 2: Parse from body text if method 1 missed fields
            const bodyText = document.body.innerText;
            for (const label of labels) {
                if (result[label]) continue;
                const regex = new RegExp(label + '\\s*\\n\\s*(.+)', 'm');
                const match = bodyText.match(regex);
                if (match) {
                    result[label] = match[1].trim().substring(0, 100);
                }
            }

            // Get maker/model
            const makers = ['TOYOTA','LEXUS','NISSAN','HONDA','MAZDA','MITSUBISHI','SUBARU',
                          'DAIHATSU','SUZUKI','BMW','MERCEDES-BENZ','AUDI','VOLKSWAGEN','PORSCHE',
                          'ISUZU','HINO','VOLVO','JAGUAR','FORD','GM','CHRYSLER'];
            const lines = bodyText.split('\\n').map(l => l.trim()).filter(l => l);
            for (let i = 0; i < lines.length; i++) {
                if (makers.includes(lines[i])) {
                    result['_maker'] = lines[i];
                    if (i + 1 < lines.length) {
                        result['_model'] = lines[i + 1];
                    }
                    break;
                }
            }

            return result;
        }""")

        print("\nExtracted fields:")
        for k, v in sorted(data.items()):
            print(f"  {k}: {v}")

        # Also dump raw text for reference
        raw = await page.inner_text("body")
        # Find the data section (after "Place Bid" and before "auction sheet")
        start = raw.find("Lot No.")
        end = raw.find("Check the following")
        if start > 0 and end > 0:
            print(f"\nRaw detail section:")
            print(raw[start:end])

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
