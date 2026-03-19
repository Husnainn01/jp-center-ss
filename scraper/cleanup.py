"""Cleanup expired auctions: delete R2 images first, then remove DB records."""

import re
import time
from storage import _get_client, S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY
from db import get_expired_auctions_with_images, delete_expired_auctions
from jst import today_jst


def _extract_r2_keys(auction: dict) -> list[str]:
    """Extract all R2 object keys from an auction record."""
    keys = set()
    # Pattern: /s3/prefix/filename.jpg → key is prefix/filename.jpg
    pattern = re.compile(r'^/s3/(.+)$')

    # From images array
    for img_url in auction.get("images", []):
        if isinstance(img_url, str):
            m = pattern.match(img_url)
            if m:
                keys.add(m.group(1))

    # From image_url
    if auction.get("image_url"):
        m = pattern.match(auction["image_url"])
        if m:
            keys.add(m.group(1))

    # From exhibit_sheet
    if auction.get("exhibit_sheet"):
        m = pattern.match(auction["exhibit_sheet"])
        if m:
            keys.add(m.group(1))

    return list(keys)


def delete_r2_images(keys: list[str]) -> int:
    """Delete images from Cloudflare R2. Returns count of deleted objects."""
    if not keys or not S3_ACCESS_KEY or not S3_SECRET_KEY:
        return 0

    client = _get_client()
    deleted = 0
    max_retries = 3

    # Use smaller batches (50) to avoid R2 InternalError on large deletes
    total_batches = (len(keys) + 49) // 50
    for i in range(0, len(keys), 50):
        batch = keys[i:i + 50]
        batch_num = i // 50 + 1
        for attempt in range(1, max_retries + 1):
            try:
                response = client.delete_objects(
                    Bucket=S3_BUCKET,
                    Delete={
                        "Objects": [{"Key": k} for k in batch],
                        "Quiet": True,
                    },
                )
                errors = response.get("Errors", [])
                deleted += len(batch) - len(errors)
                if errors:
                    print(f"  [cleanup] Batch {batch_num}/{total_batches}: {len(errors)} R2 errors")
                break  # success, move to next batch
            except Exception as e:
                if attempt < max_retries:
                    print(f"  [cleanup] Batch {batch_num}/{total_batches} failed (attempt {attempt}/{max_retries}), retrying in {attempt * 3}s...")
                    time.sleep(attempt * 3)
                else:
                    print(f"  [cleanup] Batch {batch_num}/{total_batches} failed after {max_retries} attempts: {e}")

        # Pause between batches to avoid rate limiting
        if i + 50 < len(keys):
            time.sleep(1)

    return deleted


def run_cleanup() -> dict:
    """Full cleanup: delete R2 images for expired auctions, then delete DB records."""
    today = today_jst()
    print(f"  [cleanup] Starting cleanup (today JST: {today})")

    # Step 1: Get expired auctions with their image URLs
    expired = get_expired_auctions_with_images()
    if not expired:
        print("  [cleanup] No expired auctions to clean up")
        return {"expired_auctions": 0, "r2_images_deleted": 0}

    print(f"  [cleanup] Found {len(expired)} expired auctions to delete")

    # Step 2: Collect all R2 keys
    all_keys = []
    for auction in expired:
        keys = _extract_r2_keys(auction)
        all_keys.extend(keys)

    print(f"  [cleanup] {len(all_keys)} R2 images to delete")

    # Step 3: Delete images from R2
    r2_deleted = 0
    if all_keys:
        r2_deleted = delete_r2_images(all_keys)
        print(f"  [cleanup] Deleted {r2_deleted} images from R2")

    # Step 4: Delete expired auctions from DB
    db_deleted = delete_expired_auctions()
    print(f"  [cleanup] Deleted {db_deleted} expired auctions from DB")

    return {"expired_auctions": db_deleted, "r2_images_deleted": r2_deleted}
