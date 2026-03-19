"""Database connection and operations. Optimized with batch upserts."""

import os
import re
import json
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from jst import today_jst, get_target_date

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, echo=False, pool_size=5)
Session = sessionmaker(bind=engine)

BATCH_SIZE = 200

MONTH_MAP = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
             "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def normalize_auction_date(date_str: str, source: str) -> date | None:
    """Parse auction_date string into a proper date object."""
    if not date_str:
        return None
    try:
        # USS: 2026/03/18
        m = re.match(r'^(\d{4})/(\d{2})/(\d{2})', date_str)
        if m:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        # TAA: 3/18 (no year, assume current year)
        m = re.match(r'^(\d{1,2})/(\d{1,2})$', date_str)
        if m:
            return date(datetime.now().year, int(m.group(1)), int(m.group(2)))
        # iAUC: Mar 19.2026 12:25
        m = re.match(r'^(\w{3})\s+(\d{1,2})\.(\d{4})', date_str)
        if m and m.group(1) in MONTH_MAP:
            return date(int(m.group(3)), MONTH_MAP[m.group(1)], int(m.group(2)))
    except (ValueError, KeyError):
        pass
    return None


def upsert_auctions(vehicles: list[dict]) -> dict:
    """Batch upsert auctions using PostgreSQL ON CONFLICT. Returns counts."""
    session = Session()
    new_count = 0
    updated_count = 0

    try:
        for i in range(0, len(vehicles), BATCH_SIZE):
            batch = vehicles[i:i + BATCH_SIZE]
            for v in batch:
                item_id = str(v.get("item_id", ""))
                if not item_id:
                    continue

                price_raw = v.get("start_price")
                start_price = None
                if price_raw:
                    try:
                        start_price = Decimal(str(price_raw)) * 10000
                    except (ValueError, ArithmeticError):
                        start_price = None

                images = json.dumps(v.get("images", []))

                result = session.execute(
                    text("""
                        INSERT INTO auctions (
                            item_id, lot_number, maker, model, grade, chassis_code,
                            engine_specs, year, mileage, color, rating, start_price,
                            auction_date, auction_house, location, status,
                            image_url, images, exhibit_sheet, inspection_expiry,
                            source, auction_date_norm, first_seen, last_updated
                        ) VALUES (
                            :item_id, :lot_number, :maker, :model, :grade, :chassis_code,
                            :engine_specs, :year, :mileage, :color, :rating, :start_price,
                            :auction_date, :auction_house, :location, :status,
                            :image_url, CAST(:images AS jsonb), :exhibit_sheet, :inspection_expiry,
                            :source, :auction_date_norm, NOW(), NOW()
                        )
                        ON CONFLICT (item_id) DO UPDATE SET
                            last_updated = NOW(),
                            status = EXCLUDED.status,
                            lot_number = COALESCE(NULLIF(EXCLUDED.lot_number, ''), auctions.lot_number),
                            maker = COALESCE(NULLIF(EXCLUDED.maker, ''), auctions.maker),
                            model = COALESCE(NULLIF(EXCLUDED.model, ''), auctions.model),
                            grade = COALESCE(EXCLUDED.grade, auctions.grade),
                            chassis_code = COALESCE(EXCLUDED.chassis_code, auctions.chassis_code),
                            engine_specs = COALESCE(EXCLUDED.engine_specs, auctions.engine_specs),
                            year = COALESCE(NULLIF(EXCLUDED.year, ''), auctions.year),
                            mileage = COALESCE(EXCLUDED.mileage, auctions.mileage),
                            color = COALESCE(EXCLUDED.color, auctions.color),
                            rating = COALESCE(EXCLUDED.rating, auctions.rating),
                            start_price = COALESCE(EXCLUDED.start_price, auctions.start_price),
                            auction_date = COALESCE(NULLIF(EXCLUDED.auction_date, ''), auctions.auction_date),
                            auction_house = COALESCE(NULLIF(EXCLUDED.auction_house, ''), auctions.auction_house),
                            location = COALESCE(NULLIF(EXCLUDED.location, ''), auctions.location),
                            image_url = COALESCE(EXCLUDED.image_url, auctions.image_url),
                            images = CASE WHEN jsonb_array_length(EXCLUDED.images) > 0 THEN EXCLUDED.images ELSE auctions.images END,
                            exhibit_sheet = COALESCE(EXCLUDED.exhibit_sheet, auctions.exhibit_sheet),
                            inspection_expiry = COALESCE(EXCLUDED.inspection_expiry, auctions.inspection_expiry),
                            auction_date_norm = COALESCE(EXCLUDED.auction_date_norm, auctions.auction_date_norm)
                        RETURNING (xmax = 0) AS is_new
                    """),
                    {
                        "item_id": item_id,
                        "lot_number": re.sub(r'[^0-9]', '', str(v.get("lot_number", ""))),
                        "maker": v.get("maker", "").strip(),
                        "model": v.get("model", "").strip(),
                        "grade": v.get("grade"),
                        "chassis_code": v.get("chassis_code"),
                        "engine_specs": v.get("engine_specs"),
                        "year": v.get("year"),
                        "mileage": v.get("mileage"),
                        "color": v.get("color"),
                        "rating": v.get("rating"),
                        "start_price": start_price,
                        "auction_date": v.get("auction_date", ""),
                        "auction_house": v.get("auction_house", ""),
                        "location": v.get("location", ""),
                        "status": v.get("status", "upcoming"),
                        "image_url": v.get("image_url"),
                        "images": images,
                        "exhibit_sheet": v.get("exhibit_sheet"),
                        "inspection_expiry": v.get("inspection_expiry"),
                        "source": v.get("source", "aucnet"),
                        "auction_date_norm": normalize_auction_date(v.get("auction_date", ""), v.get("source", "")),
                    },
                )
                row = result.fetchone()
                if row and row[0]:
                    new_count += 1
                else:
                    updated_count += 1

            session.commit()

    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

    return {"new": new_count, "updated": updated_count}


