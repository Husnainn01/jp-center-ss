"""Database connection and operations. Optimized with batch upserts."""

import os
import json
from decimal import Decimal
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, echo=False, pool_size=5)
Session = sessionmaker(bind=engine)

BATCH_SIZE = 200


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
                            source, first_seen, last_updated
                        ) VALUES (
                            :item_id, :lot_number, :maker, :model, :grade, :chassis_code,
                            :engine_specs, :year, :mileage, :color, :rating, :start_price,
                            :auction_date, :auction_house, :location, :status,
                            :image_url, CAST(:images AS jsonb), :exhibit_sheet, :inspection_expiry,
                            :source, NOW(), NOW()
                        )
                        ON CONFLICT (item_id) DO UPDATE SET
                            lot_number = EXCLUDED.lot_number,
                            maker = EXCLUDED.maker,
                            model = EXCLUDED.model,
                            grade = EXCLUDED.grade,
                            chassis_code = EXCLUDED.chassis_code,
                            engine_specs = EXCLUDED.engine_specs,
                            year = EXCLUDED.year,
                            mileage = EXCLUDED.mileage,
                            color = EXCLUDED.color,
                            rating = EXCLUDED.rating,
                            start_price = EXCLUDED.start_price,
                            auction_date = EXCLUDED.auction_date,
                            auction_house = EXCLUDED.auction_house,
                            location = EXCLUDED.location,
                            status = EXCLUDED.status,
                            image_url = EXCLUDED.image_url,
                            images = EXCLUDED.images,
                            exhibit_sheet = EXCLUDED.exhibit_sheet,
                            inspection_expiry = EXCLUDED.inspection_expiry,
                            source = EXCLUDED.source,
                            last_updated = NOW()
                        RETURNING (xmax = 0) AS is_new
                    """),
                    {
                        "item_id": item_id,
                        "lot_number": v.get("lot_number", ""),
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


def get_credentials() -> tuple[str, str]:
    """Get credentials from DB settings or .env."""
    session = Session()
    try:
        row = session.execute(
            text("SELECT auction_user_id, auction_password FROM session_state WHERE id = 1")
        ).fetchone()
        if row and row[0] and row[1]:
            return row[0], row[1]
    finally:
        session.close()

    return os.getenv("AUCTION_USER_ID", ""), os.getenv("AUCTION_PASSWORD", "")
