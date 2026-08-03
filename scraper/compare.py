"""
History storage (a flat CSV, one row per room type per run) and the
comparison engine that turns it into %/£ deltas vs the last report and vs
the first-ever recorded price, plus how each competitor's price compares to
our own latest price in the same room category.
"""
import csv
from collections import defaultdict
from pathlib import Path

HISTORY_COLUMNS = [
    "run_ts", "property_id", "property_name", "is_own", "room_type",
    "category", "price_pw", "offer_text", "raw_text", "source_url",
]


def categorize(room_type: str) -> str:
    """Best-effort room category from a free-text room type name, so prices
    across differently-named competitor room types can still be compared."""
    t = room_type.lower()
    if "studio" in t:
        return "studio"
    if "ensuite" in t or "en-suite" in t or "en suite" in t:
        return "ensuite"
    if "twin" in t or "flat" in t or "apartment" in t or "bed" in t:
        return "shared"
    return "other"


def load_history(path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_history(path, new_rows: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_COLUMNS)
        if not exists:
            writer.writeheader()
        for row in new_rows:
            writer.writerow(row)


def build_comparison(history_rows: list[dict]) -> list[dict]:
    """One row per (property, room type) as of the latest run, with deltas
    vs the previous run, vs the first-ever run, and vs our own current price
    in the same category."""
    series = defaultdict(list)
    for r in history_rows:
        if r.get("price_pw"):
            series[(r["property_id"], r["room_type"])].append(r)
    for rows in series.values():
        rows.sort(key=lambda r: r["run_ts"])

    all_ts = sorted({r["run_ts"] for r in history_rows})
    if not all_ts:
        return []
    latest_ts = all_ts[-1]

    own_prices_by_category = defaultdict(list)
    for rows in series.values():
        last = rows[-1]
        if last.get("is_own") == "True" and last["run_ts"] == latest_ts:
            own_prices_by_category[last["category"]].append(float(last["price_pw"]))
    own_avg_by_category = {
        cat: sum(vals) / len(vals) for cat, vals in own_prices_by_category.items()
    }

    comparison = []
    for (property_id, room_type), rows in series.items():
        last = rows[-1]
        if last["run_ts"] != latest_ts:
            continue  # room type wasn't found this run - skip rather than show stale data
        price = float(last["price_pw"])
        category = last["category"]

        pct_vs_prev = delta_vs_prev = None
        if len(rows) >= 2:
            prev_price = float(rows[-2]["price_pw"])
            delta_vs_prev = price - prev_price
            pct_vs_prev = (delta_vs_prev / prev_price) * 100 if prev_price else None

        baseline_price = float(rows[0]["price_pw"])
        delta_vs_baseline = price - baseline_price
        pct_vs_baseline = (delta_vs_baseline / baseline_price) * 100 if baseline_price else None

        vs_own_pct = None
        is_own = last.get("is_own") == "True"
        if not is_own and category in own_avg_by_category:
            own_price = own_avg_by_category[category]
            vs_own_pct = ((price - own_price) / own_price) * 100 if own_price else None

        comparison.append({
            "property_id": property_id,
            "property_name": last["property_name"],
            "is_own": is_own,
            "room_type": room_type,
            "category": category,
            "price_pw": price,
            "offer_text": last.get("offer_text", ""),
            "delta_vs_prev": delta_vs_prev,
            "pct_vs_prev": pct_vs_prev,
            "delta_vs_baseline": delta_vs_baseline,
            "pct_vs_baseline": pct_vs_baseline,
            "vs_own_pct": vs_own_pct,
            "run_ts": last["run_ts"],
        })
    return comparison
