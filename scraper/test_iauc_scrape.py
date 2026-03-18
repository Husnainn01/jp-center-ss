"""Test iAUC: login → search TOYOTA AQUA → scrape 3 vehicles with images → save to DB."""

import asyncio
import base64
import re
from dotenv import load_dotenv
load_dotenv()

from playwright.async_api import async_playwright, Page
from db import upsert_auctions
from storage import upload_image


async def iauc_login(page: Page) -> bool:
    """Login to iAUC with force-login handling."""
    await page.goto("https://www.iauc.co.jp/service/", wait_until="networkidle", timeout=30000)
    await asyncio.sleep(2)
    await page.evaluate("""() => {
        document.querySelectorAll('a').forEach(el => {
            if ((el.textContent || '').trim().includes('LOGIN')) el.click();
        });
    }""")
    await asyncio.sleep(3)
    await page.fill('input[name="id"]', "A124332")
    await page.fill('input[name="password"]', "emlo4732")
    await page.evaluate("""() => {
        document.querySelectorAll('button, input, a').forEach(el => {
            if ((el.value || el.textContent || '').trim().includes('LOGIN')) el.click();
        });
    }""")
    await page.wait_for_load_state("networkidle", timeout=30000)
    await asyncio.sleep(3)
    body = await page.inner_text("body")
    if "はい Yes" in body:
        print("  [iauc] Force login...")
        await page.click(".button-yes")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(5)
    return "vehicle" in page.url


async def download_and_upload(page: Page, url: str) -> str | None:
    """Download image via authenticated browser and upload to R2."""
    try:
        result = await page.evaluate("""async (url) => {
            try {
                const res = await fetch(url, { credentials: 'include' });
                if (!res.ok) return null;
                const blob = await res.blob();
                const reader = new FileReader();
                return new Promise(r => { reader.onloadend = () => r(reader.result); reader.readAsDataURL(blob); });
            } catch { return null; }
        }""", url)
        if result and result.startswith("data:"):
            b64 = result.split(",", 1)[1]
            img_bytes = base64.b64decode(b64)
            if len(img_bytes) > 500:
                s3_url = upload_image(img_bytes, "iauc-images", url)
                if s3_url:
                    return s3_url
        return None
    except:
        return None


