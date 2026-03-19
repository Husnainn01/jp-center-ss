"""Japan Standard Time utilities for smart auction date switching."""

from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))


def now_jst() -> datetime:
    """Current time in JST."""
    return datetime.now(JST)


def today_jst():
    """Today's date in JST."""
    return now_jst().date()


def should_scrape_today() -> bool:
    """Always False — today's auctions are already running, can't bid on them."""
    return False


def get_target_date():
    """Always tomorrow — today's auctions are already in progress, scrape tomorrow onwards."""
    now = now_jst()
    return (now + timedelta(days=1)).date()


def is_auction_date_expired(auction_date) -> bool:
    """Check if an auction date has passed (is before today in JST)."""
    if auction_date is None:
        return False
    today = today_jst()
    # Handle both date and datetime objects
    if hasattr(auction_date, 'date'):
        auction_date = auction_date.date()
    return auction_date < today
