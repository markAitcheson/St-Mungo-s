"""Throwaway diagnostic: run scrape_all() end-to-end to confirm the Canvas
sold-out fix (Silver/Platinum en-suite should now appear with price=None,
offer="SOLD OUT" instead of vanishing) and that build_comparison() surfaces
them correctly. Not part of the pipeline - delete after use."""
from scraper.scrape import scrape_all
from scraper.compare import build_comparison, HISTORY_COLUMNS
from datetime import datetime, timezone

rows = scrape_all()
print(f"\n=== scrape_all(): Canvas rows ===")
for r in rows:
    if r["property_id"] == "canvas_boyce_house":
        print(f"  {r['room_type']!r:20s} price={r['price_pw']}  offer={r['offer_text']!r}")

# simulate what run_pipeline.py does: stamp a run_ts, convert to history-row
# shape (all values as strings, matching what load_history() would read back
# from the CSV), then run build_comparison() on just this one run.
run_ts = datetime.now(timezone.utc).isoformat()
history_rows = []
for r in rows:
    row = {c: r.get(c, "") for c in HISTORY_COLUMNS}
    row["run_ts"] = run_ts
    row["is_own"] = str(r.get("is_own", False))
    row["price_pw"] = "" if r.get("price_pw") is None else str(r["price_pw"])
    history_rows.append(row)

comparison = build_comparison(history_rows)
print(f"\n=== build_comparison(): Canvas rows ===")
for r in comparison:
    if r["property_id"] == "canvas_boyce_house":
        print(f"  {r['room_type']!r:20s} price={r['price_pw']}  offer={r['offer_text']!r}  equiv={r.get('equivalent_room')}")
