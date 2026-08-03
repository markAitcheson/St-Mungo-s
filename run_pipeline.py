"""Entry point run twice daily by .github/workflows/comp-set-report.yml:
scrape every property, append to history, rebuild the report, email it."""
from datetime import datetime, timezone
from pathlib import Path

from scraper.compare import append_history, build_comparison, load_history
from scraper.report_excel import build_excel
from scraper.scrape import scrape_all
from scraper.send_email import send_report_email

HISTORY_PATH = Path("data/history.csv")
REPORT_PATH = Path("data/latest_comp_set.xlsx")


def main():
    run_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")

    scraped = scrape_all()
    rows = [
        {
            "run_ts": run_ts,
            "property_id": r["property_id"],
            "property_name": r["property_name"],
            "is_own": r["is_own"],
            "room_type": r["room_type"],
            "category": r["category"],
            "price_pw": r["price_pw"] if r["price_pw"] is not None else "",
            "offer_text": r.get("offer_text", ""),
            "raw_text": r.get("raw_text", ""),
            "source_url": r.get("source_url", ""),
        }
        for r in scraped
    ]
    append_history(HISTORY_PATH, rows)

    history = load_history(HISTORY_PATH)
    comparison = build_comparison(history)
    build_excel(comparison, history, REPORT_PATH)
    send_report_email(REPORT_PATH, comparison, run_ts)

    print(f"Run complete: {len(rows)} rows scraped, {len(comparison)} in latest comparison.")


if __name__ == "__main__":
    main()
