"""Test: Dump NINJA list page structure to see what data is available
without clicking into detail pages."""

import asyncio
import json
from playwright.async_api import async_playwright
from ninja_login import ninja_login


async def main():
    user_id, password = "L4013V80", "93493493"

    print(f"[test] Logging in as {user_id}...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )

        ok = await ninja_login(context, user_id, password)
        if not ok:
            print("[test] Login failed!")
            await browser.close()
            return

        page = context.pages[0] if context.pages else await context.new_page()
        print(f"[test] Logged in. URL: {page.url[:60]}")

        # Select ISUZU (small maker)
        brand_code = "17"  # ISUZU
        print(f"[test] Selecting ISUZU (code {brand_code})...")
        await page.evaluate(f"() => seniBrand('{brand_code}')")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(3)

        # Select all body types
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="bodytype"]').forEach(cb => {
                if (!cb.checked) cb.click();
            });
        }""")
        await asyncio.sleep(0.5)

        # Get models and pick the smallest one
        models = await page.evaluate("""() => {
            const models = [];
            document.querySelectorAll('a').forEach(a => {
                const onclick = a.getAttribute('onclick') || '';
                const match = onclick.match(/makerListChoiceCarCat\\('(\\d+)'\\)/);
                if (match) {
                    const text = a.textContent.trim();
                    const countMatch = text.match(/(.+?)\\s*\\((\\d+)\\)/);
                    if (countMatch && parseInt(countMatch[2]) > 0) {
                        models.push({ name: countMatch[1], count: parseInt(countMatch[2]), catId: match[1] });
                    }
                }
            });
            models.sort((a, b) => a.count - b.count);
            return models;
        }""")
        print(f"[test] Models found: {len(models)}")
        for m in models[:10]:
            print(f"  {m['name']}: {m['count']} (catId={m['catId']})")

        if not models:
            print("[test] No models, trying allSearch...")
            await page.evaluate("() => allSearch()")
        else:
            # Pick a model with ~20-50 vehicles
            target = next((m for m in models if 5 <= m['count'] <= 100), models[0])
            print(f"[test] Clicking model: {target['name']} ({target['count']} vehicles)")
            await page.evaluate(f"() => makerListChoiceCarCat('{target['catId']}')")

        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(5)

        print(f"[test] Results page URL: {page.url[:80]}")

        # === DUMP 0: Page text ===
        print("\n=== PAGE TEXT (first 80 lines) ===")
        body_text = await page.inner_text("body")
        for i, line in enumerate(body_text.split("\n")[:80]):
            line = line.strip()
            if line:
                print(f"  {line[:150]}")

        # Save full HTML
        html = await page.content()
        with open("ninja_listpage.html", "w") as f:
            f.write(html)
        print("\n[test] Full HTML saved to ninja_listpage.html")

        # === DUMP 1: Raw HTML structure of first few vehicle rows ===
        print("\n=== VEHICLE ROW HTML STRUCTURE ===")
        row_html = await page.evaluate("""() => {
            const els = document.querySelectorAll('[onclick*=seniCarDetail]');
            const results = [];
            const seen = new Set();
            for (const el of els) {
                // Get the closest table row or parent container
                let row = el.closest('tr') || el.closest('div') || el.parentElement;
                if (!row || seen.has(row)) continue;
                seen.add(row);
                results.push({
                    tagName: row.tagName,
                    className: row.className,
                    innerHTML: row.innerHTML.substring(0, 2000),
                    innerText: row.innerText.substring(0, 500),
                });
                if (results.length >= 2) break;
            }
            return results;
        }""")

        for i, row in enumerate(row_html):
            print(f"\n--- Row {i} ({row['tagName']}.{row['className']}) ---")
            print(f"TEXT:\n{row['innerText']}")
            print(f"\nHTML (first 1500):\n{row['innerHTML'][:1500]}")

        # === DUMP 2: All images on the page ===
        print("\n\n=== ALL IMAGES ON LIST PAGE ===")
        images = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('img')).map(img => ({
                src: img.src,
                alt: img.alt || '',
                width: img.naturalWidth,
                height: img.naturalHeight,
                className: img.className || '',
                parentTag: img.parentElement?.tagName || '',
                parentOnclick: (img.parentElement?.getAttribute('onclick') || '').substring(0, 100),
            })).filter(i => i.src && i.src.startsWith('http') && i.width > 50);
        }""")
        print(f"Total images with width>50: {len(images)}")
        for img in images[:10]:
            print(f"  {img['width']}x{img['height']} class={img['className']} parent={img['parentTag']} src={img['src'][:120]}")
            if img['parentOnclick']:
                print(f"    onclick={img['parentOnclick']}")

        # === DUMP 3: Full data extraction attempt from list ===
        print("\n\n=== EXTRACTED DATA PER VEHICLE (from list page) ===")
        vehicles = await page.evaluate("""() => {
            const results = [];
            const els = document.querySelectorAll('[onclick*=seniCarDetail]');
            const seen = new Set();

            for (const el of els) {
                const onclick = el.getAttribute('onclick') || '';
                const match = onclick.match(/seniCarDetail\\('(\\d+)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)'/);
                if (!match) continue;

                const key = match[4];
                if (seen.has(key)) continue;
                seen.add(key);

                // Get the row container
                let row = el.closest('tr') || el.closest('div') || el.parentElement;

                // Get all text, split by cells/divs
                const cells = row ? Array.from(row.querySelectorAll('td, th, div, span')).map(c => c.textContent.trim()).filter(t => t && t.length < 200) : [];
                const text = row ? row.innerText.trim() : '';

                // Get images in this row
                const imgs = row ? Array.from(row.querySelectorAll('img')).map(i => ({
                    src: i.src,
                    w: i.naturalWidth,
                    h: i.naturalHeight,
                })).filter(i => i.src.startsWith('http') && i.w > 30) : [];

                results.push({
                    params: { index: match[1], site: match[2], times: match[3], bidNo: match[4] },
                    text: text.substring(0, 400),
                    cells: cells.slice(0, 30),
                    images: imgs.slice(0, 5),
                });

                if (results.length >= 3) break;
            }
            return results;
        }""")

        for i, v in enumerate(vehicles):
            print(f"\n--- Vehicle {i} (bidNo={v['params']['bidNo']}, site={v['params']['site']}) ---")
            print(f"TEXT: {v['text'][:300]}")
            print(f"\nCELLS ({len(v['cells'])}):")
            for j, cell in enumerate(v['cells']):
                print(f"  [{j}] {cell[:100]}")
            print(f"\nIMAGES ({len(v['images'])}):")
            for img in v['images']:
                print(f"  {img['w']}x{img['h']} {img['src'][:120]}")

        # === DUMP 4: Try to find exhibit sheet links ===
        print("\n\n=== EXHIBIT SHEET / AUCTION SHEET LINKS ===")
        sheet_links = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('a, img').forEach(el => {
                const text = (el.textContent || el.alt || '').trim().toLowerCase();
                const src = el.src || el.href || '';
                const onclick = el.getAttribute('onclick') || '';
                if (text.includes('sheet') || text.includes('exhibit') || text.includes('hyoka') ||
                    src.includes('ex_image') || src.includes('sheet') || src.includes('hyoka') ||
                    onclick.includes('ex_image') || onclick.includes('sheet') || onclick.includes('hyoka')) {
                    results.push({
                        tag: el.tagName,
                        text: text.substring(0, 80),
                        src: src.substring(0, 150),
                        onclick: onclick.substring(0, 150),
                    });
                }
            });
            return results;
        }""")
        print(f"Found {len(sheet_links)} sheet-related elements:")
        for s in sheet_links[:10]:
            print(f"  <{s['tag']}> text='{s['text']}' src={s['src']} onclick={s['onclick']}")

        # Save screenshot
        await page.screenshot(path="ninja_listpage.png", full_page=True)
        print("\n[test] Screenshot saved as ninja_listpage.png")

        await browser.close()
        print("[test] Done!")


if __name__ == "__main__":
    asyncio.run(main())
