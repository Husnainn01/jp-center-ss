"""Japan Standard Time utilities.

Core rule: ONLY future dates matter.
- Today's auctions are useless — they've already started
- Customer only sees TOMORROW and beyond
- Scrapers skip today + past, only keep tomorrow onwards
- Cleanup deletes today and older
"""

from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))


def now_jst() -> datetime:
    """Current datetime in JST."""
    return datetime.now(JST)


def today_jst():
    """Today's date in JST."""
    return now_jst().date()


def should_scrape_today() -> bool:
    """False — today's auctions have already started, no point scraping them."""
    return False


def get_target_date():
    """
    Returns TOMORROW in JST — the earliest auction date worth keeping.

    Mar 25 09:00 JST → Mar 26  (tomorrow)
    Mar 25 23:59 JST → Mar 26  (still tomorrow)
    Mar 26 00:01 JST → Mar 27  (new day, target rolls forward)

    Today + past are SKIPPED. Only tomorrow and future are kept.
    """
    return today_jst() + timedelta(days=1)


def is_overnight_window() -> bool:
    """True between 11pm and 6am JST."""
    hour = now_jst().hour
    return hour >= 23 or hour < 6


def is_auction_date_expired(auction_date) -> bool:
    """True if auction_date is before tomorrow in JST (today + past = expired)."""
    if auction_date is None:
        return False
    target = get_target_date()
    if hasattr(auction_date, 'date'):
        auction_date = auction_date.date()
    return auction_date < target
