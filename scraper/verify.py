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


def get_daily_counts(source: str) -> list[dict]:
    """Get vehicle counts per auction day for a source."""
    session = Session()
    try:
        rows = session.execute(
            text("""
                SELECT
                    auction_date_norm::text as date,
                    COUNT(*) as total,
                    COUNT(image_url) as with_images,
                    COUNT(exhibit_sheet) as with_sheets
                FROM auctions
                WHERE source = :source
                AND auction_date_norm >= :target
                AND auction_date_norm IS NOT NULL
                GROUP BY auction_date_norm
                ORDER BY auction_date_norm ASC
            """),
            {"source": source, "target": get_target_date()},
        ).fetchall()
        return [{"date": r[0], "total": r[1], "with_images": r[2], "with_sheets": r[3]} for r in rows]
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

    # Per-day breakdown
    daily = get_daily_counts(source)
    if daily:
        from jst import today_jst
        from datetime import timedelta
        today = today_jst()
        tomorrow = today + timedelta(days=1)
        tomorrow_str = str(tomorrow)

        for day in daily[:5]:  # show next 5 days
            marker = " ◀ TOMORROW" if day["date"] == tomorrow_str else ""
            today_marker = " (today)" if day["date"] == str(today) else ""
            print(f"  [verify]   {day['date']}: {day['total']} vehicles, {day['with_images']} imgs, {day['with_sheets']} sheets{marker}{today_marker}")

        # Alert if tomorrow has low coverage
        tomorrow_data = next((d for d in daily if d["date"] == tomorrow_str), None)
        if tomorrow_data:
            img_coverage = (tomorrow_data["with_images"] / tomorrow_data["total"] * 100) if tomorrow_data["total"] > 0 else 0
            if img_coverage < 80:
                print(f"  [verify] WARNING: Tomorrow ({tomorrow_str}) has only {img_coverage:.0f}% image coverage!")
        else:
            print(f"  [verify] WARNING: No vehicles found for tomorrow ({tomorrow_str})!")

    if missing_imgs > 50:
        print(f"  [verify] WARNING: {source} has {missing_imgs} vehicles without images!")
    if missing_sheets > total * 0.5 and total > 0:
        print(f"  [verify] WARNING: {source} has >50% vehicles without exhibit sheets!")
