"""Ninja scraper local test — login, pick 1 small maker, scrape 1 page.
Tests: login, maker selection, model listing, pagination, sheet fetching speed.
Run: cd scraper && python3 test_ninja_local.py
"""

import asyncio
import os
import time
from dotenv import load_dotenv
load_dotenv()

from playwright.async_api import async_playwright
from ninja_login import ninja_login

USER_ID = os.getenv("NINJA_USER_ID", "L4013V80")
PASSWORD = os.getenv("NINJA_PASSWORD", "93493493")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )

        # === LOGIN ===
        print("Logging in...")
        ok = await ninja_login(context, USER_ID, PASSWORD)
        if not ok:
            print("LOGIN FAILED!")
            await browser.close()
            return

        page = context.pages[-1]
        print(f"Logged in! URL: {page.url[:60]}\n")

        # === Check available JS functions ===
        js_funcs = await page.evaluate("""() => ({
            seniToSearchcondition: typeof seniToSearchcondition === 'function',
            seniBrand: typeof seniBrand === 'function',
            allSearch: typeof allSearch === 'function',
            makerListChoiceCarCat: typeof makerListChoiceCarCat === 'function',
        })""")
        print(f"JS functions: {js_funcs}")

        # === Get maker list ===
        makers = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('a[onclick*="seniBrand"]').forEach(a => {
                const text = a.textContent.trim();
                const onclick = a.getAttribute('onclick') || '';
                const match = onclick.match(/seniBrand\\('([^']+)'/);
                if (text && match) {
                    results.push({ name: text, code: match[1], onclick: onclick.substring(0, 80) });
                }
            });
            return results;
        }""")
        print(f"\nMakers: {len(makers)}")
        for m in makers:
            print(f"  {m['name']} (code: {m['code']})")

        if not makers:
            print("No makers found! Checking page content...")
            body = await page.evaluate("() => document.body.innerText.substring(0, 500)")
            print(body)
            await browser.close()
            return

        # === Pick a small maker for testing ===
        test_maker = None
        for m in makers:
            name_lower = m['name'].lower()
            if any(k in name_lower for k in ['mitsuoka', 'smart', 'fiat', 'mini', 'alfa']):
                test_maker = m
                break
        if not test_maker:
            test_maker = makers[-1]

        print(f"\n{'='*60}")
        print(f"TEST MAKER: {test_maker['name']} (code: {test_maker['code']})")
        print(f"{'='*60}")

        # === Select maker ===
        t0 = time.time()
        await page.evaluate(f"() => seniBrand('{test_maker['code']}')")
        await asyncio.sleep(3)
        t1 = time.time()
        print(f"\nMaker selection: {t1-t0:.1f}s")

        # === Get model list for this maker ===
        models = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('a[onclick*="makerListChoiceCarCat"]').forEach(a => {
                const text = a.textContent.trim();
                const onclick = a.getAttribute('onclick') || '';
                if (text) {
                    const countMatch = text.match(/\\(([\\d,]+)\\)/);
                    const count = countMatch ? parseInt(countMatch[1].replace(',', '')) : 0;
                    const name = text.replace(/\\([\\d,]+\\)/, '').trim();
                    results.push({ name, count, onclick: onclick.substring(0, 100) });
                }
            });
            results.sort((a, b) => b.count - a.count);
            return results;
        }""")

        total_vehicles = sum(m['count'] for m in models)
        print(f"Models: {len(models)} ({total_vehicles} vehicles total)")
        for m in models[:10]:
            print(f"  {m['name']}: {m['count']}")
        if len(models) > 10:
            print(f"  ... and {len(models) - 10} more")

        # === Try allSearch (full search for this maker) ===
        if total_vehicles < 1000:
            print(f"\n--- allSearch (under 1000 limit) ---")
            t0 = time.time()
            await page.evaluate("() => allSearch()")
            await asyncio.sleep(5)
            t1 = time.time()

            total_text = await page.evaluate("""() => {
                const text = document.body.innerText;
                const m = text.match(/(\\d[\\d,]*)\\s*台/);
                return m ? m[1] : '?';
            }""")
            rows = await page.evaluate("() => document.querySelectorAll('#results_list tr, table tr').length")
            print(f"allSearch: {t1-t0:.1f}s — {total_text} results, {rows} rows")

            # === Switch to 100/page ===
            print(f"\n--- Page size ---")
            switched = await page.evaluate("""() => {
                const sel = document.querySelector('select.selDisplayedItems, select[name*="display"]');
                if (sel) {
                    sel.value = '100';
                    sel.dispatchEvent(new Event('change'));
                    return true;
                }
                // Try clicking 100 button
                for (const a of document.querySelectorAll('a')) {
                    if (a.textContent.trim() === '100' && a.getAttribute('onclick')) {
                        a.click();
                        return true;
                    }
                }
                return false;
            }""")
            await asyncio.sleep(3)

            rows_after = await page.evaluate("() => document.querySelectorAll('#results_list li[data-item_id], table.result tr').length")
            print(f"Switched to 100/page: {switched}, rows now: {rows_after}")

            # === Extract vehicle data from first page ===
            vehicles = await page.evaluate("""() => {
                const results = [];
                // Try USS/Ninja result format
                const items = document.querySelectorAll('#result_list tr, #results_list li, table tr');
                items.forEach((item, idx) => {
                    if (idx > 5) return;
                    const tds = item.querySelectorAll('td');
                    const text = item.textContent.trim().substring(0, 200);
                    const imgs = item.querySelectorAll('img');
                    const imgSrcs = Array.from(imgs).map(i => i.src).filter(s => s && !s.includes('spacer'));
                    results.push({
                        text: text.substring(0, 100),
                        tdCount: tds.length,
                        imgCount: imgSrcs.length,
                        firstImg: imgSrcs[0]?.substring(0, 80) || '',
                    });
                });
                return results;
            }""")
            print(f"\nFirst page vehicles ({len(vehicles)}):")
            for v in vehicles[:5]:
                print(f"  [{v['tdCount']} cells, {v['imgCount']} imgs] {v['text'][:80]}")
                if v['firstImg']:
                    print(f"    img: {v['firstImg']}")

            # === Test form-based detail page (exhibit sheet) ===
            print(f"\n--- Exhibit Sheet Fetch Test ---")
            has_form = await page.evaluate("() => !!document.getElementById('form1')")
            print(f"form1 exists: {has_form}")

            if has_form:
                # Get RV values or bidNo values
                rv_info = await page.evaluate("""() => {
                    const form = document.getElementById('form1');
                    const fields = {};
                    if (form) {
                        for (const inp of form.querySelectorAll('input[type=hidden]')) {
                            fields[inp.name] = inp.value;
                        }
                    }
                    // Also get first few vehicle identifiers
                    const ids = [];
                    document.querySelectorAll('[data-item_id], input[name="bidNo"]').forEach(el => {
                        ids.push(el.getAttribute('data-item_id') || el.value);
                    });
                    return { formFields: Object.keys(fields).slice(0, 10), vehicleIds: ids.slice(0, 5) };
                }""")
                print(f"Form fields: {rv_info['formFields']}")
                print(f"Vehicle IDs: {rv_info['vehicleIds']}")

                # Try opening 1 detail page sequentially
                if rv_info['vehicleIds']:
                    t0 = time.time()
                    try:
                        # Parse bidNo and times from item_id (format: uss-{bidNo}-{times})
                        item_id = rv_info['vehicleIds'][0]
                        parts = item_id.split("-") if "-" in item_id else [item_id]

                        new_page_promise = context.wait_for_event("page", timeout=10000)
                        await page.evaluate("""(v) => {
                            document.getElementById('carKindType').value = '1';
                            document.getElementById('bidNo').value = v.bidNo;
                            document.getElementById('auctionCount').value = v.times;
                            document.getElementById('zaikoNo').value = '';
                            document.getElementById('action').value = 'init';
                            var form = document.getElementById('form1');
                            form.setAttribute('action', './cardetail.action');
                            form.setAttribute('target', '_blank');
                            form.submit();
                        }""", {"bidNo": parts[1] if len(parts) > 1 else parts[0],
                               "times": parts[2] if len(parts) > 2 else "1"})

                        detail_page = await new_page_promise
                        await detail_page.wait_for_load_state("domcontentloaded", timeout=10000)
                        await asyncio.sleep(1)

                        sheet_url = await detail_page.evaluate("""() => {
                            for (const img of document.querySelectorAll('img')) {
                                if (img.src && img.src.includes('get_ex_image')) return img.src;
                            }
                            return 'NOT FOUND';
                        }""")

                        all_imgs = await detail_page.evaluate("""() => {
                            return Array.from(document.querySelectorAll('img'))
                                .filter(i => i.naturalWidth > 50)
                                .map(i => ({ src: i.src.substring(0, 80), w: i.naturalWidth }));
                        }""")

                        await detail_page.close()
                        t1 = time.time()
                        print(f"\nDetail page: {t1-t0:.2f}s")
                        print(f"  Sheet: {sheet_url[:80]}")
                        print(f"  Images: {len(all_imgs)}")
                        for img in all_imgs[:3]:
                            print(f"    [{img['w']}px] {img['src']}")

                        # Now test PARALLEL (3 at once)
                        if len(rv_info['vehicleIds']) >= 3:
                            print(f"\n--- Parallel Test (3 vehicles) ---")
                            t0 = time.time()

                            async def fetch_sheet(vid):
                                parts = vid.split("-") if "-" in vid else [vid]
                                bid_no = parts[1] if len(parts) > 1 else parts[0]
                                times = parts[2] if len(parts) > 2 else "1"
                                try:
                                    np = context.wait_for_event("page", timeout=10000)
                                    await page.evaluate("""(v) => {
                                        document.getElementById('bidNo').value = v.bidNo;
                                        document.getElementById('auctionCount').value = v.times;
                                        var form = document.getElementById('form1');
                                        form.setAttribute('target', '_blank');
                                        form.submit();
                                    }""", {"bidNo": bid_no, "times": times})
                                    dp = await np
                                    await dp.wait_for_load_state("domcontentloaded", timeout=10000)
                                    await asyncio.sleep(0.5)
                                    url = await dp.evaluate("""() => {
                                        for (const img of document.querySelectorAll('img')) {
                                            if (img.src && img.src.includes('get_ex_image')) return img.src;
                                        }
                                        return '';
                                    }""")
                                    await dp.close()
                                    return url
                                except Exception as e:
                                    return f"ERROR: {e}"

                                    # Close any extra pages
                                    for extra in context.pages[1:]:
                                        try: await extra.close()
                                        except: pass

                            # Sequential: one by one
                            results = []
                            for vid in rv_info['vehicleIds'][1:4]:
                                r = await fetch_sheet(vid)
                                results.append(r)

                            t1 = time.time()
                            print(f"Sequential (3 vehicles): {t1-t0:.2f}s")
                            for r in results:
                                print(f"  {r[:60] if r else 'none'}")

                    except Exception as e:
                        print(f"Detail page error: {e}")

                # Reset form target
                try:
                    await page.evaluate("() => document.getElementById('form1')?.setAttribute('target', '')")
                except:
                    pass

        else:
            print(f"Total > 1000 ({total_vehicles}), would need model-by-model search")

        print(f"\n{'='*60}")
        print("TEST COMPLETE")
        print(f"{'='*60}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
