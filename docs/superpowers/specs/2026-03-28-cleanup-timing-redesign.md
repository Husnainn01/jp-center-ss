# Cleanup Timing Redesign

## Problem

The scraper cleanup runs every 30 minutes as part of the sync cycle. It deletes auctions where `auction_date_norm < tomorrow JST`, which means today's auctions get deleted at midnight. Bid requests are cascade-deleted too, and while bid data is preserved in the CRM, the premature deletion means images disappear before staff can review them in the morning.

## Solution

Move cleanup from the 30-min sync loop to a **dedicated daily cron job at 11:00 AM JST**. Change the deletion cutoff from "tomorrow" to "today" — so only yesterday and older auctions are deleted.

### Design Decisions

- **11 AM JST chosen** because auctions run in the morning and staff have reviewed everything by then
- **Cutoff = today** means Monday's 11 AM cleanup deletes Sunday and older; Tuesday's deletes Monday and older
- **Bid requests still cascade-deleted** — bid data is already saved in CRM, no need to keep it in JP-Center
- **Car list items still cascade-deleted** — ephemeral data
- **R2/Tigris images still deleted** — storage costs must be managed

### Changes

| File | Change |
|---|---|
| `scraper/db.py` | `delete_expired_auctions()`: change cutoff from `get_target_date()` to `today_jst()` |
| `scraper/iauc_sync.py` | Remove `run_cleanup()` call from sync cycle |
| `scraper/run_iauc.py` | Add `scheduler.add_job` cron at 11:00 JST for cleanup |
| `scraper/run_ninja.py` | Same: remove cleanup from sync, add 11 AM cron |
| `scraper/run_aucnet.py` | Same pattern |
| `scraper/run_taa.py` | Same pattern |
| Corresponding sync files | Remove `run_cleanup()` calls |

### Data Flow After Change

```
Scraper cycle (every 30 min):
  login → scrape → DB upsert → backfill → verify → cache invalidate
  (NO cleanup)

Daily 11:00 AM JST cron:
  cleanup → delete auctions where auction_date_norm < today_jst()
         → delete associated car_list_items and bid_requests
         → delete R2/Tigris images for those auctions
```

### Edge Cases

- **Service restart at 11 AM**: Missed cleanup catches up next day (deletes everything older than that day)
- **Multiple scrapers with 11 AM cron**: Cleanup is idempotent — second run finds nothing to delete
- **No schema/migration changes needed**
