"""Delete ALL data: all R2 images + all DB auction records.
Run with: python3 nuke_all_data.py"""

import os
import sys

# Set DATABASE_URL + Railway bucket before any imports that use it
os.environ["DATABASE_URL"] = "postgresql://postgres:BPaVRgCxgvGDilvonyVwqvqbSsJAYnWJ@shuttle.proxy.rlwy.net:35795/railway"
os.environ["S3_ENDPOINT"] = "https://t3.storageapi.dev"
os.environ["S3_BUCKET"] = "organized-cube-9oku28ouqf"
os.environ["S3_ACCESS_KEY"] = "tid_IEkAKLjDPbGkOiwgQRDr_pqKAdAlqdBmsDN_cMHvdKdyxHSrtq"
os.environ["S3_SECRET_KEY"] = "tsec_04C2KII5qgpbAIKwoAHztP60jab3EG_vcIzPM15IbCZW_FleTugOWeU5Oi8dYdCEZ5Lqtf"

from dotenv import load_dotenv
load_dotenv(override=False)  # Don't override the URL we just set

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from storage import _get_client, S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY
import time

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)


def get_all_r2_keys() -> list[str]:
    """Get all image keys from all auctions."""
    import re
    pattern = re.compile(r'^/s3/(.+)$')
    keys = set()

    with Session() as session:
        rows = session.execute(text("""
            SELECT images, image_url, exhibit_sheet FROM auctions
        """)).fetchall()

        for row in rows:
            images, image_url, exhibit_sheet = row
            if images:
                for img in images:
                    if isinstance(img, str):
                        m = pattern.match(img)
                        if m:
                            keys.add(m.group(1))
            if image_url:
                m = pattern.match(image_url)
                if m:
                    keys.add(m.group(1))
            if exhibit_sheet:
                m = pattern.match(exhibit_sheet)
                if m:
                    keys.add(m.group(1))

    return list(keys)


def list_all_r2_objects() -> list[str]:
    """List ALL objects in the R2 bucket (catches orphans too)."""
    client = _get_client()
    all_keys = []
    continuation_token = None

    while True:
        kwargs = {"Bucket": S3_BUCKET, "MaxKeys": 1000}
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token

        response = client.list_objects_v2(**kwargs)
        contents = response.get("Contents", [])
        all_keys.extend(obj["Key"] for obj in contents)

        if response.get("IsTruncated"):
            continuation_token = response["NextContinuationToken"]
        else:
            break

    return all_keys


def delete_r2_objects(keys: list[str]) -> int:
    """Delete objects from R2 in batches of 50."""
    if not keys:
        return 0

    client = _get_client()
    deleted = 0

    for i in range(0, len(keys), 50):
        batch = keys[i:i + 50]
        try:
            response = client.delete_objects(
                Bucket=S3_BUCKET,
                Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True},
            )
            errors = response.get("Errors", [])
            deleted += len(batch) - len(errors)
            if errors:
                print(f"  Batch {i//50+1}: {len(errors)} errors")
        except Exception as e:
            print(f"  Batch {i//50+1} failed: {e}")

        if i + 50 < len(keys):
            time.sleep(0.5)

    return deleted


def truncate_auctions():
    """Delete all records from auctions table."""
    with Session() as session:
        result = session.execute(text("DELETE FROM auctions"))
        count = result.rowcount
        session.commit()
        return count


def main():
    # Step 1: Count current data
    with Session() as session:
        count = session.execute(text("SELECT COUNT(*) FROM auctions")).scalar()
    print(f"\n=== Current state ===")
    print(f"  Auctions in DB: {count}")

    # List all R2 objects
    print(f"\n=== Listing all R2 objects ===")
    r2_keys = list_all_r2_objects()
    print(f"  R2 objects: {len(r2_keys)}")
    if r2_keys:
        prefixes = {}
        for k in r2_keys:
            prefix = k.split("/")[0] if "/" in k else "(root)"
            prefixes[prefix] = prefixes.get(prefix, 0) + 1
        for p, c in sorted(prefixes.items()):
            print(f"    {p}: {c} files")

    if count == 0 and len(r2_keys) == 0:
        print("\nAlready empty. Nothing to delete.")
        return

    print(f"\n  Deleting {count} auction records + {len(r2_keys)} R2 images...")

    # Step 2: Delete R2 images
    if r2_keys:
        print(f"\n=== Deleting {len(r2_keys)} R2 objects ===")
        deleted = delete_r2_objects(r2_keys)
        print(f"  Deleted: {deleted}/{len(r2_keys)}")

    # Step 3: Truncate auctions
    if count > 0:
        print(f"\n=== Deleting {count} auction records ===")
        deleted_db = truncate_auctions()
        print(f"  Deleted: {deleted_db} records")

    # Verify
    with Session() as session:
        remaining = session.execute(text("SELECT COUNT(*) FROM auctions")).scalar()
    remaining_r2 = len(list_all_r2_objects())
    print(f"\n=== Done ===")
    print(f"  DB records remaining: {remaining}")
    print(f"  R2 objects remaining: {remaining_r2}")


if __name__ == "__main__":
    main()
