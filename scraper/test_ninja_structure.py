"""Discover NINJA search page structure: sites, body types, sections."""

import asyncio
import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from ninja_login import ninja_login
from db import get_site_credentials

load_dotenv()


async def main():
    user_id, password = get_site_credentials("uss")
    if not user_id:
        user_id, password = "L4013V80", "93493493"

    print(f"[test] Logging in as {user_id}...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
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
        print("[test] Logged in. Going to search...")

        # Go to search
        await page.evaluate("() => seniToSearchcondition()")
        await page.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(3)

        # Click TOYOTA as test maker
        await page.evaluate("""() => {
            for (const a of document.querySelectorAll('a'))
                if (a.textContent.trim() === '・TOYOTA') { a.click(); return; }
        }""")
        await page.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(3)

        # Now we should be on the condition/model page
        # Let's discover what's on this page
        print("\n=== PAGE URL ===")
        print(page.url)

        print("\n=== ALL LINKS (clickable elements) ===")
        links = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('a').forEach(a => {
                const text = a.textContent.trim();
                const onclick = a.getAttribute('onclick') || '';
                const href = a.getAttribute('href') || '';
                if (text && text.length < 80) {
                    results.push({ text, onclick: onclick.substring(0, 100), href: href.substring(0, 100) });
                }
            });
            return results;
        }""")
        for l in links:
            print(f"  [{l['text']}] onclick={l['onclick']} href={l['href']}")

        print("\n=== CHECKBOXES ===")
        checkboxes = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                const label = cb.closest('label')?.textContent?.trim() ||
                              cb.parentElement?.textContent?.trim() || '';
                results.push({
                    name: cb.name || '',
                    id: cb.id || '',
                    className: cb.className || '',
                    checked: cb.checked,
                    label: label.substring(0, 60),
                });
            });
            return results;
        }""")
        for cb in checkboxes:
            status = "✓" if cb["checked"] else "✗"
            print(f"  [{status}] name={cb['name']:<30} class={cb['className']:<20} label={cb['label']}")

        print("\n=== SELECT DROPDOWNS ===")
        selects = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('select').forEach(sel => {
                const options = [];
                sel.querySelectorAll('option').forEach(opt => {
                    options.push({ value: opt.value, text: opt.textContent.trim() });
                });
                results.push({ name: sel.name, id: sel.id, options: options.slice(0, 10) });
            });
            return results;
        }""")
        for s in selects:
            print(f"  select name={s['name']} id={s['id']}")
            for opt in s['options']:
                print(f"    {opt['value']}: {opt['text']}")

        print("\n=== SITE/VENUE SECTIONS ===")
        sites = await page.evaluate("""() => {
            const results = [];
            // Look for site names like SAPPORO, TOKYO, etc.
            const allText = document.body.innerText;
            const sitePatterns = ['SAPPORO', 'TOKYO', 'NAGOYA', 'OSAKA', 'KOBE', 'FUKUOKA', 'SENDAI', 'NIIGATA', 'SHIZUOKA', 'KYUSHU'];
            sitePatterns.forEach(site => {
                if (allText.includes(site)) {
                    results.push(site);
                }
            });

            // Also find any elements with "site" related content
            document.querySelectorAll('td, th, div, span, label').forEach(el => {
                const text = el.textContent.trim();
                if (text.length > 2 && text.length < 30 && /^[A-Z]/.test(text) && !text.includes(' ')) {
                    // Could be a site name
                }
            });

            return results;
        }""")
        print(f"  Found sites in page text: {sites}")

        # Take screenshot for reference
        await page.screenshot(path="ninja_search_page.png", full_page=True)
        print("\n[test] Screenshot saved as ninja_search_page.png")

        # Now try clicking conditionSearch to go deeper
        print("\n=== TRYING conditionSearch() ===")
        try:
            await page.evaluate("() => conditionSearch()")
            await page.wait_for_load_state("networkidle", timeout=15000)
            await asyncio.sleep(3)

            print(f"Page URL after conditionSearch: {page.url}")

            # Discover what's on this page
            links2 = await page.evaluate("""() => {
                const results = [];
                document.querySelectorAll('a').forEach(a => {
                    const text = a.textContent.trim();
                    const onclick = a.getAttribute('onclick') || '';
                    if (text && text.length < 80 && text.length > 1) {
                        results.push({ text, onclick: onclick.substring(0, 120) });
                    }
                });
                return results;
            }""")

            print("\n=== LINKS AFTER conditionSearch ===")
            for l in links2:
                print(f"  [{l['text']}] onclick={l['onclick']}")

            await page.screenshot(path="ninja_condition_page.png", full_page=True)
            print("\n[test] Screenshot saved as ninja_condition_page.png")

        except Exception as e:
            print(f"conditionSearch failed: {e}")

        await asyncio.sleep(2)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
