"""Japan Standard Time utilities for smart auction date switching."""

from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

# After this hour (JST), today's auctions are considered finished — switch to tomorrow
# Most Japanese car auctions run 9 AM - 12 PM JST, so by noon they're done
CUTOFF_HOUR = 12  # 12:00 PM (noon) JST


def now_jst() -> datetime:
    """Current time in JST."""
    return datetime.now(JST)


def today_jst():
    """Today's date in JST."""
    return now_jst().date()


def should_scrape_today() -> bool:
    """Return True if we should still scrape today's auctions (before 2 PM JST)."""
    return now_jst().hour < CUTOFF_HOUR


def get_target_date():
    """Get the auction date we should be scraping right now.
    Before 2 PM JST → today. After 2 PM JST → tomorrow."""
    now = now_jst()
    if now.hour < CUTOFF_HOUR:
        return now.date()
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
