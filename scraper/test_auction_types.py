"""Quick test: login to Aucnet and list all auction type checkboxes on the search page."""

import asyncio
import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from login import ensure_session
from db import get_credentials

load_dotenv()


async def main():
    user_id, password = get_credentials()
    if not user_id:
        user_id = "A124332"
        password = "Japanesemango1289"

    print(f"[test] Logging in as {user_id}...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )

        buy_href = await ensure_session(context, user_id, password)
        if not buy_href:
            print("[test] Login failed!")
            await browser.close()
            return

        print(f"[test] Logged in. Navigating to buy page...")
        page = await context.new_page()
        await page.goto(buy_href, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(5)

        # Find ALL checkboxes and their labels on the page
        checkboxes = await page.evaluate("""() => {
            const results = [];

            // Look for all checkbox inputs
            document.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                const label = cb.parentElement?.textContent?.trim() || '';
                const name = cb.name || '';
                const id = cb.id || '';
                const className = cb.className || '';
                const checked = cb.checked;
                results.push({ name, id, className, label: label.substring(0, 80), checked });
            });

            return results;
        }""")

        print(f"\n[test] Found {len(checkboxes)} checkboxes:\n")
        for cb in checkboxes:
            status = "✓" if cb["checked"] else "✗"
            print(f"  [{status}] name={cb['name']:<30} class={cb['className']:<20} label={cb['label']}")

        # Also look for auction type specific elements
        print("\n\n[test] Looking for auction type sections...")
        sections = await page.evaluate("""() => {
            const results = [];
            // Look for text containing known auction types
            const keywords = ['TV', 'GOOD VALUE', 'SAKIDORI', 'Shared', 'Ichigeki', 'Gold', 'Silver', 'Inspected', 'Self-inspection', 'Newest', 'ALL'];
            const allText = document.querySelectorAll('label, span, div, td, th');
            allText.forEach(el => {
                const text = el.textContent.trim();
                if (text.length < 100 && keywords.some(k => text.includes(k))) {
                    const checkbox = el.querySelector('input[type="checkbox"]') || el.closest('label')?.querySelector('input[type="checkbox"]');
                    results.push({
                        text: text.substring(0, 80),
                        tag: el.tagName,
                        hasCheckbox: !!checkbox,
                        checkboxName: checkbox?.name || '',
                        checked: checkbox?.checked || false,
                    });
                }
            });
            return results;
        }""")

        for s in sections:
            status = "✓" if s["checked"] else "✗"
            print(f"  [{status}] {s['tag']}: {s['text']}")
            if s["hasCheckbox"]:
                print(f"       checkbox name: {s['checkboxName']}")

        await asyncio.sleep(3)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
