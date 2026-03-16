"""Quick test: login, search, check pagination controls."""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await ctx.new_page()

        # Login
        await page.goto("https://www.aucneostation.com/", wait_until="networkidle", timeout=30000)
        await page.fill("#userid-pc", "A124332")
        await page.fill("#password-pc", "Japanesemango1289")
        await page.click("button[type='submit']")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(2)
        if "login-error-force" in page.url:
            await page.click("input[name='force_login']")
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(3)

        buy = await page.evaluate("""() => {
            for (const a of document.querySelectorAll('a'))
                if (a.textContent.trim().includes('買いメニュー')) return a.href;
        }""")
        print(f"Logged in")

        # Load search
        await page.goto(buy, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(8)

        # Select all + search
        await page.evaluate("() => document.querySelectorAll('.chk_makers').forEach(c => { if(!c.checked) c.click(); })")
        await asyncio.sleep(0.5)
        await page.evaluate("""() => {
            for (const a of document.querySelectorAll('a'))
                if (a.textContent.includes('この条件で一覧表示')) { a.click(); return; }
        }""")

        # Wait for results
        for _ in range(30):
            await asyncio.sleep(2)
            n = await page.evaluate("() => document.querySelectorAll('#results_list li[data-item_id]').length")
            if n > 0:
                print(f"Results loaded: {n} items")
                break

        # Check pagination controls
        print("\n=== PAGINATION ANALYSIS ===")
        info = await page.evaluate("""() => {
            const result = {};

            // Find all <a> with text 次
            result.next_buttons = Array.from(document.querySelectorAll('a')).filter(a =>
                a.textContent.trim() === '次'
            ).map(a => ({
                text: a.textContent.trim(),
                class: a.className,
                visible: a.offsetParent !== null,
                disabled: a.classList.contains('disabled'),
                href: a.href,
                parent_class: a.parentElement?.className || '',
            }));

            // Find select for display count
            result.display_selects = Array.from(document.querySelectorAll('select')).map(s => ({
                class: s.className,
                value: s.value,
                options: Array.from(s.options).map(o => o.value + ' ' + o.text),
                visible: s.offsetParent !== null,
            }));

            // Count li items
            result.items_count = document.querySelectorAll('#results_list li[data-item_id]').length;

            // Page info text
            const body = document.body.innerText;
            const countMatch = body.match(/(\\d+)台/);
            result.total_text = countMatch ? countMatch[0] : null;

            return result;
        }""")

        print(f"Items on page: {info['items_count']}")
        print(f"Total text: {info['total_text']}")
        print(f"\nNext buttons: {len(info['next_buttons'])}")
        for b in info['next_buttons']:
            print(f"  class='{b['class']}' visible={b['visible']} disabled={b['disabled']} parent='{b['parent_class']}'")

        print(f"\nDisplay selects: {len(info['display_selects'])}")
        for s in info['display_selects']:
            print(f"  class='{s['class']}' value={s['value']} visible={s['visible']} options={s['options']}")

        # Try changing display count
        print("\n=== TRYING 100/PAGE ===")
        await page.select_option('.selDisplayedItems', '100')
        await asyncio.sleep(10)
        n2 = await page.evaluate("() => document.querySelectorAll('#results_list li[data-item_id]').length")
        print(f"After select_option('100'): {n2} items")

        if n2 == info['items_count']:
            # Try jQuery approach
            await page.evaluate("() => { if(window.$) $('.selDisplayedItems').val('100').change(); }")
            await asyncio.sleep(10)
            n3 = await page.evaluate("() => document.querySelectorAll('#results_list li[data-item_id]').length")
            print(f"After jQuery change: {n3} items")

        # Try clicking next
        print("\n=== TRYING NEXT PAGE ===")
        clicked = await page.evaluate("""() => {
            const links = document.querySelectorAll('a');
            for (const a of links) {
                if (a.textContent.trim() === '次' && !a.classList.contains('disabled') && a.offsetParent !== null) {
                    a.click();
                    return 'clicked visible 次';
                }
            }
            // Try any 次
            for (const a of links) {
                if (a.textContent.trim() === '次' && !a.classList.contains('disabled')) {
                    a.click();
                    return 'clicked hidden 次';
                }
            }
            return 'not found';
        }""")
        print(f"Next click: {clicked}")

        await asyncio.sleep(8)
        n4 = await page.evaluate("() => document.querySelectorAll('#results_list li[data-item_id]').length")
        first_id = await page.evaluate("() => document.querySelector('#results_list li[data-item_id]')?.getAttribute('data-item_id')")
        print(f"After next: {n4} items, first id: {first_id}")

        await browser.close()

asyncio.run(main())
