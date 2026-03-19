"""Test: Dump iAUC search results list page to see what data + images
are available without clicking into detail pages."""

import asyncio
import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from iauc_login import iauc_login

load_dotenv()


async def main():
    user_id = os.getenv("IAUC_USER_ID", "")
    password = os.getenv("IAUC_PASSWORD", "")
    if not user_id or not password:
        print("Set IAUC_USER_ID and IAUC_PASSWORD in .env")
        return

    print(f"[test] Logging in as {user_id}...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        ok = await iauc_login(page, user_id, password)
        if not ok:
            print("[test] Login failed!")
            await browser.close()
            return
        print(f"[test] Logged in. URL: {page.url[:60]}")

        # === Step 1: Select all auctions ===
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="e[]"]').forEach(cb => { if (cb.checked) cb.click(); });
            document.querySelectorAll('input[name="d[]"]').forEach(cb => { if (cb.checked) cb.click(); });
        }""")
        await asyncio.sleep(1)
        await page.click("a.title-button.checkbox_on_all")
        await asyncio.sleep(1)

        checked = await page.evaluate('() => document.querySelectorAll(\'input[name="d[]"]:checked\').length')
        print(f"[test] {checked} auction sites selected")

        # === Step 2: Go to Make & Model ===
        await page.evaluate('() => check_sites(document.querySelector(".page-next-button"))')
        for _ in range(20):
            await asyncio.sleep(2)
            if "#maker" in page.url or "search" in page.url:
                break
        await asyncio.sleep(3)
        print(f"[test] Make & Model page: {page.url[:60]}")

        # === Step 3: Select a small maker (ISUZU) ===
        print("[test] Selecting ISUZU only...")
        # Uncheck all first
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="maker[]"]:checked').forEach(inp => inp.click());
        }""")
        await asyncio.sleep(0.5)

        # Click ISUZU
        maker_boxes = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('li.search-maker-checkbox')).map(li => {
                const r = li.getBoundingClientRect();
                return { text: li.textContent.trim(), x: r.x + r.width/2, y: r.y + r.height/2, visible: r.y > 0 };
            }).filter(m => m.visible);
        }""")
        for m in maker_boxes:
            label = m['text'].split('(')[0].strip().upper()
            if label == "ISUZU":
                await page.mouse.click(m['x'], m['y'])
                print(f"  Clicked ISUZU: {m['text']}")
                break
        await asyncio.sleep(2)

        # Get models
        models = await page.evaluate("""() => {
            const items = [];
            document.querySelectorAll('input[name="type[]"]').forEach((inp, idx) => {
                const name = inp.getAttribute('data-name') || '';
                const cnt = parseInt(inp.getAttribute('data-cnt') || '0');
                if (cnt > 0) items.push({ name, cnt, idx });
            });
            items.sort((a, b) => a.cnt - b.cnt);
            return items;
        }""")
        print(f"[test] {len(models)} models found:")
        for m in models[:10]:
            print(f"  {m['name']}: {m['cnt']} vehicles (idx={m['idx']})")

        if not models:
            print("[test] No models found, trying TOYOTA instead...")
            # Click TOYOTA
            for m in maker_boxes:
                label = m['text'].split('(')[0].strip().upper()
                if label == "TOYOTA":
                    await page.mouse.click(m['x'], m['y'])
                    print(f"  Clicked TOYOTA: {m['text']}")
                    break
            await asyncio.sleep(2)
            models = await page.evaluate("""() => {
                const items = [];
                document.querySelectorAll('input[name="type[]"]').forEach((inp, idx) => {
                    const name = inp.getAttribute('data-name') || '';
                    const cnt = parseInt(inp.getAttribute('data-cnt') || '0');
                    if (cnt > 0) items.push({ name, cnt, idx });
                });
                items.sort((a, b) => a.cnt - b.cnt);
                return items;
            }""")
            print(f"[test] {len(models)} models found")
            for m in models[:5]:
                print(f"  {m['name']}: {m['cnt']} vehicles")

        # Select first few small models
        to_select = models[:3]
        indices = [m['idx'] for m in to_select]
        await page.evaluate("""(indices) => {
            const inputs = document.querySelectorAll('input[name="type[]"]');
            indices.forEach(idx => {
                if (inputs[idx] && !inputs[idx].checked) inputs[idx].click();
            });
        }""", indices)
        await asyncio.sleep(1)
        print(f"[test] Selected {len(to_select)} models: {[m['name'] for m in to_select]}")

        # === Step 4: Click Next to get results ===
        await page.evaluate('() => { var b = document.querySelector("#next-bottom"); if (b) { b.disabled = false; b.click(); } }')
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass
        await asyncio.sleep(8)
        print(f"[test] Results page URL: {page.url[:80]}")

        # Wait for vehicle images
        for _ in range(10):
            cnt = await page.evaluate("() => document.querySelectorAll('img[data-code]').length")
            if cnt > 0:
                break
            await asyncio.sleep(2)

        # === DUMP 1: Page text ===
        print("\n=== PAGE TEXT (first 50 lines) ===")
        body_text = await page.inner_text("body")
        for i, line in enumerate(body_text.split("\n")[:50]):
            line = line.strip()
            if line:
                print(f"  {line[:180]}")

        # === DUMP 2: Vehicle rows / cards ===
        print("\n=== VEHICLE ELEMENTS ===")
        vehicles = await page.evaluate("""() => {
            const results = [];
            const codes = document.querySelectorAll('img[data-code]');
            const seen = new Set();

            for (const img of codes) {
                const code = img.getAttribute('data-code');
                if (!code || seen.has(code)) continue;
                seen.add(code);

                // Find the parent container
                let container = img.closest('tr') || img.closest('div') || img.closest('li') || img.parentElement?.parentElement;

                // Get all text in the container
                const text = container ? container.innerText.trim() : '';

                // Get all images in the container
                const imgs = container ? Array.from(container.querySelectorAll('img')).map(i => ({
                    src: i.src || '',
                    dataSrc: i.getAttribute('data-src') || '',
                    alt: i.alt || '',
                    w: i.naturalWidth,
                    h: i.naturalHeight,
                    className: i.className || '',
                })).filter(i => (i.src || i.dataSrc) && (i.w > 30 || i.dataSrc)) : [];

                // Get the container's HTML
                const html = container ? container.innerHTML.substring(0, 1500) : '';

                results.push({
                    code,
                    text: text.substring(0, 500),
                    images: imgs.slice(0, 5),
                    html: html.substring(0, 1000),
                    containerTag: container ? container.tagName + '.' + container.className : 'none',
                });

                if (results.length >= 3) break;
            }
            return results;
        }""")

        for i, v in enumerate(vehicles):
            print(f"\n--- Vehicle {i} (code={v['code']}) container={v['containerTag']} ---")
            print(f"TEXT:\n{v['text'][:400]}")
            print(f"\nIMAGES ({len(v['images'])}):")
            for img in v['images']:
                src = img['src'][:120] or img['dataSrc'][:120]
                print(f"  {img['w']}x{img['h']} class={img['className']} src={src}")
            print(f"\nHTML:\n{v['html'][:800]}")

        # === DUMP 3: All images on page ===
        print("\n\n=== ALL IMAGES ON RESULTS PAGE ===")
        all_imgs = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('img')).map(i => ({
                src: i.src || '',
                dataSrc: i.getAttribute('data-src') || '',
                dataCode: i.getAttribute('data-code') || '',
                w: i.naturalWidth,
                h: i.naturalHeight,
                className: i.className || '',
            })).filter(i => (i.src && i.src.startsWith('http') && i.w > 30) || i.dataSrc);
        }""")
        print(f"Total: {len(all_imgs)} images")
        for img in all_imgs[:15]:
            tag = ""
            if img['dataCode']:
                tag = f" [code={img['dataCode']}]"
            if 'iauc_pic' in (img['src'] + img.get('dataSrc', '')):
                tag += " ★ iauc_pic"
            src = img['src'][:130] or img['dataSrc'][:130]
            print(f"  {img['w']}x{img['h']} class={img['className']}{tag} src={src}")

        # === DUMP 4: Check for exhibit sheet / auction sheet patterns ===
        print("\n\n=== EXHIBIT SHEET PATTERNS ===")
        sheet_elements = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('img, a').forEach(el => {
                const src = el.src || el.href || '';
                const alt = el.alt || '';
                const text = el.textContent || '';
                const dataCode = el.getAttribute('data-code') || '';
                if (src.includes('sheet') || src.includes('exhibit') || src.includes('hyouka') ||
                    alt.includes('sheet') || text.includes('sheet') ||
                    (src.includes('iauc_pic') && src.toUpperCase().includes('/A'))) {
                    results.push({ tag: el.tagName, src: src.substring(0, 200), alt, dataCode });
                }
            });
            return results;
        }""")
        print(f"Found {len(sheet_elements)} sheet-related elements:")
        for s in sheet_elements[:10]:
            print(f"  <{s['tag']}> code={s['dataCode']} alt={s['alt']} src={s['src'][:150]}")

        # === DUMP 5: Check links/onclick handlers for detail navigation ===
        print("\n\n=== DETAIL LINKS / ONCLICK HANDLERS ===")
        links = await page.evaluate("""() => {
            const results = [];
            const seen = new Set();
            document.querySelectorAll('a[href*="detail"], a[onclick*="detail"], [onclick*="vehicleId"]').forEach(el => {
                const href = el.href || '';
                const onclick = el.getAttribute('onclick') || '';
                const key = href + onclick;
                if (seen.has(key)) return;
                seen.add(key);
                results.push({
                    tag: el.tagName,
                    href: href.substring(0, 200),
                    onclick: onclick.substring(0, 200),
                    text: el.textContent.trim().substring(0, 50),
                });
            });
            return results.slice(0, 5);
        }""")
        for l in links:
            print(f"  <{l['tag']}> text='{l['text']}' href={l['href']} onclick={l['onclick']}")

        # Save screenshot and HTML
        await page.screenshot(path="iauc_listpage.png", full_page=True)
        html = await page.content()
        with open("iauc_listpage.html", "w") as f:
            f.write(html)
        print("\n[test] Screenshot: iauc_listpage.png, HTML: iauc_listpage.html")

        await browser.close()
        print("[test] Done!")


if __name__ == "__main__":
    asyncio.run(main())
