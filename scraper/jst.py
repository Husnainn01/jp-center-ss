"""Japan Standard Time utilities.

Core rule: keep today + future vehicles in DB.
- Customer needs to see today's vehicles (may still be bidding) AND tomorrow's
- Scrapers keep today + future, only skip past dates
- Cleanup deletes auctions from yesterday and older
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
    True — include today's auctions in scrape results.
    Customers may still need to see today's vehicles (auction may not have started yet).
    iAUC shows today + future by default, so we keep that behavior.
    """
    return True


def get_target_date():
    """
    Returns today in JST — the earliest auction date worth keeping.

    Mar 20 09:00 JST → Mar 20   (keep today + future)
    Mar 20 23:59 JST → Mar 20   (still today)
    Mar 21 00:01 JST → Mar 21   (new day, target rolls forward)

    Anything BEFORE this date is skipped (yesterday + past).
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
