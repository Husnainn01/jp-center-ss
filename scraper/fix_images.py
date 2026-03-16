"""One-time script: update all existing auctions with full image URLs (01-30)."""

import json
import re
from db import Session
from sqlalchemy import text

def generate_all_images(image_url: str) -> list[str]:
    """From a single image URL, generate all possible numbered variants."""
    if not image_url or "aucnetcars.com" not in image_url:
        return []

    # Upgrade to /3/ (high-res)
    url = image_url.replace("/tvaa/1/", "/tvaa/3/").replace("/stock/1/", "/stock/3/")

    if "/tvaa/" in url:
        # Pattern: .../002085/00280803.jpg → base=00280  8, suffix changes 01-30
        match = re.match(r"^(.*/)(\d+?)(\d{2})\.jpg$", url)
        if match:
            base = match.group(1) + match.group(2)
            return [f"{base}{str(i).zfill(2)}.jpg" for i in range(1, 31)]

    elif "/stock/" in url:
        # Pattern: .../2026/04366188_03.jpg → base=04366188
        match = re.match(r"^(.*/)([^_]+)_\d{2}\.jpg$", url)
        if match:
            base = match.group(1) + match.group(2)
            return [f"{base}_{str(i).zfill(2)}.jpg" for i in range(1, 26)]

    return [url]


def main():
    session = Session()
    rows = session.execute(text("SELECT id, image_url, images FROM auctions")).fetchall()
    print(f"Processing {len(rows)} auctions...")

    updated = 0
    for row in rows:
        auction_id, image_url, current_images = row

        # Parse current images
        try:
            existing = json.loads(current_images) if current_images else []
        except (json.JSONDecodeError, TypeError):
            existing = []

        # Generate full set
        all_imgs = generate_all_images(image_url)
        if not all_imgs and existing:
            all_imgs = generate_all_images(existing[0])

        if len(all_imgs) > len(existing):
            session.execute(
                text("UPDATE auctions SET images = CAST(:imgs AS jsonb), image_url = :main WHERE id = :id"),
                {"imgs": json.dumps(all_imgs), "main": all_imgs[0] if all_imgs else image_url, "id": auction_id},
            )
            updated += 1

    session.commit()
    session.close()
    print(f"Updated {updated} auctions with full image sets")


if __name__ == "__main__":
    main()
