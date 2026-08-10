"""Throwaway diagnostic (see HANDOFF.md "Useful commands for resuming" for
the push/trigger/revert pattern this follows): re-scrapes every competitor
site live right now and compares each room's price to what's currently
committed in data/history.csv's most recent run, to check whether several
days of unchanged prices are genuine (the sites really haven't moved) or a
scraper/caching problem. Not part of the real pipeline - delete after use."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper.compare import load_history
from scraper.scrape import scrape_all


def main():
    history = load_history("data/history.csv")
    last_ts = max((r["run_ts"] for r in history), default=None)
    print(f"Last committed run: {last_ts}\n")

    last_by_key = {
        (r["property_id"], r["room_type"]): (r.get("price_pw") or None, r.get("offer_text") or "")
        for r in history
        if r["run_ts"] == last_ts
    }

    print("Doing a fresh live scrape now...\n")
    scraped = scrape_all()

    diffs = 0
    seen_keys = set()
    for r in scraped:
        key = (r["property_id"], r["room_type"])
        seen_keys.add(key)
        old_price, old_offer = last_by_key.get(key, (None, None))
        new_price = r.get("price_pw")
        changed = str(old_price) != str(new_price)
        flag = "CHANGED" if changed else "same"
        if changed:
            diffs += 1
        old_str = "" if old_price is None else old_price
        print(f"{flag:8} {r['property_name']:42} {r['room_type']:32} "
              f"committed={old_str!s:>10} live={new_price!s:>10} offer={r.get('offer_text', '')!r}")

    missing = set(last_by_key) - seen_keys
    for key in missing:
        print(f"MISSING  {key} - was in last committed run, not returned by this live scrape")

    print(f"\n{diffs} room(s) changed price out of {len(scraped)} scraped live, "
          f"{len(missing)} missing vs the last committed run.")


if __name__ == "__main__":
    main()