def parse_detail(text: str, vehicle_id: str) -> dict:
    """Parse iAUC detail page text into vehicle dict.
    Fields are tab-separated: 'Label\\tValue' per line."""

    # Build field map from tab-separated lines
    fields = {}
    for line in text.split("\n"):
        line = line.strip()
        if "\t" in line:
            parts = line.split("\t", 1)
            if len(parts) == 2:
                fields[parts[0].strip()] = parts[1].strip()

    # Get maker/model from body text
    maker = ""
    model = ""
    known_makers = ["TOYOTA", "LEXUS", "NISSAN", "HONDA", "MAZDA", "MITSUBISHI",
                    "SUBARU", "DAIHATSU", "SUZUKI", "BMW", "MERCEDES-BENZ", "AUDI",
                    "VOLKSWAGEN", "PORSCHE", "ISUZU", "HINO", "VOLVO", "JAGUAR",
                    "FORD", "GM", "CHRYSLER", "ALFA ROMEO", "FIAT", "FERRARI",
                    "MASERATI", "OPEL", "SMART", "ROVER", "BENTLEY", "TESLA",
                    "PEUGEOT", "RENAULT", "CITROEN", "LAMBORGHINI", "BYD"]
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for i, line in enumerate(lines):
        if line in known_makers:
            maker = line
            if i + 1 < len(lines):
                model = lines[i + 1].strip()
            break

    # Extract fields
    lot_no = fields.get("Lot No.", "")
    grade = fields.get("Grade", "")
    year_raw = fields.get("Year", "")
    cc = fields.get("cc", "")
    score = fields.get("Score", "")
    color = fields.get("Color", "")
    color_no = fields.get("Color No.", "")
    odometer = fields.get("Odometer", "")
    transmission = fields.get("Transmission", "")
    start_price_raw = fields.get("Start Price", "")
    auction_site = fields.get("Auction Site", "")
    holding_date = fields.get("Holding Date", "")
    exterior = fields.get("Exterior", "")
    interior = fields.get("Interior", "")
    inspection = fields.get("Inspection", "")

    # Parse year
    year = ""
    year_match = re.search(r'(20\d{2})', year_raw)
    if year_match:
        year = year_match.group(1)

    # Parse start price (remove commas)
    start_price = start_price_raw.replace(",", "") if start_price_raw else None

    # Rating from Score + Exterior/Interior
    rating = score
    if exterior or interior:
        rating = f"{score} {exterior}/{interior}".strip()

    # Parse auction site name
    site_name = auction_site.split("[")[0].strip() if auction_site else ""
    location = ""
    loc_match = re.search(r'\[(.+?)\]', auction_site)
    if loc_match:
        location = loc_match.group(1)

    # Build color string
    color_str = color
    if color_no:
        color_str = f"{color} ({color_no})"

    item_id = f"iauc-{vehicle_id}"

    return {
        "item_id": item_id,
        "lot_number": lot_no,
        "maker": maker,
        "model": model,
        "grade": grade or None,
        "chassis_code": None,
        "engine_specs": cc or None,
        "year": year or year_raw,
        "mileage": odometer or None,
        "inspection_expiry": inspection or None,
        "color": color_str or None,
        "rating": rating or None,
        "start_price": start_price if start_price else None,
        "auction_date": holding_date,
        "auction_house": site_name or "iAUC",
        "location": location or site_name,
        "status": "upcoming",
        "image_url": None,
        "images": [],
        "exhibit_sheet": None,
        "source": "iauc",
    }


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        # === Login ===
        print("[test] Login...")
        ok = await iauc_login(page)
        if not ok:
            print("  FAILED!")
            await browser.close()
            return
        print("  OK")

        # === English ===
        await page.evaluate("() => { const el = document.querySelector('a.jp'); if (el) el.click(); }")
        await page.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(3)

        # === Uncheck Kyoyuzaiko ===
        await page.evaluate("""() => {
            document.querySelectorAll('input[name="e[]"]').forEach(cb => { if (cb.checked) cb.click(); });
        }""")
        await asyncio.sleep(1)

        # === Next to Make & Model ===
        await page.evaluate('() => check_sites(document.querySelector(".page-next-button"))')
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(5)

        # === Select TOYOTA ===
        box = await page.evaluate("""() => {
            for (const li of document.querySelectorAll('li.search-maker-checkbox'))
                if (li.textContent.trim() === 'TOYOTA') {
                    const r = li.getBoundingClientRect();
                    return { x: r.x + r.width/2, y: r.y + r.height/2 };
                }
        }""")
        await page.mouse.click(box['x'], box['y'])
        await asyncio.sleep(3)

        # === Select AQUA model ===
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
                print(f"  Selected AQUA")
                break
        await asyncio.sleep(2)

        # === Next to Results ===
        await page.click('#next-bottom')
        await page.wait_for_load_state("networkidle", timeout=60000)
        await asyncio.sleep(10)

        result_text = await page.evaluate("""() => {
            const m = document.body.innerText.match(/Result[：:]\\s*(\\d[\\d,]*)/);
            return m ? m[1] : '0';
        }""")
        print(f"  Results: {result_text}")

        # Wait for car images to load
        print("  Waiting for images to load...")
        for attempt in range(10):
            img_count = await page.evaluate("() => document.querySelectorAll('img[src*=\"iauc_pic\"]').length")
            if img_count > 0:
                break
            await asyncio.sleep(2)
            print(f"    Waiting... ({attempt+1})")
        print(f"  Car images on page: {img_count}")

        # === Scrape first 3 vehicles ===
        print("\n[test] Scraping 3 vehicles...")
        all_vehicles = []

        # Get car images on list page — clicking them navigates to detail
        car_imgs = await page.evaluate("""() => {
            const items = [];
            document.querySelectorAll('img').forEach(img => {
                if (img.src && img.src.includes('iauc_pic') && img.naturalWidth > 50) {
                    const a = img.closest('a');
                    if (a && a.href) {
                        const match = a.href.match(/vehicleId=([^&]+)/);
                        if (match) {
                            items.push({ href: a.href, id: match[1] });
                        }
                    }
                }
            });
            // Deduplicate
            const seen = new Set();
            return items.filter(i => { if (seen.has(i.id)) return false; seen.add(i.id); return true; });
        }""")
        print(f"  Found {len(car_imgs)} vehicle links from images")

        # If no image links, try clicking car images by position
        if not car_imgs:
            car_imgs = await page.evaluate("""() => {
                const items = [];
                const seen = new Set();
                document.querySelectorAll('tr').forEach(tr => {
                    const img = tr.querySelector('img');
                    const tds = tr.querySelectorAll('td');
                    if (img && img.src && !img.src.includes('icon') && tds.length > 3) {
                        // Find any link with vehicleId
                        const links = tr.querySelectorAll('a[href*="vehicleId"], a[href*="detail"]');
                        links.forEach(a => {
                            const match = a.href.match(/vehicleId=([^&]+)/);
                            if (match && !seen.has(match[1])) {
                                seen.add(match[1]);
                                items.push({ href: a.href, id: match[1] });
                            }
                        });
                    }
                });
                return items;
            }""")
            print(f"  Found {len(car_imgs)} vehicle links from table rows")

        # Get vehicle IDs from image data-code attributes
        if not car_imgs:
            print("  Getting vehicle IDs from image data-code...")
            car_imgs = await page.evaluate("""() => {
                const items = [];
                const seen = new Set();
                document.querySelectorAll('img[data-code]').forEach(img => {
                    const code = img.getAttribute('data-code');
                    if (code && !seen.has(code)) {
                        seen.add(code);
                        items.push({ id: code });
                    }
                });
                return items;
            }""")
            print(f"  Found {len(car_imgs)} vehicles from data-code")

        # Get __tid from current URL
        tid = ""
        tid_match = re.search(r'__tid=([^&]+)', page.url)
        if tid_match:
            tid = tid_match.group(1)

        for i in range(min(3, len(car_imgs))):
            print(f"\n--- Vehicle {i+1} ---")
            vehicle_id = car_imgs[i]['id']
            print(f"  Vehicle ID: {vehicle_id}")

            detail_url = f"https://www.iauc.co.jp/detail/?vehicleId={vehicle_id}&owner_id=&from=vehicle&id=&__tid={tid}"
            await page.goto(detail_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(5)
            print(f"  URL: {page.url}")

            # Get text
            detail_text = await page.inner_text("body")
            vehicle = parse_detail(detail_text, vehicle_id)
            print(f"  {vehicle['maker']} {vehicle['model']} | {vehicle['grade']} | {vehicle['year']} | {vehicle['mileage']} | ¥{vehicle['start_price']}")
            print(f"  {vehicle['auction_house']} | {vehicle['auction_date']} | Rating: {vehicle['rating']}")

            # Get images
            imgs = await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('img'))
                    .filter(i => i.src.includes('iauc_pic') && i.naturalWidth > 100)
                    .map(i => ({ src: i.src, w: i.naturalWidth, h: i.naturalHeight }));
            }""")
            print(f"  Detail images: {len(imgs)}")

            car_images = []
            exhibit_sheet = None
            for img in imgs:
                src = img['src']
                letter_match = re.search(r'/([A-F])\d+\.JPG', src)
                if not letter_match:
                    continue
                letter = letter_match.group(1)
                print(f"    Uploading {letter} ({img['w']}x{img['h']})...")
                s3_url = await download_and_upload(page, src)
                if s3_url:
                    if letter == 'A':
                        exhibit_sheet = s3_url
                        print(f"      Sheet → {s3_url}")
                    else:
                        car_images.append(s3_url)
                        print(f"      Photo → {s3_url}")
                else:
                    print(f"      FAILED")

            vehicle["images"] = car_images
            vehicle["image_url"] = car_images[0] if car_images else None
            vehicle["exhibit_sheet"] = exhibit_sheet
            all_vehicles.append(vehicle)

            # Go back to list
            await page.go_back()
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(5)

            # Get text
            detail_text = await page.inner_text("body")

            # Parse vehicle data
            vehicle = parse_detail(detail_text, vehicle_id)
            print(f"  {vehicle['maker']} {vehicle['model']} | {vehicle['grade']} | {vehicle['year']} | {vehicle['mileage']} | ¥{vehicle['start_price']}")
            print(f"  {vehicle['auction_house']} | {vehicle['auction_date']}")

            # Get images
            imgs = await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('img'))
                    .filter(i => i.src.includes('iauc_pic') && i.naturalWidth > 100)
                    .map(i => ({ src: i.src, w: i.naturalWidth, h: i.naturalHeight }));
            }""")
            print(f"  Images: {len(imgs)}")

            # Upload car images (B-F) and auction sheet (A)
            car_images = []
            exhibit_sheet = None

            for img in imgs:
                src = img['src']
                # A = auction sheet, B-F = car photos
                letter_match = re.search(r'/([A-F])\d+\.JPG', src)
                if not letter_match:
                    continue

                letter = letter_match.group(1)
                print(f"    Uploading {letter} ({img['w']}x{img['h']})...")
                s3_url = await download_and_upload(page, src)

                if s3_url:
                    if letter == 'A':
                        exhibit_sheet = s3_url
                        print(f"      Auction sheet → {s3_url}")
                    else:
                        car_images.append(s3_url)
                        print(f"      Car photo → {s3_url}")
                else:
                    print(f"      FAILED")

            vehicle["images"] = car_images
            vehicle["image_url"] = car_images[0] if car_images else None
            vehicle["exhibit_sheet"] = exhibit_sheet
            all_vehicles.append(vehicle)

            # Go back to results
            await page.go_back()
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(3)

        # === Save to DB ===
        if all_vehicles:
            print(f"\n[test] Saving {len(all_vehicles)} vehicles to DB...")
            result = upsert_auctions(all_vehicles)
            print(f"  New: {result['new']}, Updated: {result['updated']}")

            for v in all_vehicles:
                print(f"  {v['item_id']}: {v['maker']} {v['model']} | imgs={len(v['images'])} | sheet={'yes' if v['exhibit_sheet'] else 'no'}")

        # Logout
        print("\n[test] Logging out...")
        await page.evaluate("""() => {
            document.querySelectorAll('a').forEach(a => {
                if (a.textContent.trim().includes('Logout')) a.click();
            });
        }""")
        await asyncio.sleep(3)

        await browser.close()
        print("\n[test] Done!")


if __name__ == "__main__":
    asyncio.run(main())
