"""Completeness verification: compare DB counts vs expectations after each scrape."""

from db import Session, get_target_date
from sqlalchemy import text


def get_db_counts(source: str) -> dict:
    """Get counts of upcoming vehicles in DB for a source."""
    session = Session()
    try:
        row = session.execute(
            text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(image_url) as with_images,
                    COUNT(exhibit_sheet) as with_sheets
                FROM auctions
                WHERE source = :source
                AND auction_date_norm >= :target
            """),
            {"source": source, "target": get_target_date()},
        ).fetchone()
        return {
            "total": row[0],
            "with_images": row[1],
            "with_sheets": row[2],
        }
    finally:
        session.close()


def log_completeness(source: str, db_counts: dict):
    """Log completeness metrics after a scrape run."""
    total = db_counts["total"]
    with_images = db_counts["with_images"]
    with_sheets = db_counts["with_sheets"]

    img_pct = (with_images / total * 100) if total > 0 else 0
    sheet_pct = (with_sheets / total * 100) if total > 0 else 0
    missing_imgs = total - with_images
    missing_sheets = total - with_sheets

    print(f"  [verify] {source}: {total} upcoming vehicles in DB")
    print(f"  [verify] {source}: {with_images}/{total} ({img_pct:.1f}%) have images — {missing_imgs} missing")
    print(f"  [verify] {source}: {with_sheets}/{total} ({sheet_pct:.1f}%) have exhibit sheets — {missing_sheets} missing")

    if missing_imgs > 50:
        print(f"  [verify] WARNING: {source} has {missing_imgs} vehicles without images!")
    if missing_sheets > total * 0.5 and total > 0:
        print(f"  [verify] WARNING: {source} has >50% vehicles without exhibit sheets!")
