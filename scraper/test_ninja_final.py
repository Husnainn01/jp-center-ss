"""Final test: iframe vs new tab for exhibit sheets with real data.
Tries multiple makers/models until it finds vehicles.
Run: cd scraper && python3 test_ninja_final.py
"""
import asyncio
import time
from playwright.async_api import async_playwright


async def login(context):
    page = await context.new_page()
    await page.goto("https://www.ninja-cartrade.jp/ninja/", wait_until="networkidle", timeout=60000)
    await asyncio.sleep(2)
    await page.fill("#loginId", "L4013V80")
    await page.fill("#password", "93493493")
    await page.evaluate("() => login()")
    await asyncio.sleep(5)
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except:
        pass
    body = await page.inner_text("body")
    if "different user" in body.lower():
        await page.evaluate("""() => { for (const a of document.querySelectorAll('a')) if (a.textContent.trim() === 'Login') { a.click(); return; } }""")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(3)
    return page if "searchcondition" in page.url else None


async def find_vehicles(page):
    """Try makers until we find one with < 1000 vehicles."""
    # Try smaller makers first
    makers_to_try = ['19', '73', '56', '81', '90', '49', '46']  # Mitsuoka, Alfa, MINI, Peugeot, Volvo, Porsche, Audi

    for code in makers_to_try:
        await page.evaluate(f"() => seniBrand('{code}')")
        await asyncio.sleep(3)

        models = await page.evaluate("""() => {
            const r = [];
            document.querySelectorAll('a[onclick*="makerListChoiceCarCat"]').forEach(a => {
                const t = a.textContent.trim();
                const m = t.match(/\\(([\\d,]+)\\)/);
                r.push({ name: t, count: m ? parseInt(m[1].replace(',', '')) : 0 });
            });
            return r;
        }""")
        total = sum(m['count'] for m in models)
        maker_name = await page.evaluate("""() => {
            const sel = document.querySelector('.selected-maker, .maker-selected');
            return sel ? sel.textContent.trim() : '?';
        }""")

        if total > 0 and total < 1000:
            print(f"Found: code={code} total={total}")
            await page.evaluate("() => allSearch()")
            await asyncio.sleep(5)

            for _ in range(10):
                cnt = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
                if cnt > 0:
                    return cnt
                await asyncio.sleep(1)

        if total > 0:
            # Try a small model
            for m in models:
                if 5 <= m['count'] <= 100:
                    print(f"Trying model: {m['name']} ({m['count']})")
                    onclick = await page.evaluate(f"""() => {{
                        for (const a of document.querySelectorAll('a[onclick*="makerListChoiceCarCat"]')) {{
                            if (a.textContent.includes('{m['name'].split("(")[0].strip()}')) return a.getAttribute('onclick');
                        }}
                        return '';
                    }}""")
                    if onclick:
                        await page.evaluate(f"() => {{ {onclick} }}")
                        await asyncio.sleep(5)
                        for _ in range(10):
                            cnt = await page.evaluate("() => document.querySelectorAll('[onclick*=seniCarDetail]').length")
                            if cnt > 0:
                                return cnt
                            await asyncio.sleep(1)

        # Go back to search condition for next maker
        await page.evaluate("() => seniToSearchcondition()")
        await asyncio.sleep(2)

    return 0


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080}, locale="en-US")

        page = await login(context)
        if not page:
            print("Login failed!")
            await browser.close()
            return
        print("Logged in!\n")

        # Find vehicles
        rows = await find_vehicles(page)
        print(f"Rows found: {rows}")

        if rows == 0:
            print("No vehicles found with any maker!")
            await browser.close()
            return

        # Get unique vehicles
        vehicles = await page.evaluate("""() => {
            const r = [];
            const seen = new Set();
            document.querySelectorAll('[onclick*=seniCarDetail]').forEach(el => {
                const m = el.getAttribute('onclick').match(/seniCarDetail\\('(\\d+)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)',\\s*'([^']*)'/);
                if (m && !seen.has(m[4])) {
                    seen.add(m[4]);
                    r.push({ index: m[1], site: m[2], times: m[3], bidNo: m[4], zaikoNo: m[5] });
                }
            });
            return r;
        }""")
        print(f"Unique vehicles: {len(vehicles)}")

        test_count = min(5, len(vehicles))

        # ===== TEST 1: New tab =====
        print(f"\n{'='*60}")
        print(f"NEW TAB ({test_count} vehicles)")
        print(f"{'='*60}")
        t0 = time.time()
        sheets_tab = 0
        for v in vehicles[:test_count]:
            try:
                np = context.wait_for_event("page", timeout=10000)
                await page.evaluate("""(v) => {
                    document.getElementById('carKindType').value = '1';
                    document.getElementById('kaijoCode').value = v.site;
                    document.getElementById('auctionCount').value = v.times;
                    document.getElementById('bidNo').value = v.bidNo;
                    document.getElementById('zaikoNo').value = '';
                    document.getElementById('action').value = 'init';
                    var form = document.getElementById('form1');
                    form.setAttribute('action', './cardetail.action');
                    form.setAttribute('target', '_blank');
                    form.submit();
                }""", v)
                dp = await np
                await dp.wait_for_load_state("networkidle", timeout=15000)
                await asyncio.sleep(1)

                info = await dp.evaluate("""() => {
                    const html = document.documentElement.innerHTML;
                    let sheet = '';
                    for (const img of document.querySelectorAll('img')) {
                        if (img.src.includes('get_ex_image')) { sheet = img.src; break; }
                    }
                    return {
                        sheet,
                        htmlLen: html.length,
                        hasEx: html.includes('get_ex_image'),
                        loggedOut: document.body.innerText.includes('logged out'),
                    };
                }""")
                await dp.close()

                if info['loggedOut']:
                    print(f"  {v['bidNo']}: SESSION DEAD!")
                    break
                elif info['sheet']:
                    sheets_tab += 1
                    print(f"  {v['bidNo']}: SHEET FOUND ({info['htmlLen']} chars)")
                else:
                    print(f"  {v['bidNo']}: no sheet (html={info['htmlLen']}, hasEx={info['hasEx']})")
            except Exception as e:
                print(f"  {v['bidNo']}: ERROR {e}")
                for extra in context.pages[1:]:
                    try: await extra.close()
                    except: pass
        t_tab = time.time() - t0
        await page.evaluate("() => document.getElementById('form1')?.setAttribute('target', '')")
        print(f"  Total: {t_tab:.2f}s | Sheets: {sheets_tab}/{test_count}")

        # ===== TEST 2: Iframe with 2s render wait =====
        print(f"\n{'='*60}")
        print(f"IFRAME + 2s wait ({test_count} vehicles)")
        print(f"{'='*60}")
        t0 = time.time()
        sheets_iframe = 0
        for v in vehicles[:test_count]:
            result = await page.evaluate("""(v) => {
                return new Promise((resolve) => {
                    let f = document.getElementById('_sf');
                    if (!f) {
                        f = document.createElement('iframe');
                        f.id = '_sf'; f.name = '_sf';
                        f.style.cssText = 'position:absolute;left:-9999px;width:800px;height:600px';
                        document.body.appendChild(f);
                    }
                    f.onload = function() {
                        setTimeout(() => {
                            try {
                                const doc = f.contentDocument;
                                const html = doc.documentElement.innerHTML;
                                let sheet = '';
                                // Try img tags first
                                doc.querySelectorAll('img').forEach(img => {
                                    if (img.src.includes('get_ex_image')) sheet = img.src;
                                });
                                // Fallback: HTML regex
                                if (!sheet) {
                                    const m = html.match(/action=get_ex_image&amp;FilePath=([^"&]*)/);
                                    if (m) sheet = './cardetail.action?action=get_ex_image&FilePath=' + m[1];
                                }
                                resolve({
                                    sheet,
                                    htmlLen: html.length,
                                    hasEx: html.includes('get_ex_image'),
                                    loggedOut: doc.body.innerText.includes('logged out'),
                                });
                            } catch(e) { resolve({ error: e.message }); }
                        }, 2000);
                    };
                    document.getElementById('carKindType').value = '1';
                    document.getElementById('kaijoCode').value = v.site;
                    document.getElementById('auctionCount').value = v.times;
                    document.getElementById('bidNo').value = v.bidNo;
                    document.getElementById('zaikoNo').value = '';
                    document.getElementById('action').value = 'init';
                    var form = document.getElementById('form1');
                    form.setAttribute('action', './cardetail.action');
                    form.setAttribute('target', '_sf');
                    form.submit();
                    setTimeout(() => resolve({ error: 'timeout' }), 15000);
                });
            }""", v)

            if result.get('loggedOut'):
                print(f"  {v['bidNo']}: SESSION DEAD!")
                break
            elif result.get('sheet'):
                sheets_iframe += 1
                print(f"  {v['bidNo']}: SHEET FOUND ({result['htmlLen']} chars)")
            else:
                print(f"  {v['bidNo']}: no sheet (html={result.get('htmlLen','?')}, hasEx={result.get('hasEx','?')})")
        t_iframe = time.time() - t0
        await page.evaluate("() => document.getElementById('form1')?.setAttribute('target', '')")
        print(f"  Total: {t_iframe:.2f}s | Sheets: {sheets_iframe}/{test_count}")

        # ===== TEST 3: Batch iframes x5 =====
        print(f"\n{'='*60}")
        print(f"BATCH IFRAME x5 ({test_count} vehicles)")
        print(f"{'='*60}")
        t0 = time.time()
        sheets_batch = 0
        batch = vehicles[:test_count]
        results = await page.evaluate("""(batch) => {
            return new Promise((resolve) => {
                const results = new Array(batch.length).fill(null);
                let done = 0;
                const check = () => {
                    done++;
                    if (done >= batch.length) resolve(results);
                };

                batch.forEach((v, idx) => {
                    const fid = '_bf' + idx;
                    let f = document.getElementById(fid);
                    if (!f) {
                        f = document.createElement('iframe');
                        f.id = fid; f.name = fid;
                        f.style.cssText = 'position:absolute;left:-9999px;width:800px;height:600px';
                        document.body.appendChild(f);
                    }
                    f.onload = () => {
                        setTimeout(() => {
                            try {
                                const doc = f.contentDocument;
                                const html = doc.documentElement.innerHTML;
                                let sheet = '';
                                doc.querySelectorAll('img').forEach(img => {
                                    if (img.src.includes('get_ex_image')) sheet = img.src;
                                });
                                if (!sheet) {
                                    const m = html.match(/action=get_ex_image&amp;FilePath=([^"&]*)/);
                                    if (m) sheet = './cardetail.action?action=get_ex_image&FilePath=' + m[1];
                                }
                                results[idx] = {
                                    sheet, htmlLen: html.length,
                                    hasEx: html.includes('get_ex_image'),
                                    loggedOut: doc.body.innerText.includes('logged out'),
                                };
                            } catch(e) { results[idx] = { error: e.message }; }
                            check();
                        }, 2000);
                    };
                    const orig = document.getElementById('form1');
                    const c = orig.cloneNode(true);
                    c.style.display = 'none';
                    const set = (n, val) => { const el = c.querySelector('[name=' + n + ']'); if (el) el.value = val; };
                    set('carKindType', '1'); set('kaijoCode', v.site); set('auctionCount', v.times);
                    set('bidNo', v.bidNo); set('zaikoNo', ''); set('action', 'init');
                    c.setAttribute('action', './cardetail.action');
                    c.setAttribute('target', fid);
                    document.body.appendChild(c);
                    c.submit();
                    c.remove();
                });
                setTimeout(() => resolve(results), 20000);
            });
        }""", batch)
        for i, r in enumerate(results):
            bid = batch[i]['bidNo']
            if r and r.get('loggedOut'):
                print(f"  {bid}: SESSION DEAD!")
            elif r and r.get('sheet'):
                sheets_batch += 1
                print(f"  {bid}: SHEET FOUND ({r['htmlLen']} chars)")
            else:
                info = f"html={r.get('htmlLen','?')}, hasEx={r.get('hasEx','?')}" if r else "null"
                print(f"  {bid}: no sheet ({info})")
        t_batch = time.time() - t0
        print(f"  Total: {t_batch:.2f}s | Sheets: {sheets_batch}/{test_count}")

        # Session
        alive = await page.evaluate("() => !!document.getElementById('form1')")
        print(f"\nSession alive: {alive}")

        # Summary
        print(f"\n{'='*60}")
        print(f"FINAL RESULTS ({test_count} vehicles)")
        print(f"{'='*60}")
        print(f"  New tabs:       {t_tab:.2f}s ({t_tab/test_count:.2f}s/v) sheets={sheets_tab}")
        print(f"  Iframe seq:     {t_iframe:.2f}s ({t_iframe/test_count:.2f}s/v) sheets={sheets_iframe}")
        print(f"  Batch iframe:   {t_batch:.2f}s ({t_batch/test_count:.2f}s/v) sheets={sheets_batch}")
        if t_tab > 0:
            print(f"\n  Iframe speedup: {t_tab/t_iframe:.1f}x")
            print(f"  Batch speedup:  {t_tab/t_batch:.1f}x")
        print(f"  Results match: tab={sheets_tab} iframe={sheets_iframe} batch={sheets_batch}")

        await browser.close()

asyncio.run(main())