def log_sync(new_count: int, updated_count: int, expired_count: int, total_scraped: int, duration_ms: int, error: str | None = None, source: str = "aucnet"):
    """Write a sync log entry."""
    session = Session()
    try:
        session.execute(
            text("""
                INSERT INTO sync_logs (run_at, new_count, updated_count, expired_count, total_scraped, duration_ms, error, source)
                VALUES (NOW(), :new, :updated, :expired, :total, :duration, :error, :source)
            """),
            {"new": new_count, "updated": updated_count, "expired": expired_count, "total": total_scraped, "duration": duration_ms, "error": error, "source": source},
        )
        session.commit()
    finally:
        session.close()


def mark_expired(active_item_ids: set[str], source: str | None = None) -> int:
    """Mark auctions not in the active set as expired. Scoped by source if provided."""
    if not active_item_ids:
        return 0

    session = Session()
    try:
        if source:
            result = session.execute(
                text("""
                    UPDATE auctions SET status = 'expired', last_updated = NOW()
                    WHERE status IN ('upcoming', 'active')
                    AND source = :source
                    AND item_id != ALL(:ids)
                """),
                {"ids": list(active_item_ids), "source": source},
            )
        else:
            result = session.execute(
                text("""
                    UPDATE auctions SET status = 'expired', last_updated = NOW()
                    WHERE status IN ('upcoming', 'active')
                    AND item_id != ALL(:ids)
                """),
                {"ids": list(active_item_ids)},
            )
        session.commit()
        return result.rowcount
    finally:
        session.close()


def get_site_credentials(site_id: str) -> tuple[str, str]:
    """Get credentials for an auction site from the auction_sites table."""
    session = Session()
    try:
        row = session.execute(
            text("SELECT user_id, password FROM auction_sites WHERE id = :site_id"),
            {"site_id": site_id},
        ).fetchone()
        if row and row[0] and row[1]:
            return row[0], row[1]
    finally:
        session.close()
    return "", ""


def get_credentials() -> tuple[str, str]:
    """Get Aucnet credentials from auction_sites table."""
    return get_site_credentials("aucnet")


def get_existing_item_ids(source: str) -> set[str]:
    """Get all existing item_ids for a source. Used to skip already-scraped vehicles."""
    session = Session()
    try:
        rows = session.execute(
            text("SELECT item_id FROM auctions WHERE source = :source AND image_url IS NOT NULL"),
            {"source": source},
        ).fetchall()
        return {row[0] for row in rows}
    finally:
        session.close()


def is_site_enabled(site_id: str) -> bool:
    """Check if an auction site is enabled."""
    session = Session()
    try:
        row = session.execute(
            text("SELECT is_enabled FROM auction_sites WHERE id = :site_id"),
            {"site_id": site_id},
        ).fetchone()
        return bool(row and row[0])
    finally:
        session.close()


def get_expired_auctions_with_images() -> list[dict]:
    """Get all expired auctions that have images, so we can delete from R2 before removing DB records."""
    session = Session()
    try:
        rows = session.execute(
            text("""
                SELECT id, item_id, image_url, images, exhibit_sheet, source
                FROM auctions
                WHERE auction_date_norm < :cutoff
                AND auction_date_norm IS NOT NULL
            """),
            {"cutoff": get_target_date()},
        ).fetchall()
        results = []
        for row in rows:
            images_json = row[2] or "[]"
            if isinstance(images_json, str):
                try:
                    images_list = json.loads(images_json)
                except:
                    images_list = []
            else:
                images_list = images_json if isinstance(images_json, list) else []
            results.append({
                "id": row[0],
                "item_id": row[1],
                "image_url": row[2],
                "images": images_list,
                "exhibit_sheet": row[4],
                "source": row[5],
            })
        return results
    finally:
        session.close()


def delete_expired_auctions() -> int:
    """Delete auctions before target date (tomorrow). Today's auctions can't be bid on. Returns count deleted."""
    cutoff = get_target_date()
    session = Session()
    try:
        # First delete car_list_items that reference these auctions
        session.execute(
            text("""
                DELETE FROM car_list_items
                WHERE auction_id IN (
                    SELECT id FROM auctions
                    WHERE auction_date_norm < :cutoff
                    AND auction_date_norm IS NOT NULL
                )
            """),
            {"cutoff": cutoff},
        )
        # Then delete bid_requests that reference these auctions
        session.execute(
            text("""
                DELETE FROM bid_requests
                WHERE auction_id IN (
                    SELECT id FROM auctions
                    WHERE auction_date_norm < :cutoff
                    AND auction_date_norm IS NOT NULL
                )
            """),
            {"cutoff": cutoff},
        )
        # Now delete the auctions
        result = session.execute(
            text("""
                DELETE FROM auctions
                WHERE auction_date_norm < :cutoff
                AND auction_date_norm IS NOT NULL
            """),
            {"cutoff": cutoff},
        )
        session.commit()
        return result.rowcount
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
