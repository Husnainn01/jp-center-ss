"""Japan Standard Time utilities.

Core rule: always target today's date in JST.
- Auctions from previous days are skipped (they are gone)
- After midnight JST, today_jst() naturally becomes the next day
- No manual time-based switching needed — the date rolls itself
"""

from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))


def now_jst() -> datetime:
    """Current datetime in JST."""
    return datetime.now(JST)


def today_jst():
    """Today's date in JST. After midnight this automatically becomes tomorrow."""
    return now_jst().date()


def should_scrape_today() -> bool:
    """
    Always True — today's auctions are always upcoming until midnight JST.
    After midnight, today_jst() itself rolls to the new day automatically.
    No manual switching needed.
    """
    return True


def get_target_date():
    """
    Always returns today in JST.

    Mar 19 09:00 JST → Mar 19   (today's upcoming auctions)
    Mar 19 23:59 JST → Mar 19   (still today until midnight)
    Mar 20 00:01 JST → Mar 20   (new day, now targeting Mar 20)

    Anything before this date is a past auction and gets skipped.
    """
    return today_jst()


def is_overnight_window() -> bool:
    """
    True between 11pm and 6am JST.
    This is when we run the full 40k overnight pass — low traffic, site is quiet.
    Nothing to do with auction closing time, just best scraping window.
    """
    hour = now_jst().hour
    return hour >= 23 or hour < 6


def is_auction_date_expired(auction_date) -> bool:
    """
    True if auction_date is before today in JST.
    Used by cleanup to remove past auctions from DB.
    """
    if auction_date is None:
        return False
    target = get_target_date()
    if hasattr(auction_date, 'date'):
        auction_date = auction_date.date()
    return auction_date < target
