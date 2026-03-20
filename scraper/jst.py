"""Japan Standard Time utilities.

Core rule: always target tomorrow's date in JST.
- Today's auctions have already started — too late to bid
- Customer needs tomorrow's vehicles to submit bids in advance
- Scrapers skip today + past, only keep tomorrow and future
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
    False — today's auctions have already started, no point scraping them.
    iAUC uses this to uncheck the 'Today' button so it doesn't even fetch today's vehicles.
    """
    return False


def get_target_date():
    """
    Returns tomorrow in JST — the earliest auction date worth scraping.

    Mar 20 09:00 JST → Mar 21   (skip today, target tomorrow)
    Mar 20 23:59 JST → Mar 21   (still targeting tomorrow)
    Mar 21 00:01 JST → Mar 22   (new day, tomorrow shifts forward)

    Anything before this date is skipped (today + past).
    """
    return today_jst() + timedelta(days=1)


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
