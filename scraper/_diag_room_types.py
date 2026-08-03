"""Throwaway diagnostic script v3: run the real scrape_all() pipeline
end-to-end against the fixed parsers and print every row, to validate
against Mark's ground-truth room type list before merging. Not part of the
pipeline - delete after use."""
from scraper.scrape import scrape_all

rows = scrape_all()
by_property = {}
for r in rows:
    by_property.setdefault(r["property_name"], []).append(r)

for prop_name, prop_rows in by_property.items():
    print(f"\n=== {prop_name} ({len(prop_rows)} rows) ===")
    for r in sorted(prop_rows, key=lambda x: (x.get("price_pw") is None, x.get("price_pw", 0))):
        print(f"  {r['room_type']!r:45s} £{r['price_pw']}\t[{r['category']}]")
        if r["room_type"] == "SCRAPE ERROR":
            print(f"    error: {r['offer_text']}")
